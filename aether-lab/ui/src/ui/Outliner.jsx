import { useEffect, useMemo, useRef, useState } from "react";
import { selectedPart, useStore } from "../store";
import FloatPanel, { PanelIcon } from "./FloatPanel";
import { L } from "./layout";
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
        <div className="text-[11px] text-silver">Uniform scale <Num value={p.scale[0]} step={0.02} onCommit={(v) => up({ scale: [v, v, v] })} /></div>
      </div>
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

export default function Outliner() {
  const parts = useStore((s) => s.state?.parts || []);
  const open = useStore((s) => s.panels.outliner);
  const tab = useStore((s) => s.outlinerTab);
  const file = useRef();
  const tree = useMemo(() => {
    const kids = {}, ids = new Set(parts.map((p) => p.id));
    for (const p of parts) (kids[p.parent && ids.has(p.parent) ? p.parent : "root"] ||= []).push(p);
    const render = (p, d) => <Row key={p.id} p={p} depth={d} kids={(kids[p.id] || []).map((k) => render(k, d + 1))} />;
    return (kids.root || []).map((p) => render(p, 0));
  }, [parts]);
  const st = useStore.getState();
  return (<>
    <PanelIcon id="outliner" title="Scene" icon="layers" style={{ left: L.gap, top: L.top }} />
    <FloatPanel id="outliner" title="Scene" icon="layers" open={open} onClose={() => st.setPanel("outliner", false)}
      style={{ left: L.gap, top: L.top, bottom: L.bottom, width: L.left }}
      right={<>
        <button className="grid h-6 w-6 place-items-center rounded-md text-silver hover:bg-white/10 hover:text-white" title="Import STEP B-rep or AETHER CAD package"
          onClick={() => file.current.click()}><Icon name="upload" className="h-3.5 w-3.5" /></button>
        <input id="step-input" ref={file} type="file" accept=".step,.stp,.zip" hidden onChange={async (e) => {
          const f = e.target.files[0]; e.target.value = ""; if (!f) return;
          try {
            const data = await new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.onerror = reject; r.readAsDataURL(f); });
            const isPackage = f.name.toLowerCase().endsWith(".aether.zip");
            if (!isPackage && !/\.(step|stp)$/i.test(f.name)) throw new Error("Select a STEP or .aether.zip CAD package.");
            const j = await (await import("../api")).api(isPackage ? "/api/cad/import_package" : "/api/cad/import_step", { file: data, name: f.name });
            st.applyState(j.state); st.setPanel("cad", true); st.notify(isPackage ? "CAD package restored and recomputed." : "STEP imported as external B-rep; feature history is not available.");
          } catch (err) { st.notify(err.message, "error"); }
        }} />
      </>}>
      <div className="mx-3.5 mb-2 flex gap-1 rounded-lg bg-black/25 p-0.5">
        {[["outliner", `Outliner · ${parts.length}`], ["item", "Item  (N)"]].map(([k, l]) => (
          <button key={k} className={`tab ${tab === k ? "tab-on" : ""}`} onClick={() => useStore.setState({ outlinerTab: k })}>{l}</button>))}
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-2 pb-2">{tab === "outliner" ? tree : <ItemTab />}</div>
    </FloatPanel>
  </>);
}
