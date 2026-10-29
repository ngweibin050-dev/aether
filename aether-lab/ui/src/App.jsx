import { useEffect } from "react";
import Viewport from "./scene/Viewport";
import TopBar from "./ui/TopBar";
import LeftPanel from "./ui/LeftPanel";
import RightPanel from "./ui/RightPanel";
import ResultsDock from "./ui/ResultsDock";
import Assistant from "./ui/Assistant";
import Hud from "./ui/Hud";
import HandTracker from "./hand/HandTracker";
import useShortcuts from "./useShortcuts";
import { useStore } from "./store";

export default function App() {
  const ready = useStore((s) => !!s.state);
  const mode = useStore((s) => s.mode);
  useShortcuts();
  useEffect(() => { useStore.getState().load().catch((e) => useStore.getState().notify(e.message, "error")); }, []);
  useEffect(() => { if (mode === "hand") useStore.getState().setPanel("left", false); }, [mode]);
  return (
    <div className="bg-aurora relative h-full w-full overflow-hidden">
      <div className="absolute inset-0">{ready && <Viewport />}</div>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_55%,rgba(0,0,0,.55))]" />
      <div className="pointer-events-none absolute inset-0">
        <TopBar />
        {ready && <><Hud /><LeftPanel /><RightPanel /><ResultsDock /><HandTracker /><Assistant /></>}
      </div>
      {!ready && <div className="absolute inset-0 grid place-items-center"><div className="busy-sheen rounded-2xl border border-line px-6 py-3 font-display text-slate-300">Connecting to the AETHER physics server…</div></div>}
    </div>
  );
}
