import { useEffect } from "react";
import { useStore } from "./store";
import { run } from "./commands";
import { active as modalActive, startModal, lastMouse } from "./scene/modal";
import { view } from "./scene/registry";

// Blender 4.x default keymap (object mode), mapped onto AETHER's commands.
// Laptops without a numpad: the number row works like the numpad ("Emulate Numpad").
export default function useShortcuts() {
  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || modalActive()) return;
      const s = useStore.getState();
      if (s.menu && e.key !== "Escape") return;
      const k = e.key.toLowerCase(), code = e.code;
      const ctrl = e.ctrlKey || e.metaKey, alt = e.altKey, shift = e.shiftKey;
      const at = { x: lastMouse.x, y: lastMouse.y };
      const go = (id) => { e.preventDefault(); run(id); };
      const menu = (kind) => { e.preventDefault(); s.setMenu({ kind, ...at }); };

      // numpad (or number row) views
      const num = code.startsWith("Numpad") ? code.slice(6) : code.startsWith("Digit") ? code.slice(5) : null;
      if (num !== null && !alt) {
        const map = { 1: ctrl ? "view.back" : "view.front", 3: ctrl ? "view.left" : "view.right", 7: ctrl ? "view.bottom" : "view.top",
          5: "view.ortho", 0: "view.eye", Decimal: "view.frame" };
        if (map[num]) return go(map[num]);
        const orb = { 2: [0, 15], 8: [0, -15], 4: [-15, 0], 6: [15, 0] }[num];
        if (orb) { e.preventDefault(); return view.nav?.orbit(orb[0] * Math.PI / 180, orb[1] * Math.PI / 180); }
        if (num === "Add") { e.preventDefault(); return view.nav?.zoom(0.85); }
        if (num === "Subtract") { e.preventDefault(); return view.nav?.zoom(1.18); }
      }
      if (code === "NumpadDecimal" || (k === "." && !shift && !ctrl)) return go("view.frame");
      if (k === "home") return go("view.all");
      if (k === "escape") { s.setMenu(null); s.setDock(null); return; }
      if (k === "tab") return go("view.mode");
      if (k === "f3") return menu("search");
      if (k === "f2") return go("edit.rename");
      if (k === "f12") return go(ctrl ? "holo.prop" : "holo.calc");
      if (k === "`" || k === "~") return menu("pie-view");

      if (ctrl) {
        if (k === "z") return go(shift ? "edit.redo" : "edit.undo");
        if (k === "y") return go("edit.redo");
        if (k === "s") return go("file.save");
        if (k === "o") return go("file.open");
        if (k === "i") return go("sel.invert");
        if (k === "p") return go("obj.parent");
        if (k === " ") return go("view.panels");
        return;
      }
      if (alt) {
        const m = { a: "sel.none", g: "obj.clearloc", r: "obj.clearrot", s: "obj.clearscale", p: "obj.unparent", h: "obj.unhide",
          z: "in.xray", x: "in.secx", y: "in.secy" }[k];
        if (m) return go(m);
        return;
      }
      if (shift) {
        if (k === "a") return menu("add");
        if (k === "d") return go("obj.dup");
        if (k === "s") return menu("pie-snap");
        if (k === "h") return go("obj.hideothers");
        if (k === "g") return go("sel.parent");
        if (k === "]" || k === "}") return go("sel.children");
        return;
      }
      if (["g", "r", "s"].includes(k) && s.selection.length) { e.preventDefault(); return startModal(k.toUpperCase()); }
      const m = { a: "sel.all", h: "obj.hide", e: "in.explode", "/": "in.isolate", t: "view.toolbar", n: "view.sidebar" }[k];
      if (m) return go(m);
      if (k === "b") { e.preventDefault(); return s.setTool("select"); }
      if (k === "z") return menu("pie-shading");
      if ((k === "x" || k === "delete") && s.selection.length) return k === "x" ? menu("delete") : go("obj.delete");
      if (k === "w") { e.preventDefault(); const order = ["select", "cursor", "move", "rotate", "scale", "measure"]; return s.setTool(order[(order.indexOf(s.activeTool) + 1) % order.length]); }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);
}
