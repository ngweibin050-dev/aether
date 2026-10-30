import { create } from "zustand";
import { api } from "./api";

const clone = (x) => JSON.parse(JSON.stringify(x));
export const DEFAULT_VIEW = { explode: 0, section: null, section_mm: 0, section_flip: false, isolate: [], xray: false };
let viewTimer = 0;

export const useStore = create((set, get) => ({
  // ---- server state (single source of truth, shared by laptop mode, hand mode and the AI) ----
  state: null,
  meshes: {},
  offsets: {},               // explode offsets at explode = 1, per part (parent frame)
  meshVersion: -1,
  compute: "local",
  backend: null,               // what the last heavy tool ran on, e.g. "cupy-gpu" on Modal

  // ---- ui state ----
  mode: "laptop",            // laptop | hand
  activeTool: "select",          // toolbar: select | cursor | move | rotate | scale | measure
  axis: null,
  selection: [],             // multi-selection; the active part is state.selected
  shading: "holo",           // wire | solid | holo
  view: { ...DEFAULT_VIEW }, // local copy of state.view so sliders feel instant
  cursor3d: [0, 0, 60],
  measure: null,             // { a, b }
  menu: null,                // { kind, x, y }
  modal: null,               // live G/R/S readout
  dock: null,                // open dock popover: section | explode
  panels: { orchestrator: true, outliner: true, physics: true, toolbar: true },
  outlinerTab: "outliner",
  busy: {},
  timing: {},
  toast: null,
  results: { hologram: null, recon: null, sweep: null, eye: null, desk: null, window: null, hand: null,
             speckle: null, search: null, film: null },
  chat: [],
  undo: [], redo: [],
  handFrame: null,
  handCursor: null,          // { x, y, down } air cursor in hand mode

  setPanel: (k, v) => set((s) => ({ panels: { ...s.panels, [k]: v ?? !s.panels[k] } })),
  setMode: (mode) => set({ mode, menu: null }),
  setTool: (t) => set({ activeTool: t, measure: t === "measure" ? get().measure : null }),
  setAxis: (axis) => set({ axis }),
  setShading: (shading) => set({ shading }),
  setMenu: (menu) => set({ menu }),
  setDock: (dock) => set((s) => ({ dock: s.dock === dock ? null : dock })),
  setHandFrame: (handFrame) => set({ handFrame }),
  notify: (text, kind = "info") => {
    set({ toast: { text, kind, t: Date.now() } });
    setTimeout(() => get().toast?.text === text && set({ toast: null }), 3500);
  },

  async load() {
    const j = await api("/api/state");
    set({ state: j.state, compute: j.compute, backend: j.gpu?.backend || null, view: { ...DEFAULT_VIEW, ...(j.state.view || {}) },
          selection: j.state.selected ? [j.state.selected] : [] });
    await get().syncMeshes();
  },

  async syncMeshes() {
    const s = get().state;
    if (!s || s.version === get().meshVersion) return;
    const j = await api("/api/meshes");
    set({ meshes: j.meshes, offsets: j.offsets || {}, meshVersion: j.version });
  },

  applyState(state) {
    const ids = new Set(state.parts.map((p) => p.id));
    set((s) => ({
      state,
      view: viewTimer ? s.view : { ...DEFAULT_VIEW, ...(state.view || {}) },
      selection: state.selected && !s.selection.includes(state.selected)
        ? [state.selected] : s.selection.filter((id) => ids.has(id)),
    }));
    get().syncMeshes();
  },

  // ---- tools (same names the AI agent uses) ----
  async tool(name, args = {}, { record = true, quiet = false } = {}) {
    const before = get().state && clone(get().state.parts);
    const t0 = performance.now();
    set((s) => ({ busy: { ...s.busy, [name]: true } }));
    try {
      const j = await api("/api/tool", { name, args });
      if (record && before && JSON.stringify(before) !== JSON.stringify(j.state.parts))
        set((s) => ({ undo: [...s.undo.slice(-49), { parts: before, selected: s.state.selected }], redo: [] }));
      get().applyState(j.state);
      get().ingest(name, j.result);
      if (j.result?._backend) set({ backend: j.result._backend });
      set((s) => ({ timing: { ...s.timing, [name]: Math.round(performance.now() - t0), last: name } }));
      if (j.result?.error && !quiet) get().notify(j.result.error, "error");
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
    if (im.sweep && r.depths_mm) {
      if (res.eye) res.eye = { ...res.eye, latest: false };
      res.sweep = { imgs: im.sweep, depths: r.depths_mm, sharp: r.share_sharp_pct, display: r.display, lasers: r.lasers_nm, speckle: r.speckle_contrast_pct, outside: r.parts_outside_window_pct, i: Math.floor(im.sweep.length / 2) };
    }
    if (im.eye) res.eye = { img: im.eye, info: r, latest: true };
    if (name === "desk_wave_view" && im.wave) res.wave = { wave: im.wave, model: im.eye_model, info: r };
    if (name === "desk_check" && r.rows) res.desk = r;
    if (name === "desk_score" && r.rows) res.score = r;
    if (name === "build_assembly" || name === "sam_3_1") res.opt = null;   // a new design: the old before/after no longer applies
    if (name === "optimize_for_desk" && r.rounds) res.opt = { ...r, before_img: im.opt_before, after_img: im.opt_after };
    if (name === "sam_3_1" && !r.error) res.sam = { ...r, overlay: im.sam_overlay, cutout: im.sam_cutout };
    if (name === "window_check" && r.parts) res.window = r;
    if (name === "hand_check") res.hand = r;
    if (im.speckle_one) res.speckle = { ...r, imgs: im };
    if (name === "speckle_compare" && !im.speckle_one && r.one_frame !== undefined) res.speckle = { ...(res.speckle || {}), ...r };
    if (name === "search_column_width" && r.tried) res.search = r;
    if (name === "export_film" && r.path) res.film = { ...r, imgs: im };
    if (name === "set_view" && r.view && !viewTimer) set({ view: { ...DEFAULT_VIEW, ...r.view } });
    set({ results: res });
  },

  // what the viewer's eye sees comes first (fast, recognisable); the lab phase hologram after
  eyeDisplay: "desk1d",
  eyeColor: true,              // R/G/B lasers (full colour) or one 530 nm laser
  eyeArgs() { return { display: get().eyeDisplay, color: get().eyeColor }; },
  setEyeDisplay(d) { set({ eyeDisplay: d }); if (get().results.sweep) get().tool("focus_sweep", { steps: 7, ...get().eyeArgs() }); },
  setEyeColor(c) { set({ eyeColor: c }); if (get().results.sweep) get().tool("focus_sweep", { steps: 7, ...get().eyeArgs() }); },
  eyeView(extra = {}) {
    const sw = get().results.sweep;
    return get().tool("eye_view", { ...get().eyeArgs(), ...(sw ? { focus_z_mm: sw.depths[sw.i] } : {}), ...extra });
  },
  async hologram() {
    // progressive: one focus first (seconds), then the whole sweep, then the lab phase hologram
    const first = await get().tool("eye_view", get().eyeArgs());
    if (first?.error) return;
    await get().tool("focus_sweep", { steps: 7, ...get().eyeArgs() });
    await get().tool("make_hologram");
  },

  // ---- selection ----
  select(id, { extend = false } = {}) {
    const s = get().state;
    if (!s) return;
    let selection = get().selection;
    if (!id) selection = [];
    else if (extend) selection = selection.includes(id) && s.selected === id ? selection.filter((x) => x !== id) : [...new Set([...selection, id])];
    else selection = [id];
    const active = selection.includes(id) ? id : selection[selection.length - 1] || null;
    set({ state: { ...s, selected: active }, selection });
  },
  selectMany(ids, extend = false) {
    const s = get().state;
    const selection = extend ? [...new Set([...get().selection, ...ids])] : ids;
    set({ state: { ...s, selected: selection[selection.length - 1] || null }, selection });
  },
  selectAll() { get().selectMany(get().state.parts.filter((p) => p.visible !== false).map((p) => p.id)); },
  invertSelection() { const sel = get().selection; get().selectMany(get().state.parts.filter((p) => !sel.includes(p.id)).map((p) => p.id)); },

  // ---- scene edits as one undo step ----
  async pushParts(parts, selected) {
    const j = await api("/api/scene", { parts, selected });
    get().applyState(j.state);
  },
  async commitParts(parts, selected = get().state.selected) {
    const before = clone(get().state.parts);
    set((s) => ({ undo: [...s.undo.slice(-49), { parts: before, selected: s.state.selected }], redo: [],
                  state: { ...s.state, parts, selected } }));      // optimistic: no jump back while the server answers
    await get().pushParts(parts, selected);
  },
  async editSelected(fn) {
    const sel = new Set(get().selection);
    if (!sel.size) return;
    await get().commitParts(clone(get().state.parts).map((p) => (sel.has(p.id) ? fn(p) ?? p : p)));
  },
  async commitTransform(id, t) {
    return get().tool("update_part", { id, ...t });
  },
  async deleteSelected() {
    const sel = new Set(get().selection);
    if (!sel.size) return;
    const parts = get().state.parts;
    const drop = new Set(sel);
    let grew = true;
    while (grew) { grew = false; for (const p of parts) if (drop.has(p.parent) && !drop.has(p.id)) { drop.add(p.id); grew = true; } }
    set({ selection: [] });
    await get().commitParts(parts.filter((p) => !drop.has(p.id)), null);
  },
  async duplicate() {
    const s = get().state;
    const sel = get().selection.map((id) => s.parts.find((p) => p.id === id)).filter(Boolean);
    if (!sel.length) return [];
    const parts = clone(s.parts), map = {};
    const rid = () => Math.random().toString(16).slice(2, 10);
    const copyTree = (p, parent) => {
      const n = { ...clone(p), id: rid(), name: p.name + ".001", parent };
      map[p.id] = n.id; parts.push(n);
      for (const k of s.parts.filter((q) => q.parent === p.id)) copyTree(k, n.id);
    };
    for (const p of sel) if (!sel.some((q) => q.id === p.parent)) copyTree(p, p.parent);
    const ids = sel.map((p) => map[p.id]).filter(Boolean);
    await get().commitParts(parts, ids[ids.length - 1]);
    get().selectMany(ids);
    return ids;
  },
  async setVisible(ids, visible) {
    const on = new Set(ids);
    await get().commitParts(get().state.parts.map((p) => (on.has(p.id) ? { ...p, visible } : p)));
  },
  async parentTo(childIds, parentId) {
    const kids = new Set(childIds);
    await get().commitParts(get().state.parts.map((p) => (kids.has(p.id) && p.id !== parentId ? { ...p, parent: parentId } : p)));
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

  // ---- see inside: local first, then the server (debounced), so the hologram uses the same view ----
  setView(patch, { now = false } = {}) {
    set({ view: { ...get().view, ...patch } });
    clearTimeout(viewTimer);
    const send = () => {
      viewTimer = 0;
      const v = get().view;
      get().tool("set_view", { ...v, section: v.section || "off" }, { record: false, quiet: true }).catch(() => {});
    };
    if (now) send(); else viewTimer = setTimeout(send, 250);
  },

  progress: [],                // live steps of the running Muse Spark turn
  // one Muse Spark turn (chat, photo -> SAM 3.1 -> model, or the closed design loop), with live steps
  async turn(path, body, userMsg) {
    const before = clone(get().state.parts);
    set((s) => ({ chat: [...s.chat, userMsg], busy: { ...s.busy, chat: true }, progress: [] }));
    const poll = setInterval(() => fetch("/api/progress").then((r) => r.json()).then((p) => set({ progress: p.steps || [] })).catch(() => {}), 600);
    try {
      const j = await api(path, body);
      if (JSON.stringify(before) !== JSON.stringify(j.state.parts))
        set((s) => ({ undo: [...s.undo, { parts: before, selected: null }], redo: [] }));
      get().applyState(j.state);
      set({ view: { ...DEFAULT_VIEW, ...(j.state.view || {}) } });
      const KEYS = { make_hologram: ["hologram", "reconstruction"], propagate: ["reconstruction"], focus_sweep: ["sweep"], eye_view: ["eye"],
        speckle_compare: ["speckle_one", "speckle_random", "speckle_groups"], export_film: ["predicted_wall", "film_tile"],
        optimize_for_desk: ["opt_before", "opt_after"], sam_3_1: ["sam_overlay", "sam_cutout"] };
      for (const t of j.trace) {
        const im = {};
        for (const k of KEYS[t.tool] || []) if (j.images[k]) im[k] = j.images[k];
        get().ingest(t.tool, { ...t.result, _images: im });
      }
      if (j.trace.some((t) => t.tool === "optimize_for_desk" || t.tool === "sam_3_1")) get().setPanel("physics", true);
      set((s) => ({ chat: [...s.chat, { role: "steps", trace: j.trace }, ...(j.reply ? [{ role: "ai", text: j.reply }] : [])] }));
    } catch (e) {
      set((s) => ({ chat: [...s.chat, { role: "error", text: e.message }] }));
    } finally {
      clearInterval(poll);
      set((s) => ({ busy: { ...s.busy, chat: false } }));
    }
  },
  ask(text) { return get().turn("/api/chat", { text }, { role: "user", text }); },
  askPhoto(image, prompt, size_mm) {
    const many = prompt.includes(",");
    return get().turn("/api/photo", { image, prompt, size_mm }, { role: "user", img: image,
      text: many ? `Drawing of a machine (${size_mm} mm wide): find ${prompt} → SAM 3.1 → assembly` : `Photo of a real ${prompt} (~${size_mm} mm) → SAM 3.1 → model` });
  },
  optimize(target_pct = 80) {
    return get().turn("/api/optimize", { target_pct, max_rounds: 3 }, { role: "user", text: `Make it sharp on the AETHER Desk (≥${target_pct}%)` });
  },
}));

export const selectedPart = (s) => s.state?.parts.find((p) => p.id === s.state.selected) || null;
export const HEAVY = ["desk_score", "make_hologram", "propagate", "focus_sweep", "eye_view", "desk_check", "search_column_width", "speckle_compare", "export_film"];
export const isBusy = (s) => HEAVY.some((k) => s.busy[k]) || s.busy.chat;
