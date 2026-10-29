import { useEffect } from "react";
import { useStore } from "./store";

export default function useShortcuts() {
  useEffect(() => {
    const onKey = (e) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
      const s = useStore.getState();
      const k = e.key.toLowerCase();
      const ctrl = e.ctrlKey || e.metaKey;
      if (k === "tab") { e.preventDefault(); s.setMode(s.mode === "laptop" ? "hand" : "laptop"); return; }
      if (ctrl && k === "z") { e.preventDefault(); e.shiftKey ? s.redoOnce() : s.undoOnce(); return; }
      if (ctrl && k === "y") { e.preventDefault(); s.redoOnce(); return; }
      if (e.shiftKey && k === "d") { e.preventDefault(); s.duplicate(); return; }
      if (ctrl) return;
      if (k === "g") s.setGizmo("translate");
      else if (k === "r") s.setGizmo("rotate");
      else if (k === "s") s.setGizmo("scale");
      else if (["x", "y", "z"].includes(k)) s.setAxis(s.axis === k ? null : k);
      else if (k === "escape") { s.setAxis(null); s.select(null); }
      else if ((k === "delete" || k === "backspace") && s.state?.selected) s.tool("delete_part", { id: s.state.selected });
      else if (k === "h" && s.state?.selected) {
        const p = s.state.parts.find((x) => x.id === s.state.selected);
        s.tool("update_part", { id: p.id, visible: p.visible === false });
      }
      else if (k === "enter") s.tool("make_hologram").then(() => s.tool("focus_sweep", { steps: 9 }));
      else if (k === "[") s.setPanel("left");
      else if (k === "]") s.setPanel("right");
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);
}
