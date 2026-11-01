import { AnimatePresence, motion } from "framer-motion";
import { HEAVY, useStore } from "../store";
import { SineLoader } from "./Charts";

const HINTS = {
  laptop: [["LMB", "select / box"], ["⇧LMB", "add"], ["MMB · Alt+LMB", "orbit"], ["⇧MMB", "pan"], ["Wheel", "zoom"], ["RMB", "menu"], ["⇧A", "add"], ["G R S", "transform"], ["F3", "search"]],
  hand: [["point", "air cursor"], ["pinch", "click / grab"], ["pinch empty", "orbit"], ["2-hand pinch", "rotate·scale / explode"], ["V-sign (2 fingers)", "hand menu"], ["fist", "deselect"], ["both palms", "hologram"]],
};

export default function StatusBar() {
  const mode = useStore((s) => s.mode);
  const parts = useStore((s) => s.state?.parts.length || 0);
  const sel = useStore((s) => s.selection.length);
  const modal = useStore((s) => s.modal);
  const toast = useStore((s) => s.toast);
  const busy = useStore((s) => s.busy);
  const compute = useStore((s) => s.compute);
  const running = HEAVY.find((h) => busy[h]);
  return (
    <>
      <footer className="pointer-events-auto absolute inset-x-0 bottom-0 z-30 flex h-[22px] items-center gap-4 overflow-hidden whitespace-nowrap border-t border-white/[0.06] bg-[#04060b]/90 px-3 text-[10.5px] text-silver">
        {HINTS[mode].map(([k, v]) => <span key={k} className="flex items-center gap-1.5"><span className="kbd">{k}</span>{v}</span>)}
        <span className="hidden min-w-0 truncate font-mono text-[10px] uppercase tracking-[0.12em] text-cyan-glow/60 2xl:inline">Screen render · hologram in Physics panel</span>
        <span className="kbd ml-auto">⇧Tab</span><span className="-ml-2.5 whitespace-nowrap">hide panels</span>
        <span className="whitespace-nowrap font-mono">Objects {sel}/{parts}</span>
        <span className="whitespace-nowrap font-mono">{mode === "hand" ? "Hand tracking" : "Laptop"}</span>
      </footer>
      <AnimatePresence>
        {modal && (
          <motion.div style={{ x: "-50%" }} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="pointer-events-none absolute left-1/2 top-[60px] z-40 rounded-lg border border-cyan-glow/30 bg-black/70 px-3 py-1.5 font-mono text-[12px] text-cyan-50 backdrop-blur-xl">
            {modal.text} <span className="ml-3 text-[10.5px] text-silver">XYZ axis · type number · Ctrl snap · ↵ ok · Esc cancel</span>
          </motion.div>
        )}
        {running && !modal && (
          <motion.div style={{ x: "-50%" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="pointer-events-none absolute left-1/2 top-[60px] z-40 rounded-full border border-cyan-glow/20 bg-black/55 px-3 py-1 backdrop-blur-xl">
            <SineLoader label={`${compute === "modal" ? "Modal GPU" : "physics engine"} · ${running.replace(/_/g, " ")}`} />
          </motion.div>
        )}
        {toast && (
          <motion.div key={toast.t} style={{ x: "-50%" }} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={`pointer-events-none absolute left-1/2 top-[100px] z-50 max-w-[560px] rounded-xl border px-4 py-2 text-[12px] backdrop-blur-xl ${toast.kind === "error" ? "border-bad/40 bg-bad/15 text-rose-100" : "border-cyan-glow/30 bg-black/60 text-cyan-50"}`}>{toast.text}</motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
