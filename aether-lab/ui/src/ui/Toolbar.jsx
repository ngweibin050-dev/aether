import { motion } from "framer-motion";
import { useStore } from "../store";
import Icon from "./Icon";
import { useLayout } from "./layout";

const TOOLS = [
  ["select", "select", "Select box (B, drag)"], ["cursor", "cursor", "3D cursor (Shift+RMB)"],
  ["move", "move", "Move gizmo (G = free move)"], ["rotate", "rotate", "Rotate gizmo (R)"], ["scale", "scale", "Scale gizmo (S)"],
  ["measure", "ruler", "Measure (click two points)"],
];

export default function Toolbar() {
  const tool = useStore((s) => s.activeTool);
  const open = useStore((s) => s.panels.toolbar);
  const lay = useLayout();
  const st = useStore.getState();
  if (!open) return null;
  return (
    <motion.nav initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
      className="glass pointer-events-auto absolute z-20 transition-[left] duration-300 flex flex-col gap-1 rounded-xl p-1" style={{ left: lay.toolLeft, top: lay.toolTop }}>
      {TOOLS.map(([k, ic, t]) => (
        <button key={k} title={t} onClick={() => st.setTool(k)}
          className={`grid h-8 w-8 place-items-center rounded-lg transition active:scale-95 ${tool === k ? "bg-cyan-glow/20 text-cyan-glow shadow-inner" : "text-white/70 hover:bg-white/[0.08] hover:text-white"}`}>
          <Icon name={ic} /></button>
      ))}
    </motion.nav>
  );
}
