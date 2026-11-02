import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useStore } from "../store";
import { COMMANDS, MENUS } from "../commands";
import Icon from "./Icon";

export function MenuList({ items, onDone }) {
  let group = null;
  return items.map((c) => {
    const head = c.group && c.group !== group ? (group = c.group) : null;
    const ok = !c.when || c.when();
    return (
      <div key={c.id}>
        {head && <div className="label px-2.5 pb-1 pt-2 !text-[9px]">{head}</div>}
        <button disabled={!ok} className="menu-item" onClick={() => { onDone?.(); c.run(); }}>
          <span className="flex-1 first-letter:uppercase">{c.label}</span>
          {c.keys && <span className="font-mono text-[10px] text-silver">{c.keys}</span>}
        </button>
      </div>
    );
  });
}

export default function MenuBar() {
  const [open, setOpen] = useState(null);
  const shading = useStore((s) => s.shading);
  const xray = useStore((s) => s.view.xray);
  const compute = useStore((s) => s.compute);
  const stale = useStore((s) => s.modalStale);
  const undo = useStore((s) => s.undo.length), redo = useStore((s) => s.redo.length);
  const s = useStore.getState();
  useEffect(() => {
    if (!open) return;
    const close = (e) => !e.target.closest?.("[data-menubar]") && setOpen(null);
    addEventListener("pointerdown", close);
    return () => removeEventListener("pointerdown", close);
  }, [open]);
  return (
    <header className="pointer-events-auto absolute inset-x-3 top-3 z-40 flex h-10 items-center gap-2" data-menubar>
      <div className="glass flex h-10 items-center gap-1 rounded-xl px-2">
        <a href="#/" title="Back to the AETHER home page" className="flex items-center gap-2 rounded-lg pl-1 pr-2 transition hover:bg-white/[0.06]">
          <div className="relative h-5 w-5 rounded-full border border-cyan-glow/70 shadow-glow"><div className="absolute inset-[5px] rounded-full bg-cyan-glow/80" /></div>
          <span className="font-display text-[13px] font-bold tracking-[0.22em]">AETHER</span>
          <span className="grad-text-lab font-mono text-[10px] font-semibold"> v0.1.0</span>
        </a>
        {MENUS.map((m) => (
          <div key={m} className="relative">
            <button onClick={() => setOpen(open === m ? null : m)} onPointerEnter={() => open && setOpen(m)}
              className={`rounded-md px-2.5 py-1 text-[12px] transition ${open === m ? "bg-white/10 text-white" : "text-white/75 hover:text-white"}`}>{m}</button>
            <AnimatePresence>
              {open === m && (
                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.12 }}
                  className="glass-solid scroll-thin absolute left-0 top-9 max-h-[70vh] w-64 overflow-y-auto p-1">
                  <MenuList items={COMMANDS.filter((c) => c.menu === m)} onDone={() => setOpen(null)} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div className="glass flex h-10 items-center gap-1 rounded-xl px-1.5">
          <button title="Undo (Ctrl+Z)" disabled={!undo} onClick={() => s.undoOnce()} className="btn-icon border-0 bg-transparent"><Icon name="undo" /></button>
          <button title="Redo (Ctrl+Shift+Z)" disabled={!redo} onClick={() => s.redoOnce()} className="btn-icon border-0 bg-transparent"><Icon name="redo" /></button>
          <span className="mx-1 h-5 w-px bg-white/10" />
          <button title="X-ray (Alt+Z)" onClick={() => s.setView({ xray: !xray }, { now: true })}
            className={`btn-icon border-0 ${xray ? "bg-cyan-glow/20 text-cyan-glow" : "bg-transparent"}`}><Icon name="xray" /></button>
          {[["wire", "wire", "Wireframe"], ["solid", "solid", "Solid"], ["holo", "holo", "Hologram look"]].map(([k, ic, t]) => (
            <button key={k} title={`${t} (Z)`} onClick={() => s.setShading(k)}
              className={`btn-icon border-0 ${shading === k ? "bg-cyan-glow/20 text-cyan-glow" : "bg-transparent"}`}><Icon name={ic} fill={k === "solid" && shading === k} /></button>
          ))}
        </div>
        <span className="chip !font-sans !text-[11px]"><i className="h-1.5 w-1.5 rounded-full bg-ok shadow-[0_0_8px_#5eead4]" />Muse Spark</span>
        {compute === "modal" && stale
          ? <span className="chip !font-sans !text-[11px] !border-warn/30 !text-warn" title="Modal runs an older AETHER engine than this computer. The server is uploading the new engine to Modal now (about 1 to 3 minutes); heavy tools wait for it and then run on the GPU. Nothing runs on this CPU.">
              <i className="h-1.5 w-1.5 rounded-full bg-warn" />Modal T4 · updating engine…</span>
          : <span className="chip !font-sans !text-[11px]"><i className={`h-1.5 w-1.5 rounded-full ${compute === "modal" ? "bg-magenta-glow" : "bg-cyan-glow"}`} />{compute === "modal" ? "Modal T4 GPU" : "local CPU"}</span>}
        <span className="chip !font-sans !text-[11px] !border-warn/30 !bg-warn/[0.06] !text-warn/90" title="Everything here is a simulation, not a built display">
          Simulation<span className="hidden 2xl:inline">&nbsp;· not a built display</span></span>
      </div>
    </header>
  );
}
