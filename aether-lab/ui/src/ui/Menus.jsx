import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { selectedPart, useStore } from "../store";
import { COMMANDS, cmd, run } from "../commands";
import { MenuList } from "./MenuBar";
import Icon from "./Icon";

const CONTEXT = ["obj.move", "obj.rotate", "obj.scale", "obj.dup", "obj.delete", "obj.hide", "obj.unhide", "in.isolate", "in.secx", "in.secy",
  "in.explode", "in.xray", "obj.parent", "obj.unparent", "obj.snapcursor", "view.frame", "holo.calc"];
const PIES = {
  "pie-view": ["view.left", "view.right", "view.bottom", "view.top", "view.front", "view.back", "view.eye", "view.frame"],
  "pie-shading": ["view.wire", "view.solid", "view.holo", "in.xray"],
  "pie-snap": ["obj.snapcursor", "obj.snapsel", "obj.cursorreset", "view.frame"],
};
// Blender pie order: W, E, S, N, NW, NE, SW, SE
const DIRS = [[-1, 0], [1, 0], [0, 1], [0, -1], [-0.72, -0.72], [0.72, -0.72], [-0.72, 0.72], [0.72, 0.72]];

export function Pie({ x, y, items, onDone, radius = 120, big = false }) {
  return (
    <div className="pointer-events-none fixed inset-0 z-50">
      <motion.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="absolute" style={{ left: x, top: y }}>
        <div className="absolute -left-3 -top-3 h-6 w-6 rounded-full border-2 border-cyan-glow/60 shadow-glow" />
        {items.map((it, i) => {
          const [dx, dy] = DIRS[i % 8], ok = !it.when || it.when();
          return (
            <button key={it.id} disabled={!ok} data-hand-target
              onClick={() => { onDone(); it.run(); }}
              className={`glass-solid pointer-events-auto absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-2 whitespace-nowrap rounded-full px-3.5 ${big ? "py-3 text-[14px]" : "py-1.5 text-[12px]"}
                text-white/90 transition hover:border-cyan-glow/60 hover:text-white hover:shadow-[0_0_20px_rgba(95,225,255,.35)] disabled:opacity-35`}
              style={{ left: dx * radius, top: dy * radius * 0.82 }}>
              {it.icon && <Icon name={it.icon} className={big ? "h-5 w-5 text-cyan-glow" : "h-3.5 w-3.5 text-cyan-glow"} />}{it.label}
            </button>
          );
        })}
      </motion.div>
    </div>
  );
}

function Search({ onDone }) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const list = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return COMMANDS.filter((c) => (!c.when || c.when()) && words.every((w) => `${c.menu} ${c.label}`.toLowerCase().includes(w))).slice(0, 14);
  }, [q]);
  return (
    <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} style={{ x: "-50%" }}
      className="glass-solid pointer-events-auto fixed left-1/2 top-[110px] z-50 w-[460px] overflow-hidden">
      <div className="flex items-center gap-2 border-b border-white/[0.07] px-3 py-2.5">
        <Icon name="search" className="h-4 w-4 text-cyan-glow" />
        <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setI(0); }} placeholder="Search every AETHER action…"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setI((i + 1) % Math.max(list.length, 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setI((i - 1 + list.length) % Math.max(list.length, 1)); }
            if (e.key === "Enter" && list[i]) { onDone(); list[i].run(); }
            if (e.key === "Escape") onDone();
          }} className="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-white/35" />
        <span className="kbd">F3</span>
      </div>
      <div className="scroll-thin max-h-[52vh] overflow-y-auto p-1">
        {list.map((c, k) => (
          <button key={c.id} data-hand-target onMouseEnter={() => setI(k)} onClick={() => { onDone(); c.run(); }}
            className={`menu-item ${k === i ? "bg-cyan-glow/[0.12]" : ""}`}>
            <span className="w-16 text-[10.5px] text-silver">{c.menu}</span>
            <span className="flex-1 first-letter:uppercase">{c.label}</span>
            {c.keys && <span className="font-mono text-[10px] text-silver">{c.keys}</span>}
          </button>
        ))}
        {!list.length && <div className="px-3 py-3 text-[12px] text-silver">No matching action.</div>}
      </div>
    </motion.div>
  );
}

function Rename({ x, y, onDone }) {
  const p = useStore(selectedPart);
  const ref = useRef();
  useEffect(() => { ref.current?.select(); }, []);
  if (!p) return null;
  return (
    <div className="glass-solid pointer-events-auto fixed z-50 w-56 p-2" style={{ left: Math.min(x, innerWidth - 240), top: y }}>
      <div className="label mb-1">Rename</div>
      <input ref={ref} autoFocus defaultValue={p.name} className="field font-sans text-[12.5px]"
        onKeyDown={(e) => {
          if (e.key === "Enter") { const n = e.target.value.trim(); n && n !== p.name && useStore.getState().tool("update_part", { id: p.id, name: n }); onDone(); }
          if (e.key === "Escape") onDone();
        }} onBlur={onDone} />
    </div>
  );
}

export default function Menus() {
  const menu = useStore((s) => s.menu);
  const setMenu = useStore((s) => s.setMenu);
  const done = () => setMenu(null);
  useEffect(() => {
    if (!menu) return;
    const f = (e) => { if (!e.target.closest?.("[data-menu]")) done(); };
    const k = (e) => e.key === "Escape" && done();
    const t = setTimeout(() => addEventListener("pointerdown", f), 0);
    addEventListener("keydown", k);
    return () => { clearTimeout(t); removeEventListener("pointerdown", f); removeEventListener("keydown", k); };
  }, [menu]);
  if (!menu) return null;
  const x = menu.x ?? innerWidth / 2, y = menu.y ?? innerHeight / 2;
  const rows = { add: 14, context: 17, delete: 1 }[menu.kind] || 8;
  const at = { left: Math.min(x, innerWidth - 270), top: Math.max(56, Math.min(y, innerHeight - 40 - rows * 31)) };
  let body = null;
  if (menu.kind === "add")
    body = <div className="glass-solid pointer-events-auto fixed z-50 w-60 p-1" style={at}><div className="label px-2.5 pb-1 pt-1.5">Add</div><MenuList items={COMMANDS.filter((c) => c.menu === "Add")} onDone={done} /></div>;
  else if (menu.kind === "context")
    body = <div className="glass-solid scroll-thin pointer-events-auto fixed z-50 max-h-[80vh] w-64 overflow-y-auto p-1" style={at}><div className="label px-2.5 pb-1 pt-1.5">Object</div><MenuList items={CONTEXT.map(cmd)} onDone={done} /></div>;
  else if (menu.kind === "delete")
    body = <div className="glass-solid pointer-events-auto fixed z-50 w-44 p-1" style={at}><button autoFocus className="menu-item" onClick={() => { done(); run("obj.delete"); }}><Icon name="trash" className="h-3.5 w-3.5 text-bad" />Delete</button></div>;
  else if (PIES[menu.kind])
    body = <Pie x={x} y={y} items={PIES[menu.kind].map(cmd)} onDone={done} />;
  else if (menu.kind === "search") body = <Search onDone={done} />;
  else if (menu.kind === "rename") body = <Rename x={x} y={y} onDone={done} />;
  else if (menu.kind === "hand" && menu.items) body = <Pie x={x} y={y} items={menu.items} onDone={done} radius={170} big />;
  return <AnimatePresence><div data-menu>{body}</div></AnimatePresence>;
}
