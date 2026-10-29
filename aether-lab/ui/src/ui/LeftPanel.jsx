import { useMemo, useRef, useState } from "react";
import { useStore } from "../store";
import Icon from "./Icon";

const PRIMS = [
  ["gear", { teeth: 16, radius: 25, thickness: 8 }], ["cylinder", { radius: 12, height: 40 }],
  ["tube", { outer: 20, inner: 15, height: 30 }], ["box", { w: 40, d: 30, h: 20 }],
  ["cone", { r_bottom: 18, r_top: 4, height: 40 }], ["sphere", { radius: 18 }],
  ["torus", { radius: 22, tube_radius: 5 }], ["nozzle", { throat: 8, exit: 24, length: 45, chamber: 14, chamber_length: 25 }],
  ["coil", { radius: 16, wire: 1.5, turns: 6, pitch: 5 }], ["blade_ring", { count: 10, inner: 6, outer: 26, thickness: 1.5, height: 8, twist: 25 }],
];

function Row({ p, depth, kids }) {
  const sel = useStore((s) => s.state.selected === p.id);
  const select = useStore((s) => s.select);
  const tool = useStore((s) => s.tool);
  const [open, setOpen] = useState(true);
  return (
    <>
      <div onClick={() => select(p.id)}
        className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] transition ${sel ? "bg-cyan-glow/15 text-white" : "text-slate-300 hover:bg-white/5"}`}
        style={{ paddingLeft: 8 + depth * 14 }}>
        <button className={`text-slate-500 transition ${kids.length ? "" : "invisible"} ${open ? "rotate-90" : ""}`}
          onClick={(e) => { e.stopPropagation(); setOpen(!open); }}><Icon name="chevron" className="h-3 w-3" /></button>
        <Icon name={p.type === "group" ? "layers" : "cube"} className={`h-3.5 w-3.5 ${sel ? "text-cyan-glow" : "text-slate-500"}`} />
        <span className={`truncate ${p.visible === false ? "opacity-40" : ""}`}>{p.name}</span>
        <span className="ml-auto font-mono text-[10px] text-slate-500">{p.type}</span>
        <button title="Hide / show" className="opacity-0 transition group-hover:opacity-100 text-slate-400 hover:text-white"
          onClick={(e) => { e.stopPropagation(); tool("update_part", { id: p.id, visible: p.visible === false }); }}>
          <Icon name={p.visible === false ? "eyeoff" : "eye"} className="h-3.5 w-3.5" /></button>
      </div>
      {open && kids}
    </>
  );
}

function importGLB(file, tool, notify) {
  // Parse GLB/GLTF in the browser, merge all meshes, send vertices+faces to be decimated server-side.
  return import("three/examples/jsm/loaders/GLTFLoader.js").then(async ({ GLTFLoader }) => {
    const buf = await file.arrayBuffer();
    const gltf = await new GLTFLoader().parseAsync(buf, "");
    const V = [], F = [];
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry.index ? o.geometry : o.geometry.toNonIndexed();
      const pos = g.attributes.position, base = V.length / 3;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        const e = o.matrixWorld.elements;
        V.push(e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]);
      }
      const idx = g.index ? g.index.array : [...Array(pos.count).keys()];
      for (let i = 0; i < idx.length; i++) F.push(idx[i] + base);
    });
    if (!F.length) throw new Error("no meshes in file");
    // y-up (glTF) -> z-up (AETHER desk)
    for (let i = 0; i < V.length; i += 3) { const y = V[i + 1]; V[i + 1] = -V[i + 2]; V[i + 2] = y; }
    notify(`Importing ${file.name}: ${F.length / 3} triangles → decimating…`);
    return tool("import_mesh", { name: file.name.replace(/\.(glb|gltf)$/i, ""), vertices: V, faces: F, target_faces: 4000 });
  });
}

export default function LeftPanel() {
  const parts = useStore((s) => s.state?.parts || []);
  const open = useStore((s) => s.panels.left);
  const setPanel = useStore((s) => s.setPanel);
  const tool = useStore((s) => s.tool);
  const notify = useStore((s) => s.notify);
  const [adding, setAdding] = useState(false);
  const file = useRef();

  const tree = useMemo(() => {
    const kids = {};
    for (const p of parts) (kids[p.parent || "root"] ||= []).push(p);
    const render = (p, d) => <Row key={p.id} p={p} depth={d} kids={(kids[p.id] || []).map((k) => render(k, d + 1))} />;
    return (kids.root || []).map((p) => render(p, 0));
  }, [parts]);

  if (!open)
    return <button onClick={() => setPanel("left", true)} className="glass pointer-events-auto absolute left-4 top-20 z-20 p-2.5" title="Scene"><Icon name="layers" /></button>;

  return (
    <aside className="glass pointer-events-auto absolute bottom-24 left-4 top-20 z-20 flex w-[270px] flex-col animate-floatin">
      <div className="flex items-center justify-between px-4 pt-4">
        <div><div className="font-display text-[14px] font-semibold">Scene</div><div className="label mt-0.5">{parts.length} parts</div></div>
        <div className="flex gap-1">
          <button className="btn-icon" title="Add part" onClick={() => setAdding(!adding)}><Icon name="plus" /></button>
          <button className="btn-icon" title="Import GLB" onClick={() => file.current.click()}><Icon name="upload" /></button>
          <button className="btn-icon" title="Collapse" onClick={() => setPanel("left", false)}><Icon name="panel" /></button>
        </div>
        <input ref={file} type="file" accept=".glb,.gltf" hidden onChange={(e) => {
          const f = e.target.files[0]; e.target.value = "";
          if (f) importGLB(f, tool, notify).catch((err) => notify(err.message, "error"));
        }} />
      </div>
      {adding && (
        <div className="mx-3 mt-3 grid grid-cols-2 gap-1.5 rounded-xl border border-line bg-black/25 p-2 animate-floatin">
          {PRIMS.map(([t, params]) => (
            <button key={t} className="rounded-lg px-2 py-1.5 text-left text-[12px] text-slate-300 hover:bg-cyan-glow/10 hover:text-white"
              onClick={() => { tool("add_part", { type: t, params, name: t.replace("_", " "), position: [0, 0, 60] }); setAdding(false); }}>
              {t.replace("_", " ")}
            </button>
          ))}
        </div>
      )}
      <div className="scroll-thin mt-3 flex-1 overflow-y-auto px-2 pb-3">{tree}</div>
      <div className="border-t border-line px-4 py-3 text-[11px] leading-relaxed text-slate-500">
        <span className="kbd">G</span> move <span className="kbd">R</span> rotate <span className="kbd">S</span> scale
        <span className="kbd ml-1">X/Y/Z</span> axis <span className="kbd">⇧D</span> duplicate <span className="kbd">Del</span>
        <span className="kbd ml-1">Ctrl Z</span> undo <span className="kbd">↵</span> hologram <span className="kbd">Tab</span> mode
      </div>
    </aside>
  );
}
