import { motion } from "framer-motion";
import { useStore } from "../store";
import Icon from "./Icon";

// What an empty project shows in the middle of the desk: how to start, in three steps, each with a working button.
export default function EmptyDesk() {
  const empty = useStore((s) => (s.state?.parts || []).length === 0);
  const busy = useStore((s) => s.busy.chat);
  const st = useStore();
  if (!empty || busy) return null;
  const focusChat = (text) => {
    st.setPanel("orchestrator", true);
    st.setWin("orchestrator", "normal");
    setTimeout(() => {
      const el = document.getElementById("ai-input");
      if (!el) return;
      if (text) {
        const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
        set.call(el, text);
        el.dispatchEvent(new Event("input", { bubbles: true }));
      }
      el.focus();
    }, 80);
  };
  const steps = [
    ["upload", "Drop a drawing or 3D file", "A blueprint, patent drawing, photo, PDF, GLB, STL or STEP. Drag it into the chat, or:",
     "Attach a file", () => { st.setPanel("orchestrator", true); st.setWin("orchestrator", "normal"); setTimeout(() => document.getElementById("photo-input")?.click(), 80); }],
    ["sparkle", "Or describe what to build", "Muse Spark builds it from parametric parts, beside anything already on the desk.",
     "Make a simple robot arm", () => focusChat("Make a simple robot arm with a base, two links and a gripper")],
    ["layers", "Then refine, inspect, export", "Ask for changes (\"make the windows blue\"), \"explain this machine\", a technical drawing, or a GLB / STEP file.",
     "Try a recorded demo", () => st.playRecorded("D")],
  ];
  return (
    <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="glass pointer-events-auto w-[min(560px,90vw)] rounded-2xl p-5">
        <div className="font-display text-[16px] font-bold text-white">This project is empty</div>
        <div className="mt-0.5 text-[12px] text-slate-400">Everything you do here is saved to the project automatically.</div>
        <div className="mt-4 space-y-3">
          {steps.map(([ic, t, d, b, f], i) => (
            <div key={t} className="flex gap-3">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-cyan-glow/30 font-mono text-[12px] text-cyan-glow">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-white">{t}</div>
                <div className="text-[11.5px] text-slate-400">{d}</div>
                <button onClick={f} className="btn mt-1.5 !py-1 text-[11.5px]"><Icon name={ic} />{b}</button>
              </div>
            </div>))}
        </div>
      </motion.div>
    </div>
  );
}
