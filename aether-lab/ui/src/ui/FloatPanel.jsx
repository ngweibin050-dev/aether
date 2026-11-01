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

// A docked lab panel, placed by the layout (style). Like a design app's panels: minimise collapses it to an icon
// at the screen edge (the viewport gets the space), maximise spreads it over the viewport, close removes it.
const DOCK = { outliner: "left", physics: "right", orchestrator: "bottom" };

export default function FloatPanel({ id, title, icon, open = true, onClose, className = "", style, right, children, busy, resizeTop }) {
  const mode = useStore((s) => s.win[id] || "normal");
  const setWin = useStore((s) => s.setWin);
  const max = mode === "max";
  return (
    <AnimatePresence>
      {open && mode !== "min" && (
        <motion.section key={id} data-dock={DOCK[id]} data-mode={mode}
          initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }}
          transition={{ type: "spring", stiffness: 360, damping: 32 }}
          style={max ? MAX_STYLE : style}
          className={`glass pointer-events-auto absolute z-20 flex flex-col overflow-hidden ${max ? "" : className}`}>
          {resizeTop && !max && (
            <div title="Drag to resize · double-click to reset" onPointerDown={resizeTop.start} onDoubleClick={resizeTop.reset}
              className="group absolute inset-x-0 top-0 z-10 flex h-2.5 cursor-ns-resize justify-center">
              <span className="mt-[3px] h-1 w-10 rounded-full bg-white/15 transition group-hover:bg-cyan-glow/70" />
            </div>)}
          <header className="flex min-w-0 items-center gap-2 px-3.5 py-2.5" onDoubleClick={() => setWin(id, max ? "normal" : "max")}>
            {icon && <IconTile icon={icon} />}
            <span className="truncate font-display text-[13px] font-bold tracking-tight text-white">{title}</span>
            {busy && <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-cyan-glow shadow-glow" />}
            <div className="ml-auto flex shrink-0 items-center gap-1" onDoubleClick={(e) => e.stopPropagation()}>
              {right}
              <HeadBtn icon="min" title="Minimise to the edge" onClick={() => setWin(id, "min")} />
              <HeadBtn icon={max ? "restore" : "max"} title={max ? "Restore" : "Maximise"} onClick={() => setWin(id, max ? "normal" : "max")} />
              {onClose && <HeadBtn icon="close" title="Close (View menu brings it back)" onClick={onClose} />}
            </div>
          </header>
          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}

// What a minimised panel leaves behind: an icon at the screen edge; click to open it again.
export function PanelIcon({ id, title, icon, style, busy }) {
  const show = useStore((s) => s.panels[id] && s.win[id] === "min");
  const setWin = useStore((s) => s.setWin);
  if (!show) return null;
  return (
    <motion.button initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} onClick={() => setWin(id, "normal")}
      title={`${title} (click to open)`} style={style}
      className="glass pointer-events-auto absolute z-20 grid h-11 w-11 place-items-center rounded-xl">
      <IconTile icon={icon} big />
      {busy && <span className="absolute right-1 top-1 h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-glow shadow-glow" />}
    </motion.button>
  );
}
