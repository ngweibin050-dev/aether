// Every action in AETHER, in one list. Menus, the F3 search, keyboard shortcuts and the hand menu all use it,
// so laptop mode and hand mode can do exactly the same things.
import { useStore } from "./store";
import { objects, view } from "./scene/registry";
import { sceneBox } from "./scene/Viewport";
import { startModal } from "./scene/modal";

const S = () => useStore.getState();
const hasSel = () => S().selection.length > 0;
const one = () => S().state?.parts.find((p) => p.id === S().state.selected);

export const PRIMS = [
  ["gear", { teeth: 16, radius: 25, thickness: 8 }], ["cylinder", { radius: 12, height: 40 }],
  ["tube", { outer: 20, inner: 15, height: 30 }], ["box", { w: 40, d: 30, h: 20 }],
  ["cone", { r_bottom: 18, r_top: 4, height: 40 }], ["sphere", { radius: 18 }],
  ["torus", { radius: 22, tube_radius: 5 }], ["nozzle", { throat: 8, exit: 24, length: 45, chamber: 14, chamber_length: 25 }],
  ["coil", { radius: 16, wire: 1.5, turns: 6, pitch: 5 }], ["blade_ring", { count: 10, inner: 6, outer: 26, thickness: 1.5, height: 8, twist: 25 }],
];

export const addPrim = (type) => {
  const params = Object.fromEntries(PRIMS)[type];
  return S().tool("add_part", { type, params, name: type.replace("_", " "), position: S().cursor3d.map((v) => +v.toFixed(2)) });
};

const download = (url, name) => { const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); };
// the print film: made into the project's exports, then downloaded like any file (it is also in the project folder)
const filmDownload = () => S().tool("export_film").then((r) => {
  if (!r?.url) return;
  download(r.url, r.name);
  S().notify(`Print film downloaded: ${r.name} (${(r.bytes / 1024).toFixed(0)} KB, also in the project's exports)`);
});
const frameSel = () => view.nav?.frame(sceneBox(S().selection.length ? S().selection : null));
const eyeView = () => {
  const s = S().state, box = sceneBox();
  if (!box.isEmpty()) view.nav?.fromPoint(s.eye, box.getCenter(new (box.min.constructor)()));
};
const sectionOn = (axis) => {
  const box = sceneBox(), v = S().view;
  if (v.section === axis) return S().setView({ section: null }, { now: true });
  const k = { x: "x", y: "y", z: "z" }[axis];
  const mid = box.isEmpty() ? 0 : (box.min[k] + box.max[k]) / 2;
  S().setView({ section: axis, section_mm: +mid.toFixed(1) }, { now: true });
};
const isolate = () => {
  const v = S().view;
  S().setView({ isolate: v.isolate.length ? [] : S().selection }, { now: true });
  setTimeout(frameSel, 60);
};
const hideSel = () => hasSel() && S().setVisible(S().selection, false);
const unhideAll = () => S().setVisible(S().state.parts.filter((p) => p.visible === false).map((p) => p.id), true);
const hideOthers = () => S().setVisible(S().state.parts.filter((p) => !S().selection.includes(p.id)).map((p) => p.id), false);
const saveScene = () => {
  const blob = new Blob([JSON.stringify({ aether: "2.1", parts: S().state.parts, view: S().view }, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "aether_scene.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
const openScene = () => {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json";
  inp.onchange = async () => {
    try {
      const j = JSON.parse(await inp.files[0].text());
      await S().commitParts(j.parts, null);
      if (j.view) S().setView(j.view, { now: true });
    } catch (e) { S().notify("Open: " + e.message, "error"); }
  };
  inp.click();
};
export const importGLB = () => document.getElementById("glb-input")?.click();

export const COMMANDS = [
  // File
  { id: "file.new", menu: "File", group: "Project", label: "New empty scene", run: () => S().commitParts([], null, "new empty scene") },
  { id: "file.open", menu: "File", group: "Project", label: "Open scene…", keys: "Ctrl O", run: openScene },
  { id: "file.save", menu: "File", group: "Project", label: "Save scene", keys: "Ctrl S", run: saveScene },
  { id: "file.import", menu: "File", group: "Import", label: "Import glTF / GLB…", run: importGLB },
  { id: "file.glb", menu: "File", group: "Export", label: "Export GLB (metres, part records inside)", run: () => download("/api/export.glb", "aether-model.glb") },
  { id: "file.step", menu: "File", group: "Export", label: "Export STEP (CAD B-rep, from the CAD document)", run: () => download("/api/cad/export.step", "aether-model.step") },
  { id: "file.aethercad", menu: "File", group: "Export", label: "Export .aethercad (editable CAD document)", run: () => download("/api/cad/export.aethercad", "aether-model.aethercad") },
  { id: "view.cad", menu: "View", group: "Panels", label: "CAD document panel", run: () => S().setPanel("cad") },
  { id: "view.asm", menu: "View", group: "Panels", label: "B-rep assembly panel (tree, mates, checks, properties)", run: () => S().setPanel("asm") },
  { id: "view.drawing", menu: "View", group: "Panels", label: "Drawing reading panel (balloons)", run: () => S().setPanel("drawing") },
  { id: "view.optics", menu: "View", group: "Panels", label: "Optics figure (desk simulation results)", run: () => S().setPanel("optics") },
  { id: "cad.asm", menu: "Inspect", group: "Engineering", label: "Build B-rep assembly (exact solids, validation, mates)", run: () => { S().setPanel("asm", true); S().buildAsm(); } },
  { id: "file.asmstep", menu: "File", group: "Export", label: "Export STEP of the machine (B-rep assembly, validated)", run: () => { S().setPanel("asm", true); S().exportStep(); } },
  { id: "file.stl", menu: "File", group: "Export", label: "Export STL (millimetres)", run: () => download("/api/export.stl", "aether-model.stl") },
  { id: "file.report", menu: "File", group: "Export", label: "Build report (one page)", run: () => window.open("/api/report.html", "_blank") },
  { id: "file.film", menu: "File", group: "Export", label: "Export print film (2400 dpi)", run: filmDownload },
  // Edit
  { id: "edit.undo", menu: "Edit", label: "Undo", keys: "Ctrl Z", run: () => S().undoOnce() },
  { id: "edit.redo", menu: "Edit", label: "Redo", keys: "Ctrl ⇧ Z", run: () => S().redoOnce() },
  { id: "edit.history", menu: "Edit", label: "History…", keys: "Ctrl H", run: () => S().setPanel("history", !S().panels.history) },
  { id: "edit.search", menu: "Edit", label: "Menu search…", keys: "F3", run: () => S().setMenu({ kind: "search" }) },
  { id: "edit.rename", menu: "Edit", label: "Rename active", keys: "F2", when: () => !!one(), run: () => S().setMenu({ kind: "rename" }) },
  // Select
  { id: "sel.all", menu: "Select", label: "All", keys: "A", run: () => S().selectAll() },
  { id: "sel.none", menu: "Select", label: "None", keys: "Alt A", run: () => S().select(null) },
  { id: "sel.invert", menu: "Select", label: "Invert", keys: "Ctrl I", run: () => S().invertSelection() },
  { id: "sel.box", menu: "Select", label: "Box select", keys: "B / drag", run: () => S().setTool("select") },
  { id: "sel.parent", menu: "Select", label: "Parent assembly", keys: "Shift G", when: () => !!one()?.parent, run: () => S().select(one().parent) },
  { id: "sel.children", menu: "Select", label: "Children", keys: "Shift ]", when: hasSel, run: () => S().selectMany(S().state.parts.filter((p) => S().selection.includes(p.parent)).map((p) => p.id)) },
  // Add
  ...PRIMS.map(([t]) => ({ id: "add." + t, menu: "Add", label: t.replace("_", " "), group: "Mesh", run: () => addPrim(t) })),
  { id: "add.ai", menu: "Add", label: "Assembly from text (Muse Spark)…", group: "AI", run: () => document.getElementById("ai-input")?.focus() },
  { id: "add.photo", menu: "Add", label: "Model from a photo (SAM 3.1)…", group: "AI", run: () => document.getElementById("photo-input")?.click() },
  { id: "ai.fix", menu: "Add", label: "Fix design for the desk (AI loop)", group: "AI", run: () => S().optimize(80) },
  { id: "add.glb", menu: "Add", label: "Import GLB model…", group: "AI", run: importGLB },
  // Object · tools (they were a toolbar under the menu bar; W cycles them)
  { id: "tool.select", menu: "Object", group: "Tools", label: "Tool: Select / box select", keys: "B", run: () => S().setTool("select") },
  { id: "tool.cursor", menu: "Object", group: "Tools", label: "Tool: 3D cursor", run: () => S().setTool("cursor") },
  { id: "tool.move", menu: "Object", group: "Tools", label: "Tool: Move gizmo", run: () => S().setTool("move") },
  { id: "tool.rotate", menu: "Object", group: "Tools", label: "Tool: Rotate gizmo", run: () => S().setTool("rotate") },
  { id: "tool.scale", menu: "Object", group: "Tools", label: "Tool: Scale gizmo", run: () => S().setTool("scale") },
  { id: "tool.measure", menu: "Object", group: "Tools", label: "Tool: Measure (click two points)", run: () => S().setTool("measure") },
  // Object
  { id: "obj.move", menu: "Object", label: "Move", keys: "G", when: hasSel, run: () => startModal("G") },
  { id: "obj.rotate", menu: "Object", label: "Rotate", keys: "R", when: hasSel, run: () => startModal("R") },
  { id: "obj.scale", menu: "Object", label: "Scale", keys: "S", when: hasSel, run: () => startModal("S") },
  { id: "obj.dup", menu: "Object", label: "Duplicate", keys: "⇧ D", when: hasSel, run: async () => { await S().duplicate(); startModal("G"); } },
  { id: "obj.delete", menu: "Object", label: "Delete", keys: "X / Del", when: hasSel, run: () => S().deleteSelected() },
  { id: "obj.clearloc", menu: "Object", label: "Clear location", keys: "Alt G", when: hasSel, run: () => S().editSelected((p) => ({ ...p, position: [0, 0, p.parent ? 0 : 60] })) },
  { id: "obj.clearrot", menu: "Object", label: "Clear rotation", keys: "Alt R", when: hasSel, run: () => S().editSelected((p) => ({ ...p, rotation: [0, 0, 0] })) },
  { id: "obj.clearscale", menu: "Object", label: "Clear scale", keys: "Alt S", when: hasSel, run: () => S().editSelected((p) => ({ ...p, scale: [1, 1, 1] })) },
  { id: "obj.parent", menu: "Object", label: "Parent to active", keys: "Ctrl P", when: () => S().selection.length > 1, run: () => S().parentTo(S().selection, S().state.selected) },
  { id: "obj.unparent", menu: "Object", label: "Clear parent", keys: "Alt P", when: hasSel, run: () => S().editSelected((p) => ({ ...p, parent: null })) },
  { id: "obj.hide", menu: "Object", label: "Hide selected", keys: "H", when: hasSel, run: hideSel },
  { id: "obj.unhide", menu: "Object", label: "Reveal hidden", keys: "Alt H", run: unhideAll },
  { id: "obj.hideothers", menu: "Object", label: "Hide unselected", keys: "⇧ H", when: hasSel, run: hideOthers },
  { id: "obj.snapcursor", menu: "Object", label: "Snap cursor to selected", keys: "⇧ S", when: hasSel, run: () => { const b = sceneBox(S().selection); if (!b.isEmpty()) useStore.setState({ cursor3d: b.getCenter(b.min.clone()).toArray().map((v) => +v.toFixed(2)) }); } },
  { id: "obj.snapsel", menu: "Object", label: "Selection to cursor", when: hasSel, run: () => {
      const c = S().cursor3d;
      S().editSelected((p) => { const o = objects.get(p.id); if (!o?.parent) return p; const l = o.parent.worldToLocal(o.position.clone().set(...c)); return { ...p, position: l.toArray().map((v) => +v.toFixed(2)) }; });
    } },
  { id: "obj.cursorreset", menu: "Object", label: "Cursor to world origin", run: () => useStore.setState({ cursor3d: [0, 0, 60] }) },
  // View
  { id: "view.frame", menu: "View", group: "Camera", label: "Frame selected", keys: "Num .", run: frameSel },
  { id: "view.all", menu: "View", group: "Camera", label: "Frame all", keys: "Home", run: () => view.nav?.frame(sceneBox()) },
  { id: "view.desk", menu: "View", group: "Camera", label: "Back to the AETHER desk", keys: "Ctrl Home", run: () => view.nav?.home() },
  { id: "view.front", menu: "View", group: "Camera", label: "Front", keys: "Num 1", run: () => view.nav?.view("front") },
  { id: "view.back", menu: "View", group: "Camera", label: "Back", keys: "Ctrl Num 1", run: () => view.nav?.view("back") },
  { id: "view.right", menu: "View", group: "Camera", label: "Right", keys: "Num 3", run: () => view.nav?.view("right") },
  { id: "view.left", menu: "View", group: "Camera", label: "Left", keys: "Ctrl Num 3", run: () => view.nav?.view("left") },
  { id: "view.top", menu: "View", group: "Camera", label: "Top", keys: "Num 7", run: () => view.nav?.view("top") },
  { id: "view.bottom", menu: "View", group: "Camera", label: "Bottom", keys: "Ctrl Num 7", run: () => view.nav?.view("bottom") },
  { id: "view.eye", menu: "View", group: "Camera", label: "Viewer's eye (camera)", keys: "Num 0", run: eyeView },
  { id: "view.ortho", menu: "View", group: "Camera", label: "Perspective / Orthographic", keys: "Num 5", run: () => { view.nav.autoOrtho = false; view.nav?.setOrtho(!view.nav.isOrtho); } },
  { id: "view.wire", menu: "View", group: "Shading", label: "Shading: Wireframe", keys: "Z", run: () => S().setShading("wire") },
  { id: "view.solid", menu: "View", group: "Shading", label: "Shading: Solid", keys: "Z", run: () => S().setShading("solid") },
  { id: "view.holo", menu: "View", group: "Shading", label: "Shading: Hologram", keys: "Z", run: () => S().setShading("holo") },
  { id: "view.explain", menu: "View", group: "Panels", label: "Explain this machine panel", run: () => { S().setPanel("explain", true); S().setWin("explain", "normal"); } },
  { id: "view.sidebar", menu: "View", group: "Panels", label: "Sidebar (Item)", keys: "N", run: () => { S().setPanel("outliner", true); useStore.setState({ outlinerTab: "item" }); } },
  { id: "view.mode", menu: "View", group: "Mode", label: "Switch Laptop / Hand mode", keys: "Tab", run: () => S().setMode(S().mode === "laptop" ? "hand" : "laptop") },
  // Inspect (see inside)
  { id: "in.xray", menu: "Inspect", group: "Look inside", label: "X-ray", keys: "Alt Z", run: () => S().setView({ xray: !S().view.xray }, { now: true }) },
  { id: "in.secx", menu: "Inspect", group: "Look inside", label: "Section cut X", keys: "Alt X", run: () => sectionOn("x") },
  { id: "in.secy", menu: "Inspect", group: "Look inside", label: "Section cut Y", keys: "Alt Y", run: () => sectionOn("y") },
  { id: "in.secz", menu: "Inspect", group: "Look inside", label: "Section cut Z", run: () => sectionOn("z") },
  { id: "in.flip", menu: "Inspect", group: "Look inside", label: "Flip section side", when: () => !!S().view.section, run: () => S().setView({ section_flip: !S().view.section_flip }, { now: true }) },
  { id: "in.explode", menu: "Inspect", group: "Look inside", label: "Explode / assemble", keys: "E", run: () => { S().setView({ explode: S().view.explode > 0.5 ? 0 : 1 }, { now: true }); setTimeout(() => view.nav?.frame(sceneBox()), 700); } },
  { id: "in.isolate", menu: "Inspect", group: "Look inside", label: "Isolate selected (local view)", keys: "/", when: () => hasSel() || S().view.isolate.length, run: isolate },
  { id: "demo.warm", menu: "Demo", label: "Warm up the GPU (before a demo)", run: () => fetch("/api/warm", { method: "POST", body: "{}" }).then(() => S().notify("Modal GPU warming up (20-60 s)")) },
  { id: "demo.CAR", menu: "Demo", group: "Live", label: "CAR · Four-view car sheet → B-rep CAD (CC0)", run: () => S().runDemo("CAR") },
  { id: "demo.D", menu: "Demo", group: "Live", label: "D · Metal drawing press (US 929,594) → 3D → Explain", run: () => S().runDemo("D") },
  { id: "demo.C", menu: "Demo", group: "Live", label: "C · Speed-reduction gearbox (US 1,770,035) → 3D → Explain", run: () => S().runDemo("C") },
  { id: "demo.recCAR", menu: "Demo", group: "Recorded (fallback, labelled)", label: "Show recorded run: CAR (B-rep CAD)", run: () => S().playRecorded("CAR") },
  { id: "demo.recD", menu: "Demo", group: "Recorded (fallback, labelled)", label: "Show recorded run: D", run: () => S().playRecorded("D") },
  { id: "demo.recC", menu: "Demo", group: "Recorded (fallback, labelled)", label: "Show recorded run: C", run: () => S().playRecorded("C") },
  { id: "in.explainMachine", menu: "Inspect", group: "Engineering", label: "Explain this machine", run: () => S().runExplain() },
  { id: "obj.placeOnBase", menu: "Object", label: "Place on base", keys: "Shift B", run: () => S().tool("place_on_base", { id: S().state.selected }) },
  { id: "in.reset", menu: "Inspect", group: "Look inside", label: "Reset inspection", run: () => S().setView({ xray: false, section: null, explode: 0, isolate: [] }, { now: true }) },
  // Hologram
  { id: "holo.calc", menu: "Hologram", label: "Calculate hologram", keys: "F12", run: () => S().hologram() },
  { id: "holo.prop", menu: "Hologram", label: "Eye focus sweep (what the viewer sees)", keys: "Ctrl F12", run: () => S().tool("focus_sweep", { steps: 7, ...S().eyeArgs() }) },
  { id: "holo.eye", menu: "Hologram", label: "Eye view (what a pupil sees)", run: () => S().eyeView() },
  { id: "holo.window", menu: "Hologram", label: "Window Law check", run: () => S().tool("window_check") },
  { id: "holo.desk", menu: "Hologram", label: "Desk sharpness check", run: () => S().tool("desk_check") },
  { id: "holo.search", menu: "Hologram", label: "Search widest column (80% at 10 cm)", run: () => S().tool("search_column_width", { height_cm: 10, min_sharpness_pct: 80 }) },
  { id: "holo.speckle", menu: "Hologram", label: "Speckle comparison", run: () => S().tool("speckle_compare", { k: 3 }) },
  { id: "holo.hand", menu: "Hologram", label: "Hand occlusion check", run: () => S().tool("hand_check") },
  { id: "holo.film", menu: "Hologram", label: "Export print film", run: filmDownload },
];

export const cmd = (id) => COMMANDS.find((c) => c.id === id);
export const run = (id) => { const c = cmd(id); if (c && (!c.when || c.when())) c.run(); };
// Tools: the actions that used to sit in the bottom dock, in one menu (and optionally pinned as a bar)
COMMANDS.push(
  { id: "tools.bar", menu: "View", group: "Panels", label: "Show tool bar under the menu", run: () => S().setDockBar() },
);

COMMANDS.push(
  { id: "view.panelsToggle", menu: "View", group: "Panels", label: "Minimise / restore all panels", keys: "Shift Tab", run: () => {
    const st = S(), ids = ["orchestrator", "outliner", "physics", "cad", "asm", "drawing", "optics"].filter((k) => st.panels[k]);
    const anyOpen = ids.some((k) => st.win[k] !== "min");
    for (const k of ids) st.setWin(k, anyOpen ? "min" : "normal");
  } },
  { id: "ws.build", menu: "View", group: "Workspace", label: "Workspace: Build (chat, scene, physics)", run: () => S().workspace("build") },
  { id: "ws.inspect", menu: "View", group: "Workspace", label: "Workspace: Inspect (scene, B-rep assembly)", run: () => S().workspace("inspect") },
  { id: "ws.present", menu: "View", group: "Workspace", label: "Workspace: Present (3D only)", run: () => S().workspace("present") },
  { id: "ws.reset", menu: "View", group: "Workspace", label: "Reset layout (dock every panel)", run: () => S().resetLayout() },
);
// each menu shows its groups together, in the order the groups first appear
{
  const order = new Map();
  COMMANDS.forEach((cmd, i) => { const k = cmd.menu + "|" + (cmd.group || ""); if (!order.has(k)) order.set(k, i); });
  const idx = new Map(COMMANDS.map((cmd, i) => [cmd, i]));
  const key = (cmd) => [order.get(cmd.menu + "|" + (cmd.group || "")), idx.get(cmd)];
  COMMANDS.sort((a, b) => { const ka = key(a), kb = key(b); return ka[0] - kb[0] || ka[1] - kb[1]; });
}

export const MENUS = ["File", "Edit", "Select", "Add", "Object", "View", "Inspect", "Hologram", "Demo"];
