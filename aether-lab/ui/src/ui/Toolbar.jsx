import { motion } from "framer-motion";
import { useStore } from "../store";
import Icon from "./Icon";

const TOOLS = [
  ["select", "select", "Select box (B, drag)"], ["cursor", "cursor", "3D cursor (Shift+RMB)"],
  ["move", "move", "Move gizmo (G = free move)"], ["rotate", "rotate", "Rotate gizmo (R)"], ["scale", "scale", "Scale gizmo (S)"],
  ["measure", "ruler", "Measure (click two points)"],
];

export default function Toolbar() {
  const tool = useStore((s) => s.activeTool);
  const open = useStore((s) => s.panels.toolbar);
  const orch = useStore((s) => s.panels.orchestrator || s.panels.outliner);
  const st = useStore.getState();
  if (!open) return null;
  return (
    <motion.nav initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
      className="glass pointer-events-auto absolute top-[60px] z-20 flex flex-col gap-1 rounded-xl p-1" style={{ left: orch ? 332 : 12 }}>
      {TOOLS.map(([k, ic, t]) => (
        <button key={k} title={t} onClick={() => st.setTool(k)}
          className={`grid h-8 w-8 place-items-center rounded-lg transition active:scale-95 ${tool === k ? "bg-cyan-glow/20 text-cyan-glow shadow-inner" : "text-white/70 hover:bg-white/[0.08] hover:text-white"}`}>
          <Icon name={ic} /></button>
      ))}
      <span className="mx-1.5 my-0.5 h-px bg-white/10" />
      <button title="Add (Shift+A)" onClick={(e) => st.setMenu({ kind: "add", x: e.clientX + 30, y: e.clientY })}
        className="grid h-8 w-8 place-items-center rounded-lg text-white/70 hover:bg-white/[0.08] hover:text-white"><Icon name="plus" /></button>
    </motion.nav>
  );
}
