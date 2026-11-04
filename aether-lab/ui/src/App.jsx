import { useEffect } from "react";
import Viewport from "./scene/Viewport";
import Interaction from "./scene/Interaction";
import MenuBar from "./ui/MenuBar";
import Orchestrator from "./ui/Orchestrator";
import Outliner from "./ui/Outliner";
import PhysicsPanel from "./ui/PhysicsPanel";
import CadPanel from "./ui/CadPanel";
import AssemblyPanel from "./ui/AssemblyPanel";
import DrawingPanel from "./ui/DrawingPanel";
import HistoryPanel from "./ui/HistoryPanel";
import OpticsFigure from "./ui/OpticsFigure";
import Lightbox, { useLightboxListener } from "./ui/Lightbox";
import FilePreview from "./ui/FilePreview";
import { PanelTray } from "./ui/FloatPanel";
import EmptyDesk from "./ui/EmptyDesk";
import NavGizmo from "./ui/NavGizmo";
import Dock from "./ui/Dock";
import ExplainPlayer, { RecordedBanner } from "./ui/ExplainPlayer";
import Menus from "./ui/Menus";
import StatusBar from "./ui/StatusBar";
import HandTracker, { AirCursor } from "./hand/HandTracker";
import useShortcuts from "./useShortcuts";
import { useStore } from "./store";

export default function App() {
  const ready = useStore((s) => !!s.state);
  useShortcuts();
  useLightboxListener();
  useEffect(() => { useStore.getState().load().catch((e) => useStore.getState().notify(e.message, "error")); }, []);
  useEffect(() => {
    const block = (e) => {
      const t = e.target;
      const editable = t.closest?.("input, textarea, [contenteditable=true]");
      const selected = String(getSelection?.() || "").length > 0;   // selected text: the browser menu can copy it
      if (!editable && !selected) e.preventDefault();
    };
    addEventListener("contextmenu", block);
    const sync = setInterval(() => useStore.getState().pollJobs(), 3000);   // background jobs + other tabs
    return () => { removeEventListener("contextmenu", block); clearInterval(sync); };
  }, []);
  return (
    <div className="bg-space relative h-full w-full overflow-hidden">
      <div className="absolute inset-0">{ready && <Viewport />}</div>
      <div className="vignette-overlay pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_60%,rgba(0,0,0,.6))]" />
      <div className="pointer-events-none absolute inset-0">
        <MenuBar />
        {ready && <>
          <Orchestrator /><Outliner /><PhysicsPanel /><CadPanel /><AssemblyPanel /><DrawingPanel /><HistoryPanel /><OpticsFigure /><NavGizmo /><Dock /><ExplainPlayer /><RecordedBanner /><HandTracker /><EmptyDesk /><PanelTray /><StatusBar />
        </>}
      </div>
      {ready && <><Interaction /><Menus /><AirCursor /></>}
      <Lightbox /><FilePreview />
      {!ready && <div className="absolute inset-0 grid place-items-center"><div className="busy-sheen rounded-2xl border border-white/10 px-6 py-3 text-silver">Connecting to the AETHER physics server…</div></div>}
    </div>
  );
}
