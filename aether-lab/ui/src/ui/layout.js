import { useStore } from "../store";

// Fixed lab layout: Scene on the left, Physics on the right, the AI orchestrator along the bottom between them.
// A minimised side panel becomes a tab in its corner and the tools next to it slide to the screen edge.
export const L = { top: 60, bottom: 30, gap: 12, left: 300, right: 340, icon: 44 };

export function useLayout() {
  const panels = useStore((s) => s.panels);
  const win = useStore((s) => s.win);
  const rects = useStore((s) => s.rects);
  // a floating panel does not push the tools aside: only a docked one does
  const leftOn = panels.outliner && win.outliner !== "min" && !rects.outliner;
  const rightOn = panels.physics && win.physics !== "min" && !rects.physics;
  const leftTab = false;                         // minimised panels live in the panel tray, not at the edges
  const rightTab = false;
  return {
    leftOn, rightOn, leftTab, rightTab, win, panels,
    // tools sit next to the panel, or next to its icon when it is minimised, or at the edge when it is closed
    toolLeft: leftOn ? L.left + 2 * L.gap : leftTab ? L.icon + 2 * L.gap - 4 : L.gap,
    toolTop: L.top,
    navRight: rightOn ? L.right + 2 * L.gap : rightTab ? L.icon + 2 * L.gap - 2 : L.gap + 2,
    navTop: L.top + 2,
    midLeft: leftOn ? L.left + 2 * L.gap : L.gap,
    midRight: rightOn ? L.right + 2 * L.gap : L.gap,
  };
}

export const MAX_STYLE = { top: L.top, left: L.gap, right: L.gap, bottom: L.bottom, zIndex: 35 };
