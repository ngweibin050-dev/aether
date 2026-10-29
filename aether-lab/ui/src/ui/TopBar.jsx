import { useStore } from "../store";
import Icon from "./Icon";

export default function TopBar() {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const compute = useStore((s) => s.compute);
  const undo = useStore((s) => s.undo.length);
  const redo = useStore((s) => s.redo.length);
  const { undoOnce, redoOnce } = useStore.getState();
  return (
    <header className="pointer-events-auto absolute inset-x-0 top-0 z-30 flex items-center gap-4 px-5 py-3">
      <div className="flex items-center gap-3">
        <div className="relative h-9 w-9 rounded-xl bg-[conic-gradient(from_200deg,#5fe1ff,#a78bfa,#5fe1ff)] shadow-glow">
          <div className="absolute inset-[3px] rounded-[9px] bg-ink-950" />
          <div className="absolute inset-[11px] rounded-full border-2 border-cyan-glow shadow-glow" />
        </div>
        <div className="leading-none">
          <div className="font-display text-[19px] font-bold tracking-[0.18em]">AETHER<span className="ml-2 font-normal tracking-[0.08em] text-cyan-glow">2.0</span></div>
          <div className="mt-1 text-[11.5px] text-slate-400">Holographic design desk</div>
        </div>
      </div>

      <div className="mx-auto flex items-center gap-1 rounded-2xl border border-line bg-black/30 p-1 backdrop-blur-xl">
        {[["laptop", "laptop", "Laptop mode"], ["hand", "hand", "Hand mode"]].map(([m, ic, label]) => (
          <button key={m} onClick={() => setMode(m)}
            className={`flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-[12.5px] font-medium transition ${mode === m ? "bg-gradient-to-r from-cyan-glow/25 to-violet-glow/25 text-white shadow-glow" : "text-slate-400 hover:text-slate-200"}`}>
            <Icon name={ic} />{label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button className="btn-icon" title="Undo (Ctrl+Z)" disabled={!undo} onClick={undoOnce}><Icon name="undo" /></button>
        <button className="btn-icon" title="Redo (Ctrl+Shift+Z)" disabled={!redo} onClick={redoOnce}><Icon name="redo" /></button>
        <span className="chip"><i className="h-1.5 w-1.5 rounded-full bg-ok shadow-[0_0_8px_#5eead4]" />Muse Spark</span>
        <span className="chip"><i className={`h-1.5 w-1.5 rounded-full ${compute === "modal" ? "bg-violet-glow" : "bg-cyan-glow"}`} />physics · {compute === "modal" ? "Modal GPU" : "this PC"}</span>
        <span className="chip border-warn/30 text-warn">Simulation · not a built display</span>
      </div>
    </header>
  );
}
