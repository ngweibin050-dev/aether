import { create } from "zustand";
import { api } from "./api";

const clone = (x) => JSON.parse(JSON.stringify(x));

export const useStore = create((set, get) => ({
  // ---- server state (single source of truth, shared by laptop and hand modes) ----
  state: null,
  meshes: {},
  meshVersion: -1,
  compute: "local",

  // ---- ui state ----
  mode: "laptop",            // laptop | hand
  gizmo: "translate",        // translate | rotate | scale
  axis: null,                // null | x | y | z  (Blender-style axis lock)
  panels: { left: true, right: true, results: true },
  rightTab: "object",        // object | optics | desk
  busy: {},
  toast: null,
  results: { hologram: null, recon: null, sweep: null, eye: null, desk: null, window: null, hand: null,
             speckle: null, search: null, film: null },
  chat: [],
  undo: [], redo: [],
  handFrame: null,           // latest hand landmarks for the overlay

  setPanel: (k, v) => set((s) => ({ panels: { ...s.panels, [k]: v ?? !s.panels[k] } })),
  setMode: (mode) => set({ mode }),
  setGizmo: (gizmo) => set({ gizmo }),
  setAxis: (axis) => set({ axis }),
  setTab: (rightTab) => set({ rightTab }),
  setHandFrame: (handFrame) => set({ handFrame }),
  notify: (text, kind = "info") => {
    set({ toast: { text, kind, t: Date.now() } });
    setTimeout(() => get().toast?.text === text && set({ toast: null }), 3500);
  },

  async load() {
    const j = await api("/api/state");
    set({ state: j.state, compute: j.compute });
    await get().syncMeshes();
  },

  async syncMeshes() {
    const s = get().state;
    if (!s || s.version === get().meshVersion) return;
    const j = await api("/api/meshes");
    set({ meshes: j.meshes, meshVersion: j.version });
  },

  applyState(state) {
    set({ state });
    get().syncMeshes();
  },

  // ---- tools (same names the AI agent uses) ----
  async tool(name, args = {}, { record = true, quiet = false } = {}) {
    const before = get().state && clone(get().state.parts);
    set((s) => ({ busy: { ...s.busy, [name]: true } }));
    try {
      const j = await api("/api/tool", { name, args });
      if (record && before && JSON.stringify(before) !== JSON.stringify(j.state.parts))
        set((s) => ({ undo: [...s.undo.slice(-49), { parts: before, selected: s.state.selected }], redo: [] }));
      get().applyState(j.state);
      get().ingest(name, j.result);
      return j.result;
    } catch (e) {
      if (!quiet) get().notify(e.message, "error");
      throw e;
    } finally {
      set((s) => ({ busy: { ...s.busy, [name]: false } }));
    }
  },

  ingest(name, r) {
    if (!r) return;
    const im = r._images || {};
    const res = { ...get().results };
    if (im.hologram) res.hologram = { img: im.hologram, info: r };
    if (im.reconstruction) res.recon = { img: im.reconstruction, z: r.z_mm };
    if (im.sweep && r.depths_mm) res.sweep = { imgs: im.sweep, depths: r.depths_mm, sharp: r.share_sharp_pct, i: Math.floor(im.sweep.length / 2) };
    if (im.eye) res.eye = { img: im.eye, info: r };
    if (name === "desk_check" && r.rows) res.desk = r;
    if (name === "window_check" && r.parts) res.window = r;
    if (name === "hand_check") res.hand = r;
    if (im.speckle_one) res.speckle = { ...r, imgs: im };
    if (name === "speckle_compare" && !im.speckle_one && r.one_frame !== undefined) res.speckle = { ...(res.speckle || {}), ...r };
    if (name === "search_column_width" && r.tried) res.search = r;
    if (name === "export_film" && r.path) res.film = { ...r, imgs: im };
    set({ results: res });
  },

  select(id) {
    const s = get().state;
    if (!s) return;
    set({ state: { ...s, selected: id } });
  },

  async pushParts(parts, selected) {
    const j = await api("/api/scene", { parts, selected });
    get().applyState(j.state);
  },

  async commitTransform(id, t) {
    return get().tool("update_part", { id, ...t });
  },

  async undoOnce() {
    const { undo, state } = get();
    if (!undo.length) return;
    const prev = undo[undo.length - 1];
    set((s) => ({ undo: s.undo.slice(0, -1), redo: [...s.redo, { parts: clone(state.parts), selected: state.selected }] }));
    await get().pushParts(prev.parts, prev.selected);
  },
  async redoOnce() {
    const { redo, state } = get();
    if (!redo.length) return;
    const next = redo[redo.length - 1];
    set((s) => ({ redo: s.redo.slice(0, -1), undo: [...s.undo, { parts: clone(state.parts), selected: state.selected }] }));
    await get().pushParts(next.parts, next.selected);
  },
  async duplicate() {
    const s = get().state;
    const p = s?.parts.find((x) => x.id === s.selected);
    if (!p || p.type === "group" || p.type === "mesh") return;
    await get().tool("add_part", { type: p.type, params: p.params, name: p.name + " copy",
      position: [p.position[0] + 15, p.position[1], p.position[2]], rotation: p.rotation, scale: p.scale, parent: p.parent });
  },

  async ask(text) {
    const before = clone(get().state.parts);
    set((s) => ({ chat: [...s.chat, { role: "user", text }], busy: { ...s.busy, chat: true } }));
    try {
      const j = await api("/api/chat", { text });
      if (JSON.stringify(before) !== JSON.stringify(j.state.parts))
        set((s) => ({ undo: [...s.undo, { parts: before, selected: null }], redo: [] }));
      get().applyState(j.state);
      const KEYS = { make_hologram: ["hologram"], propagate: ["reconstruction"], focus_sweep: ["sweep"], eye_view: ["eye"],
        speckle_compare: ["speckle_one", "speckle_random", "speckle_groups"], export_film: ["predicted_wall", "film_tile"] };
      for (const t of j.trace) {
        const im = {};
        for (const k of KEYS[t.tool] || []) if (j.images[k]) im[k] = j.images[k];
        get().ingest(t.tool, { ...t.result, _images: im });
      }
      set((s) => ({ chat: [...s.chat, { role: "steps", trace: j.trace }, { role: "ai", text: j.reply }] }));
    } catch (e) {
      set((s) => ({ chat: [...s.chat, { role: "error", text: e.message }] }));
    } finally {
      set((s) => ({ busy: { ...s.busy, chat: false } }));
    }
  },
}));

export const selectedPart = (s) => s.state?.parts.find((p) => p.id === s.state.selected) || null;
