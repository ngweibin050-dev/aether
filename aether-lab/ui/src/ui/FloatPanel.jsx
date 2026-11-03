import { useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useStore } from "../store";
import { MAX_STYLE } from "./layout";
import Icon from "./Icon";

const HeadBtn = ({ icon, title, onClick }) => (
  <button className="grid h-6 w-6 place-items-center rounded-md text-slate-400 transition hover:bg-white/10 hover:text-white" title={title} onClick={onClick}>
    <Icon name={icon} className="h-3.5 w-3.5" /></button>
);

export const IconTile = ({ icon, big }) => (
  <span className={`grid shrink-0 place-items-center rounded-md border border-cyan-glow/25 bg-gradient-to-br from-cyan-400/15 to-violet-500/15 text-cyan-glow ${big ? "h-8 w-8" : "h-6 w-6"}`}>
    <Icon name={icon} className={big ? "h-4 w-4" : "h-3.5 w-3.5"} /></span>
);

// Every lab panel works the same way (like Illustrator's panels):
//  - docked: placed by the layout (style); drag the header to float it anywhere, its place and size are remembered;
//  - floating: drag the header to move, the corner to resize; "Dock" puts it back where it belongs;
//  - minimise: it becomes an icon in the panel tray at the left edge (click to bring it back);
//  - maximise: double-click the header (or the button); close: View menu brings it back.
const DOCK = { outliner: "left", physics: "right", orchestrator: "bottom" };
export const PANEL_META = {};                     // id -> { title, icon } for the tray (filled by the panels)

export default function FloatPanel({ id, title, icon, open = true, onClose, className = "", style, right, children, busy, resizeTop }) {
  const mode = useStore((s) => s.win[id] || "normal");
  const rect = useStore((s) => s.rects[id]);
  const setWin = useStore((s) => s.setWin);
  const setRect = useStore((s) => s.setRect);
  const ref = useRef();
  PANEL_META[id] = { title, icon };
  const max = mode === "max";
  const floating = !!rect && !max;

  const drag = (e) => {
    if (e.button !== 0 || e.target.closest("button, input, select, textarea")) return;
    const sec = ref.current;
    if (!sec) return;
    e.preventDefault();
    const r0 = sec.getBoundingClientRect();
    const x0 = e.clientX, y0 = e.clientY;
    let r = { x: r0.left, y: r0.top, w: r0.width, h: r0.height }, moved = false;
    const mv = (ev) => {
      const dx = ev.clientX - x0, dy = ev.clientY - y0;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 4) return;
      moved = true;
      r = { ...r, x: Math.min(Math.max(r0.left + dx, -r0.width + 80), innerWidth - 80), y: Math.min(Math.max(r0.top + dy, 48), innerHeight - 40) };
      Object.assign(sec.style, { left: r.x + "px", top: r.y + "px", right: "auto", bottom: "auto", width: r.w + "px", height: r.h + "px" });
    };
    const up = () => {
      removeEventListener("pointermove", mv); removeEventListener("pointerup", up);
      if (moved) setRect(id, r);
    };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  const resize = (e) => {
    e.preventDefault(); e.stopPropagation();
    const sec = ref.current, r0 = sec.getBoundingClientRect(), x0 = e.clientX, y0 = e.clientY;
    let r = { x: r0.left, y: r0.top, w: r0.width, h: r0.height };
    const mv = (ev) => {
      r = { ...r, w: Math.max(240, r0.width + ev.clientX - x0), h: Math.max(140, r0.height + ev.clientY - y0) };
      Object.assign(sec.style, { left: r.x + "px", top: r.y + "px", right: "auto", bottom: "auto", width: r.w + "px", height: r.h + "px" });
    };
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); setRect(id, r); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  const place = max ? MAX_STYLE : floating ? { left: rect.x, top: rect.y, width: rect.w, height: rect.h, zIndex: 25 } : style;

  return (
    <AnimatePresence>
      {open && mode !== "min" && (
        <motion.section ref={ref} key={id} data-dock={floating ? undefined : DOCK[id]} data-mode={mode} data-panel={id}
          initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }}
          transition={{ type: "spring", stiffness: 360, damping: 32 }}
          style={place}
          className={`glass pointer-events-auto absolute z-20 flex flex-col overflow-hidden ${max || floating ? "" : className}`}>
          {resizeTop && !max && !floating && (
            <div title="Drag to resize · double-click to reset" onPointerDown={resizeTop.start} onDoubleClick={resizeTop.reset}
              className="group absolute inset-x-0 top-0 z-10 flex h-2.5 cursor-ns-resize justify-center">
              <span className="mt-[3px] h-1 w-10 rounded-full bg-white/15 transition group-hover:bg-cyan-glow/70" />
            </div>)}
          <header className="flex min-w-0 cursor-grab items-center gap-2 px-3.5 py-2.5 active:cursor-grabbing" onPointerDown={drag}
            onDoubleClick={(e) => !e.target.closest("button") && setWin(id, max ? "normal" : "max")}
            title="Drag to move · double-click to maximise">
            {icon && <IconTile icon={icon} />}
            <span className="truncate font-display text-[13px] font-bold tracking-tight text-white">{title}</span>
            {busy && <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-cyan-glow shadow-glow" />}
            <div className="ml-auto flex shrink-0 items-center gap-1">
              {right}
              {floating && <HeadBtn icon="panel" title="Dock (put it back in its place)" onClick={() => setRect(id, null)} />}
              <HeadBtn icon="min" title="Minimise to the panel tray" onClick={() => setWin(id, "min")} />
              <HeadBtn icon={max ? "restore" : "max"} title={max ? "Restore" : "Maximise"} onClick={() => setWin(id, max ? "normal" : "max")} />
              {onClose && <HeadBtn icon="close" title="Close (View menu brings it back)" onClick={onClose} />}
            </div>
          </header>
          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
          {floating && <div onPointerDown={resize} title="Drag to resize"
            className="absolute bottom-0 right-0 z-10 h-3.5 w-3.5 cursor-nwse-resize rounded-tl bg-white/10 hover:bg-cyan-glow/50" />}
        </motion.section>
      )}
    </AnimatePresence>
  );
}

// Kept for the panels that still render one: the tray (PanelTray) shows every minimised panel instead.
export function PanelIcon() {
  return null;
}

// One place for every minimised panel: a column of icons at the left edge, above the status bar.
export function PanelTray() {
  const panels = useStore((s) => s.panels);
  const win = useStore((s) => s.win);
  const setWin = useStore((s) => s.setWin);
  const ids = Object.keys(win).filter((k) => panels[k] && win[k] === "min" && k !== "orchestrator" && PANEL_META[k]);
  if (!ids.length) return null;
  return (
    <div className="pointer-events-auto absolute bottom-10 left-3 z-30 flex flex-col gap-1.5">
      {ids.map((k) => (
        <motion.button key={k} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} onClick={() => setWin(k, "normal")}
          title={`${PANEL_META[k].title} (click to open)`} className="glass group flex h-10 items-center gap-2 rounded-xl px-1.5">
          <IconTile icon={PANEL_META[k].icon || "panel"} big />
          <span className="hidden pr-2 text-[11.5px] text-white group-hover:inline">{PANEL_META[k].title}</span>
        </motion.button>))}
    </div>
  );
}
