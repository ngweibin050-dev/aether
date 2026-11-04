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
  modalStale: false,           // Modal runs an older engine than this computer: the server is redeploying it

  // ---- ui state ----
  mode: "laptop",            // laptop | hand
  activeTool: "select",          // toolbar: select | cursor | move | rotate | scale | measure
  axis: null,
  selection: [],             // multi-selection; the active part is state.selected
  // solid by default (on demand rendering, smooth on integrated GPUs); the hologram look animates every frame
  shading: (() => { try { return localStorage.getItem("aether.shading") || "solid"; } catch { return "solid"; } })(),           // wire | solid | holo
  view: { ...DEFAULT_VIEW }, // local copy of state.view so sliders feel instant
  cursor3d: [0, 0, 60],
  measure: null,             // { a, b }
  menu: null,                // { kind, x, y }
  modal: null,               // live G/R/S readout
  dock: null,                // open dock popover: section | explode
  panels: { orchestrator: true, outliner: true, physics: true, toolbar: true, cad: false, asm: false, drawing: false, optics: false, explain: false, history: false },
  win: { orchestrator: "normal", outliner: "normal", physics: "normal", cad: "normal", asm: "normal", drawing: "normal", optics: "normal", explain: "normal" },   // normal | min | max
  dockBar: false,            // the tool strip (hologram, section, explode…) is in Tools; this shows it as a bar too
  outlinerTab: "outliner",
  busy: {},
  timing: {},
  toast: null,
  results: { hologram: null, recon: null, sweep: null, eye: null, desk: null, window: null, hand: null,
             speckle: null, search: null, film: null },
  chat: [],
  lightbox: null,            // { src, title }: a picture opened big (double-click any image)
  preview: null,             // { name, url, ... }: a file opened in the preview (3D viewer, PDF, ...)
  openLightbox: (lb) => set({ lightbox: lb }),
  // the project's undo history lives on the server (history.py): one history for the assistant's turns, edits here
  // and background builds; undo / redo reverse only the parts a step changed. undo / redo: its steps, newest first
  undo: [], redo: [], history: { steps: [], redo: [] },
  handFrame: null,
  handCursor: null,          // { x, y, down } air cursor in hand mode

  setPanel: (k, v) => set((s) => {
    const on = v ?? !s.panels[k];
    return { panels: { ...s.panels, [k]: on }, ...(on && s.win[k] === "min" ? { win: { ...s.win, [k]: "normal" } } : {}) };
  }),
  // one panel can be maximised at a time; maximising one restores any other maximised one
  setWin: (k, v) => set((s) => {
    const win = { ...s.win };
    if (v === "max") for (const o in win) if (win[o] === "max") win[o] = "normal";
    win[k] = v;
    return { win, panels: { ...s.panels, [k]: true } };
  }),
  setDockBar: (v) => set((s) => ({ dockBar: v ?? !s.dockBar })),
  // floating panels: where the user put each one (remembered in this browser); none = docked by the layout
  rects: (() => { try { return JSON.parse(localStorage.getItem("aether.layout.v1") || "{}"); } catch { return {}; } })(),
  setRect: (id, r) => set((s) => {
    const rects = { ...s.rects };
    if (r) rects[id] = r; else delete rects[id];
    try { localStorage.setItem("aether.layout.v1", JSON.stringify(rects)); } catch { /* private mode */ }
    return { rects };
  }),
  // workspaces: which panels are shown for a kind of work; every panel goes back to its docked place
  workspace(name) {
    const W = {
      build: { panels: { orchestrator: true, outliner: true, physics: true, cad: false, asm: false, drawing: false, optics: false }, dock: false },
      inspect: { panels: { orchestrator: true, outliner: true, physics: false, cad: false, asm: true, drawing: false, optics: false }, min: ["orchestrator"] },
      present: { panels: { orchestrator: true, outliner: false, physics: false, cad: false, asm: false, drawing: false, optics: false }, min: ["orchestrator"] },
    }[name];
    if (!W) return;
    const win = Object.fromEntries(Object.keys(get().win).map((k) => [k, (W.min || []).includes(k) ? "min" : "normal"]));
    try { localStorage.removeItem("aether.layout.v1"); } catch { /* private mode */ }
    set({ panels: { ...get().panels, ...W.panels }, win, rects: {}, dockBar: false });
  },
  resetLayout() { get().workspace("build"); },
  setMode: (mode) => set({ mode, menu: null }),
  setTool: (t) => set({ activeTool: t, measure: t === "measure" ? get().measure : null }),
  setAxis: (axis) => set({ axis }),
  setShading: (shading) => { try { localStorage.setItem("aether.shading", shading); } catch { /* private mode */ } set({ shading }); },
  setMenu: (menu) => set({ menu }),
  setDock: (dock) => set((s) => ({ dock: s.dock === dock ? null : dock })),
  setHandFrame: (handFrame) => set({ handFrame }),
  notify: (text, kind = "info") => {
    set({ toast: { text, kind, t: Date.now() } });
    setTimeout(() => get().toast?.text === text && set({ toast: null }), 3500);
  },

  async load() {
    const j = await api("/api/state");
    set({ state: j.state, compute: j.compute, backend: j.gpu?.backend || null, modalStale: !!j.gpu?.stale, view: { ...DEFAULT_VIEW, ...(j.state.view || {}) },
          selection: j.state.selected ? [j.state.selected] : [] });
    await get().syncMeshes();
    get().loadProject();
    fetch("/api/demos").then((r) => r.json()).then((d) => set({ demos: d.demos || [] })).catch(() => {});
    fetch("/api/warm", { method: "POST", body: "{}" }).catch(() => {});   // the GPU container starts while the lab opens
  },

  async syncMeshes() {
    const s = get().state;
    if (!s || s.version === get().meshVersion) return;
    const j = await api("/api/meshes");
    // keep the old object for an unchanged mesh, so its GPU geometry is reused instead of rebuilt (and leaked)
    const old = get().meshes, same = (a, b) => a && b && a.v.length === b.v.length && a.f.length === b.f.length &&
      (a.l?.length || 0) === (b.l?.length || 0) && [0, 1, 7, a.v.length >> 1, a.v.length - 1].every((i) => a.v[i] === b.v[i]);
    const meshes = Object.fromEntries(Object.entries(j.meshes).map(([id, m]) => [id, same(old[id], m) ? old[id] : m]));
    set({ meshes, offsets: j.offsets || {}, meshVersion: j.version, brepIds: j.brep || [] });
    if (get().asm || (j.brep || []).length) get().loadAsm();
  },

  setChat(chat) { set({ chat: chat || [] }); },
  async loadHistory() {
    const h = await fetch("/api/history").then((r) => r.json()).catch(() => null);
    if (h) set({ history: h, undo: h.steps.filter((x) => x.source !== "auto"), redo: h.redo });
  },
  applyState(state) {
    if (state.version !== get().state?.version) get().loadHistory();
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
    const t0 = performance.now();
    set((s) => ({ busy: { ...s.busy, [name]: true } }));
    try {
      const j = await api("/api/tool", { name, args, ...(record ? {} : { label: null }) });
      get().applyState(j.state);
      get().ingest(name, j.result);
      if (j.result?._backend) set({ backend: j.result._backend });
      if (j.gpu) set({ modalStale: !!j.gpu.stale });
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
    if ((name === "read_views" || name === "sam_3_1" || name === "build_assembly") && !r.error)
      for (const k of ["hologram", "recon", "sweep", "eye", "wave", "desk", "score", "window", "hand", "speckle"]) delete res[k];   // a new design: old measurements no longer apply
    if (im.hologram) res.hologram = { img: im.hologram, info: r };
    if (im.reconstruction) res.recon = { img: im.reconstruction, z: r.z_mm };
    if (im.sweep && r.depths_mm) {
      if (res.eye) res.eye = { ...res.eye, latest: false };
      res.sweep = { imgs: im.sweep, depths: r.depths_mm, sharp: r.share_sharp_pct.map((v) => v ?? 0), sharpRaw: r.share_sharp_pct, display: r.display, lasers: r.lasers_nm, speckle: r.speckle_contrast_pct, outside: r.parts_outside_window_pct, inFocus: r.in_focus_area_pct, i: Math.floor(im.sweep.length / 2) };
    }
    if (im.eye) res.eye = { img: im.eye, info: r, latest: true };
    if (name === "desk_wave_view" && im.wave) res.wave = { wave: im.wave, model: im.eye_model, info: r };
    if (name === "desk_check" && r.rows) res.desk = r;
    if (name === "desk_score" && r.rows) res.score = r;
    if (name === "build_assembly" || name === "sam_3_1" || name === "read_views") res.opt = null;   // a new design: the old before/after no longer applies
    if (name === "optimize_for_desk" && r.rounds) res.opt = { ...r, before_img: im.opt_before, after_img: im.opt_after };
    if ((name === "sam_3_1" || name === "read_views") && !r.error) res.sam = { ...r, overlay: im.sam_overlay, cutout: im.sam_cutout, checkImg: im.sam_check };
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
  async pushParts(parts, selected, label) {
    const j = await api("/api/scene", { parts, selected, label });
    get().applyState(j.state);
  },
  // one edit of the scene = one step of the project's history (label: what the History panel and "undo" say)
  async commitParts(parts, selected = get().state.selected, label = "edit in the app") {
    set((s) => ({ state: { ...s.state, parts, selected } }));      // optimistic: no jump back while the server answers
    await get().pushParts(parts, selected, label);
  },
  async editSelected(fn, label = "edit") {
    const sel = new Set(get().selection);
    if (!sel.size) return;
    await get().commitParts(clone(get().state.parts).map((p) => (sel.has(p.id) ? fn(p) ?? p : p)), undefined, label);
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
    const names = parts.filter((p) => sel.has(p.id)).map((p) => p.name);
    await get().commitParts(parts.filter((p) => !drop.has(p.id)), null,
      `delete ${names.slice(0, 3).join(", ")}${names.length > 3 ? ` (+${names.length - 3})` : ""}`);
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
    await get().commitParts(parts, ids[ids.length - 1], `duplicate ${sel.map((p) => p.name).slice(0, 3).join(", ")}`);
    get().selectMany(ids);
    return ids;
  },
  async setVisible(ids, visible) {
    const on = new Set(ids);
    await get().commitParts(get().state.parts.map((p) => (on.has(p.id) ? { ...p, visible } : p)), undefined, visible ? "show" : "hide");
  },
  async parentTo(childIds, parentId) {
    const kids = new Set(childIds);
    await get().commitParts(get().state.parts.map((p) => (kids.has(p.id) && p.id !== parentId ? { ...p, parent: parentId } : p)), undefined, "parent");
  },

  // Ctrl+Z / Ctrl+Shift+Z / the History panel: the server's history (only the parts of that step go back)
  async undoOnce(id) {
    if (get().busy.history) return;
    set((s) => ({ busy: { ...s.busy, history: true } }));
    try {
      const j = await api("/api/history/undo", id ? { id } : {});
      get().applyState(j.state);
      const r = j.result;
      get().notify(r.undone ? `Undone: ${r.reverted} (${r.what})${r.also_undone?.length ? ` + ${r.also_undone.length} step(s) built on it` : ""}` : r.why,
        r.undone ? "info" : "error");
    } catch (e) { get().notify(e.message, "error"); }
    set((s) => ({ busy: { ...s.busy, history: false } }));
  },
  async redoOnce() {
    if (get().busy.history) return;
    set((s) => ({ busy: { ...s.busy, history: true } }));
    try {
      const j = await api("/api/history/redo", {});
      get().applyState(j.state);
      get().notify(j.result.redone ? `Redone: ${j.result.step} (${j.result.what})` : j.result.why, j.result.redone ? "info" : "error");
    } catch (e) { get().notify(e.message, "error"); }
    set((s) => ({ busy: { ...s.busy, history: false } }));
  },

  // ---- see inside: local first, then the server (debounced), so the hologram uses the same view ----
  // ---- sync with the server: background jobs (CAD details) and the scene version (another tab, a finished job) ----
  jobs: {},
  async pollJobs() {
    const j = await fetch("/api/jobs").then((r) => r.json()).catch(() => null);
    if (!j) return;
    const prev = get().jobs || {};
    set({ jobs: j.jobs || {} });
    // a background job that just finished (a CAD model built while the user kept working): its message into the chat,
    // and the new model framed
    for (const [id, job] of Object.entries(j.jobs || {})) {
      if (job.message && prev[id] && prev[id].state === "running" && job.state !== "running") {
        set((x) => ({ chat: [...x.chat, job.message] }));
        if (job.state === "done") setTimeout(() => import("./commands").then((m) => m.run("view.all")), 1200);
      }
    }
    const s = get();
    if (s.project && j.project && j.project !== s.project.slug && !s.busy.chat) return s.loadProject().then(() => s.load());
    if (j.version != null && s.state && j.version > s.state.version && !s.busy.asm && !s.modal) {
      const st = await api("/api/state").catch(() => null);
      if (st) get().applyState(st.state);
    }
  },

  // ---- projects (projects.py): the open project, saved automatically on the server ----
  project: null,               // { slug, name, saved }
  async loadProject() {
    const j = await api("/api/project").catch(() => null);
    if (j) set({ project: { slug: j.slug, name: j.name, saved: j.saved }, chat: j.chat || [] });
  },
  _enter(j) {
    set({ selection: [], explain: null, asm: null, caps: {}, results: { ...get().results, sam: null, sweep: null, score: null } });
    get().applyState(j.state);
    get().loadProject();
    setTimeout(() => import("./commands").then((m) => m.run("view.all")), 400);
  },
  async newProject(name) { const j = await api("/api/projects/new", { name }); get()._enter(j); get().notify(`New project: ${j.name}`); },
  async openProject(slug) { const j = await api("/api/projects/open", { slug }); get()._enter(j); get().notify(`Opened ${j.name}`); },
  async renameProject(name) { await api("/api/projects/rename", { name }); get().loadProject(); },
  async restoreVersion(n) {
    const j = await api("/api/projects/restore", { n });
    get().applyState(j.state);
    get().notify(`Restored version ${n} (the scene before it was saved as a version)`);
  },

  // ---- B-rep assembly of the machine (cad/assembly.py in the CAD worker) ----
  asm: null,                   // report: summary, groups, records (per part), mates, contact pairs, STEP result
  brepIds: [],                 // parts whose viewport mesh is the tessellated B-rep solid
  caps: {},                    // true section faces per part (part frame), from the B-rep Boolean section
  async loadAsm() {
    const j = await api("/api/asm/report").catch(() => null);
    set({ asm: j?.built ? j : null });
    return j;
  },
  async buildAsm() {
    set((s) => ({ busy: { ...s.busy, asm: true } }));
    try {
      const j = await api("/api/asm/build", {});
      const { state, ...rep } = j;
      set({ asm: rep });
      get().applyState(state);
      const m = rep.summary;
      get().notify(`B-rep assembly: ${m.valid_solids}/${m.built} solids valid · ${m.mates_satisfied}/${m.mates} mates satisfied · ${m.interferences} interference(s) · ${m.seconds.total} s`);
      get().fetchCaps();
    } catch (e) { get().notify(e.message, "error"); }
    set((s) => ({ busy: { ...s.busy, asm: false } }));
  },
  async exportStep() {
    set((s) => ({ busy: { ...s.busy, step: true } }));
    try {
      const j = await api("/api/asm/step", {});
      set((s) => ({ asm: { ...s.asm, step: j.step } }));
      get().notify(`STEP written: ${j.step.parts} solids in ${j.step.write_seconds} s · re-reading it in a fresh process to verify…`);
      const poll = async () => {                        // the round trip runs in the background; follow it
        const a = await get().loadAsm();
        const st = a?.step;
        if (st?.roundtrip === "running") return setTimeout(poll, 4000);
        if (st) get().notify(`STEP round trip ${st.roundtrip_all_pass ? "PASS" : "FAIL"}: ${st.parts} solids re-read and compared (${st.seconds ?? "-"} s)`,
          st.roundtrip_all_pass ? "info" : "error");
      };
      setTimeout(poll, 4000);
    } catch (e) { get().notify(e.message, "error"); }
    set((s) => ({ busy: { ...s.busy, step: false } }));
  },
  async fetchCaps() {
    const v = get().view, a = get().asm;
    if (!v.section || !a || a.stale) return set({ caps: {} });
    const key = `${v.section}${v.section_mm}${v.section_flip}`;
    get()._capKey = key;
    try {
      const j = await api("/api/asm/section", { axis: v.section, offset: v.section_mm, flip: v.section_flip });
      if (get()._capKey === key) set({ caps: j.parts });
    } catch { set({ caps: {} }); }
  },

  setView(patch, { now = false } = {}) {
    set({ view: { ...get().view, ...patch } });
    if (["section", "section_mm", "section_flip"].some((k) => k in patch)) {
      clearTimeout(get()._capTimer);
      set({ _capTimer: setTimeout(() => get().fetchCaps(), 180) });
    }
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
    set((s) => ({ chat: [...s.chat, userMsg], busy: { ...s.busy, chat: true }, progress: [] }));
    // the server's clock offset lets each running step show its own seconds without trusting this computer's clock
    const poll = setInterval(() => fetch("/api/progress").then((r) => r.json())
      .then((p) => set({ progress: p.steps || [], progressSkew: p.now ? Date.now() / 1000 - p.now : 0 })).catch(() => {}), 600);
    try {
      const j = await api(path, body);
      get().applyState(j.state);
      set({ view: { ...DEFAULT_VIEW, ...(j.state.view || {}) } });
      get().ingestTrace(j.trace, j.images);
      if (j.gpu) set({ modalStale: !!j.gpu.stale });
      if (j.trace.some((t) => t.tool === "optimize_for_desk" || t.tool === "sam_3_1" || t.tool === "read_views")) get().setPanel("physics", true);
      // a new or removed model (from a drawing, a photo or the assistant): bring all of it into view
      if (j.trace.some((t) => t.tool === "read_views" || t.tool === "sam_3_1")
          || (j.extras?.changes || []).some((c) => /^(Added|Removed)/.test(c) && !/ to (?!the desk)/.test(c))) {
        // frame it once its geometry has arrived (a big model takes a moment), inside the area the panels leave free
        const t0 = Date.now();
        const go = () => (get().meshVersion === get().state?.version || Date.now() - t0 > 8000)
          ? setTimeout(() => import("./commands").then((m) => m.run("view.all")), 150) : setTimeout(go, 150);
        go();
      }
      const x = j.extras || {};
      if (x.explain) { set({ explain: x.explain, explainStep: 0 }); get().setPanel("explain", true); }   // "explain / teach me": the panel opens
      const PANEL = { assembly: "asm", drawing: "drawing", optics: "optics", cad: "cad", physics: "physics" };
      for (const u of x.ui || []) if (u.open_panel && PANEL[u.open_panel]) get().setPanel(PANEL[u.open_panel], true);
      set((s) => ({ chat: [...s.chat, ...(j.trace?.length ? [{ role: "steps", trace: j.trace }] : []),
        ...(j.reply || x.question ? [{ role: "ai", text: j.reply, extras: x, img: j.images?.drawing }] : [])] }));
    } catch (e) {
      set((s) => ({ chat: [...s.chat, { role: "error", text: e.message }] }));
    } finally {
      clearInterval(poll);
      // the finished turn's steps stay in the chat (who did what, seconds)
      const done = (get().progress || []).filter((x) => x.s != null);
      set((s) => ({ busy: { ...s.busy, chat: false }, chat: done.length ? [...s.chat, { role: "timeline", steps: done }] : s.chat }));
    }
  },
  // "undo this" on an assistant message: back to the scene before THAT turn (saved with the project, so it works
  // after a restart), without asking Muse Spark
  async undoTurn(id) {
    const j = await api("/api/undo", { id });
    if (j.state) get().applyState(j.state);
    const r = j.result || {};
    set((s) => ({ chat: [...s.chat, { role: "ai", text: r.undone
      ? `Undone: ${r.reverted} (${r.what}).${r.also_undone?.length ? ` Also undone, because they built on it: ${r.also_undone.join("; ")}.` : ""}`
      : `Could not undo: ${r.why}` }] }));
  },
  // one message to the assistant, with the files attached to it (uploaded first: /api/files)
  ask(text, files = []) {
    return get().turn("/api/chat", { text, attachments: files.map((f) => f.name) }, { role: "user", text, files });
  },
  async upload(file) {
    const r = await fetch("/api/files", { method: "POST", headers: { "X-Filename": encodeURIComponent(file.name) }, body: file });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  },
  // Explain this machine: Muse Spark's step-by-step explanation of the built model (explain.py) + one Muse Image
  // illustration; the step player (ui/ExplainPlayer.jsx) highlights each step's parts
  explain: null,               // { machine, steps, rejected_steps, timing, illustration, ... }
  explainStep: 0,
  async runExplain(demo_id = null) {
    if (get().busy.explain) return;
    set((s) => ({ busy: { ...s.busy, explain: true }, progress: [], explain: null }));
    get().setPanel("explain", true);
    const poll = setInterval(() => fetch("/api/progress").then((r) => r.json())
      .then((p) => set({ progress: p.steps || [], progressSkew: p.now ? Date.now() / 1000 - p.now : 0 })).catch(() => {}), 600);
    try {
      const r = await fetch("/api/explain", { method: "POST", body: JSON.stringify(demo_id ? { demo_id } : {}) });
      const j = await r.json();
      if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
      set({ explain: j, explainStep: 0 });
      get().setPanel("explain", true);
      const done = (get().progress || []).filter((x) => x.s != null);
      if (done.length) set((s) => ({ chat: [...s.chat, { role: "timeline", steps: done }] }));
    } catch (e) {
      get().notify(`Explain failed: ${e.message}`, "error");
    } finally {
      clearInterval(poll);
      set((s) => ({ busy: { ...s.busy, explain: false } }));
    }
  },
  setExplainStep(i) { set({ explainStep: i }); },
  closeExplain() {
    set({ explain: null, explainStep: 0 });
    get().setPanel("explain", false);
    get().setView({ xray: false, explode: 0, section: null }, { now: true });
    get().select(null);
  },
  askPhoto(image, prompt, size_mm, mode = "interpret", kind = "auto", demo_id = null) {
    const what = { auto: "image → 3D (AETHER decides what it is)", machine: `machine drawing → ${mode === "trace" ? "SAM 3.1 traces each part" : "read like an engineer"} → 3D assembly`,
      three_view: "three-view sheet → 3D model from named parts", part: "photo of one part → SAM 3.1 → model" }[kind];
    set({ recorded: null });
    return get().turn("/api/photo", { image, prompt, size_mm, mode, kind, ...(demo_id ? { demo_id } : {}) }, { role: "user", img: image,
      text: `${prompt ? prompt + ": " : ""}${what} (${size_mm} mm, assumed unless a dimension is read)` });
  },
  // Demo menu: the three public-domain inputs, run LIVE (a machine is then explained); the last successful live run of
  // each is kept by the server and can be shown only as a RECORDED run (banner + chat label), never as live
  demos: [],
  recorded: null,              // { id, title, at } while a recorded run is on screen
  async runDemo(id) {
    const d = get().demos.find((x) => x.id === id);
    if (!d || get().busy.chat) return;
    fetch("/api/warm", { method: "POST", body: "{}" }).catch(() => {});
    const blob = await (await fetch(d.image)).blob();
    const image = await new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(r.result); r.readAsDataURL(blob); });
    await get().askPhoto(image, d.kind === "three_view" ? d.title : "", d.size_mm, "interpret", d.kind, id);
    if (d.kind === "machine" && get().chat.slice(-1)[0]?.role !== "error") {
      const t0 = Date.now();                       // let the model's geometry arrive, then explain it
      while (get().meshVersion !== get().state?.version && Date.now() - t0 < 8000) await new Promise((r) => setTimeout(r, 200));
      await get().runExplain(id);
    }
  },
  // a run's tool results and images into the panels (live turns and recorded runs alike)
  ingestTrace(trace, images) {
    const KEYS = { make_hologram: ["hologram", "reconstruction"], propagate: ["reconstruction"], focus_sweep: ["sweep"], eye_view: ["eye"],
      speckle_compare: ["speckle_one", "speckle_random", "speckle_groups"], export_film: ["predicted_wall", "film_tile"],
      optimize_for_desk: ["opt_before", "opt_after"], sam_3_1: ["sam_overlay", "sam_cutout", "sam_check"], read_views: ["sam_check"] };
    for (const t of trace || []) {
      const im = {};
      for (const k of KEYS[t.tool] || []) if (images?.[k]) im[k] = images[k];
      get().ingest(t.tool, { ...t.result, _images: im });
    }
  },
  async playRecorded(id) {
    const r = await fetch(`/api/demo/recorded?id=${id}`);
    const j = await r.json();
    if (!r.ok) return get().notify(j.error || "no recorded run", "error");
    const d = get().demos.find((x) => x.id === id) || { title: id };
    set({ state: j.state, selection: [], recorded: { id, title: d.title, at: j.recorded_at }, explain: null,
          chat: [...get().chat, { role: "ai", text: `RECORDED run of ${d.title} from ${j.recorded_at}: not live. ${j.reply || ""}`.trim() },
                 ...(j.steps?.length ? [{ role: "timeline", steps: j.steps.filter((x) => x.s != null) }] : [])] });
    await get().syncMeshes();
    get().ingestTrace(j.trace, j.images);              // the panels show the recorded run's results, under the banner
    if (j.explain) set({ explain: { ...j.explain, recorded_at: j.recorded_at }, explainStep: 0 });
    import("./commands").then((m) => m.run("view.all"));
  },
  optimize(target_pct = 80) {
    return get().turn("/api/optimize", { target_pct, max_rounds: 3 }, { role: "user", text: `Make it sharp on the AETHER Desk (≥${target_pct}%)` });
  },
}));

export const selectedPart = (s) => s.state?.parts.find((p) => p.id === s.state.selected) || null;
export const HEAVY = ["desk_score", "make_hologram", "propagate", "focus_sweep", "eye_view", "desk_check", "search_column_width", "speckle_compare", "export_film"];
export const isBusy = (s) => HEAVY.some((k) => s.busy[k]) || s.busy.chat;
