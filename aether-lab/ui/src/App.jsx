import { useEffect } from "react";
import Viewport from "./scene/Viewport";
import Interaction from "./scene/Interaction";
import MenuBar from "./ui/MenuBar";
import Orchestrator from "./ui/Orchestrator";
import Outliner from "./ui/Outliner";
import PhysicsPanel from "./ui/PhysicsPanel";
import Toolbar from "./ui/Toolbar";
import NavGizmo from "./ui/NavGizmo";
import Dock from "./ui/Dock";
import Menus from "./ui/Menus";
import StatusBar from "./ui/StatusBar";
import HandTracker, { AirCursor } from "./hand/HandTracker";
import useShortcuts from "./useShortcuts";
import { useStore } from "./store";

export default function App() {
  const ready = useStore((s) => !!s.state);
  useShortcuts();
  useEffect(() => { useStore.getState().load().catch((e) => useStore.getState().notify(e.message, "error")); }, []);
  return (
    <div className="bg-space relative h-full w-full overflow-hidden">
      <div className="absolute inset-0">{ready && <Viewport />}</div>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_60%,rgba(0,0,0,.6))]" />
      <div className="pointer-events-none absolute inset-0">
        <MenuBar />
        {ready && <>
          <Orchestrator /><Outliner /><PhysicsPanel /><Toolbar /><NavGizmo /><Dock /><HandTracker /><StatusBar />
        </>}
      </div>
      {ready && <><Interaction /><Menus /><AirCursor /></>}
      {!ready && <div className="absolute inset-0 grid place-items-center"><div className="busy-sheen rounded-2xl border border-white/10 px-6 py-3 text-silver">Connecting to the AETHER physics server…</div></div>}
    </div>
  );
}
