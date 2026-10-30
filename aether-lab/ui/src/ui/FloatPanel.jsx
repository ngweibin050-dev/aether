import { useEffect, useState } from "react";
import { AnimatePresence, motion, useDragControls, useMotionValue } from "framer-motion";
import Icon from "./Icon";

const load = (k) => { try { return JSON.parse(localStorage.getItem("aether.panel." + k)) || {}; } catch { return {}; } };
const save = (k, v) => { try { localStorage.setItem("aether.panel." + k, JSON.stringify(v)); } catch { /* private mode */ } };

// A floating spatial HUD: drag it by its header, fold it to its title, it remembers where you left it.
export default function FloatPanel({ id, title, icon, open = true, onClose, className = "", style, right, children, busy }) {
  const saved = load(id);
  const x = useMotionValue(saved.x || 0), y = useMotionValue(saved.y || 0);
  const [folded, setFolded] = useState(!!saved.folded);
  const drag = useDragControls();
  useEffect(() => save(id, { x: x.get(), y: y.get(), folded }), [folded, id, x, y]);
  return (
    <AnimatePresence>
      {open && (
        <motion.section
          drag dragListener={false} dragControls={drag} dragMomentum={false} dragElastic={0}
          onDragEnd={() => save(id, { x: x.get(), y: y.get(), folded })}
          initial={{ opacity: 0, scale: 0.96, filter: "blur(6px)" }} animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          exit={{ opacity: 0, scale: 0.96, filter: "blur(6px)" }} transition={{ type: "spring", stiffness: 320, damping: 30, filter: { duration: 0.25, ease: "easeOut" } }}
          style={{ x, y, ...style }}
          className={`glass pointer-events-auto absolute z-20 flex flex-col overflow-hidden ${className} ${folded ? "!h-auto" : ""}`}>
          <header onPointerDown={(e) => drag.start(e)}
            className="group flex cursor-grab items-center gap-2 px-3.5 py-2.5 active:cursor-grabbing">
            {icon && <Icon name={icon} className="h-3.5 w-3.5 text-cyan-glow" />}
            <span className="font-display text-[12.5px] font-semibold tracking-wide text-white">{title}</span>
            {busy && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-glow shadow-glow" />}
            <div className="ml-auto flex items-center gap-1" onPointerDown={(e) => e.stopPropagation()}>
              {right}
              <button className="grid h-6 w-6 place-items-center rounded-md text-silver hover:bg-white/10 hover:text-white" title={folded ? "Expand" : "Fold"}
                onClick={() => setFolded(!folded)}><Icon name={folded ? "plus" : "min"} className="h-3.5 w-3.5" /></button>
              {onClose && <button className="grid h-6 w-6 place-items-center rounded-md text-silver hover:bg-white/10 hover:text-white" title="Close"
                onClick={onClose}><Icon name="close" className="h-3.5 w-3.5" /></button>}
            </div>
          </header>
          {!folded && <div className="flex min-h-0 flex-1 flex-col">{children}</div>}
          <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-cyan-glow/[0.06]" />
        </motion.section>
      )}
    </AnimatePresence>
  );
}
