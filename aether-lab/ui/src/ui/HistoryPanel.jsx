import { useStore } from "../store";
import FloatPanel from "./FloatPanel";
import { L, useLayout } from "./layout";
import Icon from "./Icon";

// The project's undo history (history.py on the server): every assistant turn, edit and build is one step. Undoing a
// step puts back only the parts it changed; a step that later steps built on is undone with them (said in the toast).

const SOURCE = { ai: ["AI", "text-violet-300"], edit: ["edit", "text-sky-300"], build: ["build", "text-emerald-300"],
  auto: ["auto", "text-slate-500"] };

const ago = (t) => {
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 60 ? "now" : s < 3600 ? `${Math.round(s / 60)} min` : s < 86400 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} d`;
};

export default function HistoryPanel() {
  const open = useStore((s) => s.panels.history);
  const h = useStore((s) => s.history);
  const busy = useStore((s) => s.busy.history);
  const st = useStore();
  const lay = useLayout();
  const style = { right: lay.navRight + 56, top: L.top + 40, width: 360, height: "min(520px, 60vh)" };
  const Row = ({ x, redo }) => {
    const [tag, cls] = SOURCE[x.source] || [x.source, "text-slate-400"];
    return (
      <div className={`group flex items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] ${redo ? "opacity-55" : "hover:bg-white/[0.05]"}`}>
        <span className={`w-9 shrink-0 font-mono text-[9.5px] uppercase ${cls}`}>{tag}</span>
        <span className={`min-w-0 flex-1 truncate ${redo ? "line-through" : ""}`} title={x.label}>{x.label}</span>
        <span className="shrink-0 font-mono text-[9.5px] text-slate-500" title={`${x.parts} part(s) changed`}>{ago(x.t)}</span>
        {!redo && <button type="button" disabled={busy} title="Undo this step (only the parts it changed go back)"
          onClick={() => st.undoOnce(x.id)}
          className="shrink-0 rounded-md px-1.5 py-0.5 text-[10.5px] text-slate-400 opacity-0 transition hover:bg-white/10 hover:text-white group-hover:opacity-100 disabled:opacity-30">
          undo</button>}
      </div>);
  };
  return (
    <FloatPanel id="history" title="History · undo / redo" icon="undo" open={open} busy={busy} onClose={() => st.setPanel("history", false)} style={style}>
      <div className="flex shrink-0 gap-1.5 px-3 pb-2">
        <button type="button" className="btn flex-1" disabled={busy || !h.can_undo} onClick={() => st.undoOnce()}><Icon name="undo" /> Undo</button>
        <button type="button" className="btn flex-1" disabled={busy || !h.can_redo} onClick={() => st.redoOnce()}><Icon name="redo" /> Redo</button>
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {h.redo.map((x) => <Row key={"r" + x.id} x={x} redo />)}
        {h.steps.length ? h.steps.map((x) => <Row key={x.id} x={x} />)
          : <div className="px-2 py-3 text-[12px] text-slate-500">Nothing to undo yet in this project.</div>}
        <div className="mt-2 px-2 text-[10.5px] leading-relaxed text-slate-500">
          Undo puts back only the parts that step changed: other models stay as they are. "auto" steps (the CAD detail pass)
          are skipped by Ctrl+Z.</div>
      </div>
    </FloatPanel>
  );
}
