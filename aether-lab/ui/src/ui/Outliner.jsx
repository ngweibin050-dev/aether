import { useEffect, useMemo, useRef, useState } from "react";
import { selectedPart, useStore } from "../store";
import FloatPanel from "./FloatPanel";
import Icon from "./Icon";
import { Slider } from "./Charts";

// Blender number field: drag left/right to scrub, click to type.
export function Num({ value, onCommit, step = 1, className = "" }) {
  const [v, setV] = useState(value);
  const [edit, setEdit] = useState(false);
  useEffect(() => setV(value), [value]);
  const commit = () => { setEdit(false); const n = parseFloat(v); if (!Number.isNaN(n) && n !== value) onCommit(n); else setV(value); };
  if (edit)
    return <input autoFocus className={`field ${className}`} value={v} onChange={(e) => setV(e.target.value)} onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") { setV(value); setEdit(false); } }} />;
  const down = (e) => {
    const x0 = e.clientX, v0 = +value; let moved = false, cur = v0;
    const mv = (ev) => { const dx = ev.clientX - x0; if (Math.abs(dx) > 3) moved = true; if (moved) { cur = +(v0 + dx * step * (ev.shiftKey ? 0.1 : 0.5)).toFixed(3); setV(cur); } };
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); moved ? cur !== v0 && onCommit(cur) : setEdit(true); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  return <div onPointerDown={down} className={`field cursor-ew-resize truncate hover:border-cyan-glow/40 ${className}`}>{(+v).toFixed(2).replace(/\.?0+$/, "") || 0}</div>;
}

function Vec({ label, value, onCommit, step }) {
  return (
    <div className="grid grid-cols-[52px_1fr_1fr_1fr] items-center gap-1">
      <span className="text-[11px] text-silver">{label}</span>
      {["x", "y", "z"].map((a, i) => (
        <div key={a} className="relative">
          <span className={`pointer-events-none absolute left-1.5 top-1/2 z-10 -translate-y-1/2 font-mono text-[9px] ${["text-rose-400", "text-emerald-400", "text-sky-400"][i]}`}>{a.toUpperCase()}</span>
          <Num className="pl-4" step={step} value={+(value[i] ?? 0)} onCommit={(n) => { const v = [...value]; v[i] = n; onCommit(v); }} />
        </div>
      ))}
    </div>
  );
}

function Row({ p, depth, kids }) {
  const sel = useStore((s) => s.selection.includes(p.id));
  const active = useStore((s) => s.state.selected === p.id);
  const st = useStore.getState();
  const [open, setOpen] = useState(depth < 1);
  const [name, setName] = useState(null);
  return (
    <>
      <div draggable onDragStart={(e) => e.dataTransfer.setData("text/aether", p.id)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const id = e.dataTransfer.getData("text/aether"); if (id && id !== p.id) st.parentTo([id], p.id); }}
        onClick={(e) => st.select(p.id, { extend: e.shiftKey || e.ctrlKey })}
        onDoubleClick={() => setName(p.name)}
        className={`group flex h-7 cursor-pointer items-center gap-1.5 rounded-md pr-1.5 text-[12px] transition ${active ? "bg-cyan-glow/[0.16] text-white" : sel ? "bg-cyan-glow/[0.08] text-white" : "text-white/75 hover:bg-white/[0.05]"}`}
        style={{ paddingLeft: 6 + depth * 14 }}>
        <button className={`text-silver transition ${kids.length ? "" : "invisible"} ${open ? "rotate-90" : ""}`}
          onClick={(e) => { e.stopPropagation(); setOpen(!open); }}><Icon name="chevron" className="h-3 w-3" /></button>
        <Icon name={p.type === "group" ? "layers" : "cube"} className={`h-3.5 w-3.5 shrink-0 ${sel ? "text-cyan-glow" : "text-silver/70"}`} />
        {name !== null ? (
          <input autoFocus className="field h-5 py-0" value={name} onChange={(e) => setName(e.target.value)} onClick={(e) => e.stopPropagation()}
            onBlur={() => { if (name && name !== p.name) st.tool("update_part", { id: p.id, name }); setName(null); }}
            onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") setName(null); }} />
        ) : <span className={`truncate ${p.visible === false ? "opacity-35" : ""}`}>{p.name}</span>}
        <span className="ml-auto font-mono text-[9.5px] text-white/30">{p.type}</span>
        <button title="Hide in viewport" className="text-silver opacity-60 hover:text-white group-hover:opacity-100"
          onClick={(e) => { e.stopPropagation(); st.setVisible([p.id], p.visible === false); }}>
          <Icon name={p.visible === false ? "eyeoff" : "eye"} className="h-3.5 w-3.5" /></button>
      </div>
      {open && kids}
    </>
  );
}

function ItemTab() {
  const p = useStore(selectedPart);
  const n = useStore((s) => s.selection.length);
  const st = useStore.getState();
  if (!p) return <div className="px-4 py-5 text-[12px] text-silver">Nothing selected. Click a part, drag a box, or press <span className="kbd">A</span>.</div>;
  const up = (args) => st.commitParts(st.state.parts.map((q) => (q.id === p.id ? { ...q, ...args, params: args.params ? { ...q.params, ...args.params } : q.params } : q)));
  return (
    <div className="space-y-3 px-3.5 pb-3">
      <div className="flex items-center gap-2">
        <input className="field font-sans text-[12.5px]" defaultValue={p.name} key={p.id + p.name}
          onBlur={(e) => e.target.value && e.target.value !== p.name && st.tool("update_part", { id: p.id, name: e.target.value })}
          onKeyDown={(e) => e.key === "Enter" && e.target.blur()} />
        <button className="btn-icon hover:text-bad" title="Delete (X)" onClick={() => st.deleteSelected()}><Icon name="trash" /></button>
      </div>
      <div className="font-mono text-[10px] text-silver">{p.type} · {p.id}{n > 1 ? ` · ${n} selected` : ""}</div>
      <div className="space-y-1.5">
        <div className="label">Transform · mm / °</div>
        <Vec label="Location" value={p.position} onCommit={(v) => up({ position: v })} step={1} />
        <Vec label="Rotation" value={p.rotation} onCommit={(v) => up({ rotation: v })} step={1} />
        <Vec label="Scale" value={p.scale} onCommit={(v) => up({ scale: v })} step={0.02} />
      </div>
      {p.type !== "group" && p.type !== "mesh" && (
        <div className="space-y-1.5">
          <div className="label">Parameters</div>
          <div className="grid grid-cols-2 gap-x-2 gap-y-1.5">
            {Object.entries(p.params).filter(([, v]) => typeof v === "number").map(([k, v]) => (
              <label key={k} className="grid grid-cols-[1fr_64px] items-center gap-1.5"><span className="truncate font-mono text-[10px] text-silver">{k}</span>
                <Num value={v} step={0.5} onCommit={(x) => st.tool("update_part", { id: p.id, params: { [k]: x } })} /></label>
            ))}
          </div>
        </div>
      )}
      {p.type === "gear" && <GearTurn p={p} />}
      {p.eng?.dims && Object.keys(p.eng.dims).length > 0 && (
        <div className="space-y-1">
          <div className="label">Engineering · {p.eng.kind}</div>
          <div className="space-y-0.5 font-mono text-[10px]">
            {Object.entries(p.eng.dims).map(([k, [v, src]]) => (
              <div key={k} className="flex gap-2"><span className="w-28 truncate text-silver">{k}</span><span className="text-white/90">{String(v)}</span>
                <span className={`ml-auto truncate ${/assumed/.test(src) ? "text-warn" : "text-cyan-glow/80"}`} title={src}>{/assumed/.test(src) ? "assumed" : src ? "from drawing" : ""}</span></div>))}
            {p.eng.joints?.map((j, i) => <div key={i} className="text-silver">{j.type.replace("_", " ")} → {j.with}</div>)}
          </div>
        </div>
      )}
      <div className="space-y-1">
        <div className="flex justify-between"><span className="label">Optical brightness</span><span className="readout">{(p.brightness ?? 1).toFixed(2)}</span></div>
        <Slider value={p.brightness ?? 1} min={0.1} max={1} step={0.05} onCommit={(v) => up({ brightness: +v.toFixed(2) })} />
      </div>
    </div>
  );
}

// Turn a gear: meshing gears follow by the tooth ratio (engine turn_gear). "Run" keeps turning it.
function GearTurn({ p }) {
  const st = useStore.getState();
  const [run, setRun] = useState(false);
  useEffect(() => {
    if (!run) return;
    let alive = true;
    (async () => { while (alive) { await st.tool("turn_gear", { id: p.id, degrees: 6 }, { record: false, quiet: true }).catch(() => (alive = false)); await new Promise((r) => setTimeout(r, 60)); } })();
    return () => { alive = false; };
  }, [run, p.id]);
  return (
    <div className="space-y-1">
      <div className="label">Motion · {p.params.teeth} teeth{p.params.module ? ` · m ${p.params.module}` : ""}</div>
      <div className="grid grid-cols-3 gap-1.5">
        <button className="btn !py-1 text-[11px]" onClick={() => st.tool("turn_gear", { id: p.id, degrees: -15 })}>↺ 15°</button>
        <button className={`btn !py-1 text-[11px] ${run ? "!border-cyan-glow/50 text-cyan-glow" : ""}`} onClick={() => setRun(!run)}>{run ? "Stop" : "Run"}</button>
        <button className="btn !py-1 text-[11px]" onClick={() => st.tool("turn_gear", { id: p.id, degrees: 15 })}>↻ 15°</button>
      </div>
    </div>
  );
}

// STL / OBJ (mm, z up as most CAD exports) -> import_mesh at real size
function importCAD(file) {
  const { tool, notify } = useStore.getState();
  const ext = file.name.split(".").pop().toLowerCase();
  const loader = ext === "stl" ? import("three/examples/jsm/loaders/STLLoader.js").then((m) => new m.STLLoader())
    : import("three/examples/jsm/loaders/OBJLoader.js").then((m) => new m.OBJLoader());
  return loader.then(async (L) => {
    const V = [], F = [];
    if (ext === "stl") {
      const g = L.parse(await file.arrayBuffer());
      const pos = g.attributes.position;
      for (let i = 0; i < pos.count; i++) { V.push(pos.getX(i), pos.getY(i), pos.getZ(i)); F.push(i); }
    } else {
      const obj = L.parse(await file.text());
      obj.updateMatrixWorld(true);
      obj.traverse((o) => {
        if (!o.isMesh) return;
        const pos = o.geometry.attributes.position, base = V.length / 3, e = o.matrixWorld.elements;
        for (let i = 0; i < pos.count; i++) {
          const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
          V.push(e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]);
        }
        const idx = o.geometry.index ? o.geometry.index.array : [...Array(pos.count).keys()];
        for (let i = 0; i < idx.length; i++) F.push(idx[i] + base);
      });
    }
    if (!F.length) throw new Error("no triangles in file");
    notify(`Importing ${file.name}: ${F.length / 3} triangles at real size (mm) → decimating…`);
    return tool("import_mesh", { name: file.name.replace(/\.(stl|obj)$/i, ""), vertices: V, faces: F, target_faces: 6000,
      position: useStore.getState().cursor3d, size_mm: 0 });
  });
}

// Three orthographic views (front, top, right side) -> visual-hull solid at real size
async function importThreeView(files) {
  const { tool, notify } = useStore.getState();
  if (files.length !== 3) throw new Error("pick exactly 3 images: front, top, right side");
  const order = ["front", "top", "side"].map((k) => files.find((f) => f.name.toLowerCase().includes(k)));
  const picked = order.every(Boolean) && new Set(order).size === 3 ? order : files;
  const url = (f) => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(f); });
  const [front, top, side] = await Promise.all(picked.map(url));
  const w = parseFloat(window.prompt(`Front view width in mm (${picked.map((f) => f.name).join(" / ")})`, "80"));
  if (!(w > 0)) return;
  notify("Carving the three views into a solid…");
  return tool("import_three_view", { front, top, side, width_mm: w, name: picked[0].name.replace(/\.[^.]+$/, "") });
}

function importGLB(file) {
  const { tool, notify } = useStore.getState();
  return import("three/examples/jsm/loaders/GLTFLoader.js").then(async ({ GLTFLoader }) => {
    const gltf = await new GLTFLoader().parseAsync(await file.arrayBuffer(), "");
    const V = [], F = [];
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry, pos = g.attributes.position, base = V.length / 3, e = o.matrixWorld.elements;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        V.push(e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]);
      }
      const idx = g.index ? g.index.array : [...Array(pos.count).keys()];
      for (let i = 0; i < idx.length; i++) F.push(idx[i] + base);
    });
    if (!F.length) throw new Error("no meshes in file");
    for (let i = 0; i < V.length; i += 3) { const y = V[i + 1]; V[i + 1] = -V[i + 2]; V[i + 2] = y; }   // glTF y-up -> desk z-up
    notify(`Importing ${file.name}: ${F.length / 3} triangles → decimating…`);
    return tool("import_mesh", { name: file.name.replace(/\.(glb|gltf)$/i, ""), vertices: V, faces: F, target_faces: 4000, position: useStore.getState().cursor3d });
  });
}

export default function Outliner() {
  const parts = useStore((s) => s.state?.parts || []);
  const open = useStore((s) => s.panels.outliner);
  const tab = useStore((s) => s.outlinerTab);
  const file = useRef(), views = useRef();
  const tree = useMemo(() => {
    const kids = {}, ids = new Set(parts.map((p) => p.id));
    for (const p of parts) (kids[p.parent && ids.has(p.parent) ? p.parent : "root"] ||= []).push(p);
    const render = (p, d) => <Row key={p.id} p={p} depth={d} kids={(kids[p.id] || []).map((k) => render(k, d + 1))} />;
    return (kids.root || []).map((p) => render(p, 0));
  }, [parts]);
  const st = useStore.getState();
  return (
    <FloatPanel id="outliner" title="Scene" icon="layers" open={open} onClose={() => st.setPanel("outliner", false)}
      className="bottom-[78px] left-3 top-[calc(50vh+38px)] w-[310px]"
      right={<>
        <button className="grid h-6 w-6 place-items-center rounded-md text-silver hover:bg-white/10 hover:text-white" title="Add (Shift+A)"
          onClick={(e) => st.setMenu({ kind: "add", x: e.clientX, y: e.clientY })}><Icon name="plus" className="h-3.5 w-3.5" /></button>
        <button className="grid h-6 w-6 place-items-center rounded-md text-silver hover:bg-white/10 hover:text-white" title="Import CAD mesh: STL, OBJ, GLB (STEP: export STL from your CAD first)"
          onClick={() => file.current.click()}><Icon name="upload" className="h-3.5 w-3.5" /></button>
        <input id="glb-input" ref={file} type="file" accept=".glb,.gltf,.stl,.obj" hidden onChange={(e) => {
          const f = e.target.files[0]; e.target.value = "";
          if (f) (/\.(stl|obj)$/i.test(f.name) ? importCAD(f) : importGLB(f)).catch((err) => st.notify(err.message, "error"));
        }} />
        <button className="grid h-6 w-6 place-items-center rounded-md font-mono text-[9px] text-silver hover:bg-white/10 hover:text-white"
          title="Three-view drawing → 3D: pick 3 images (front, top, right side; names containing front/top/side set the order)"
          onClick={() => views.current.click()}>3V</button>
        <input ref={views} type="file" accept="image/*" multiple hidden onChange={(e) => {
          const fs = [...e.target.files]; e.target.value = "";
          if (fs.length) importThreeView(fs).catch((err) => st.notify(err.message, "error"));
        }} />
      </>}>
      <div className="mx-3.5 mb-2 flex gap-1 rounded-lg bg-black/25 p-0.5">
        {[["outliner", `Outliner · ${parts.length}`], ["item", "Item  (N)"]].map(([k, l]) => (
          <button key={k} className={`tab ${tab === k ? "tab-on" : ""}`} onClick={() => useStore.setState({ outlinerTab: k })}>{l}</button>))}
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-2 pb-2">{tab === "outliner" ? tree : <ItemTab />}</div>
    </FloatPanel>
  );
}
