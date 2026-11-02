import { useMemo, useRef, useState } from "react";
import { useStore } from "../store";
import Icon from "./Icon";

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

export default function LeftPanel() {
  const parts = useStore((s) => s.state?.parts || []);
  const open = useStore((s) => s.panels.left);
  const setPanel = useStore((s) => s.setPanel);
  const tool = useStore((s) => s.tool);

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
          <button className="btn-icon" title="Collapse" onClick={() => setPanel("left", false)}><Icon name="panel" /></button>
        </div>
      </div>
      <div className="scroll-thin mt-3 flex-1 overflow-y-auto px-2 pb-3">{tree}</div>
      <div className="border-t border-line px-4 py-3 text-[11px] leading-relaxed text-slate-500">
        <span className="kbd">G</span> move <span className="kbd">R</span> rotate <span className="kbd">S</span> scale
        <span className="kbd ml-1">X/Y/Z</span> axis <span className="kbd">⇧D</span> duplicate <span className="kbd">Del</span>
        <span className="kbd ml-1">Ctrl Z</span> undo <span className="kbd">↵</span> hologram <span className="kbd">Tab</span> mode
      </div>
    </aside>
  );
}
