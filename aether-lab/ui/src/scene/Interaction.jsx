// Mouse in the viewport, Blender style: click select (Shift adds), drag = box select (Ctrl subtracts),
// Shift+RMB places the 3D cursor, RMB opens the object context menu, double-click selects the whole assembly.
import { useEffect, useState } from "react";
import * as THREE from "three";
import { useStore } from "../store";
import { objects, view } from "./registry";
import { active as modalActive } from "./modal";

const ray = new THREE.Raycaster();
const AXI = { x: 0, y: 1, z: 2 };

export function pick(x, y) {
  if (!view.camera || !view.dom) return null;
  const r = view.dom.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2((x - r.left) / r.width * 2 - 1, -((y - r.top) / r.height) * 2 + 1), view.camera);
  const meshes = [];
  for (const [, o] of objects) o?.children.forEach((c) => c.isMesh && c.userData.part && meshes.push(c));
  const v = useStore.getState().view;
  const visible = (m) => { let o = m; while (o) { if (!o.visible) return false; o = o.parent; } return true; };
  for (const h of ray.intersectObjects(meshes, false)) {
    if (!visible(h.object)) continue;
    if (v.section) {
      const d = h.point.getComponent(AXI[v.section]) - v.section_mm;
      if (v.section_flip ? d < 0 : d > 0) continue;
    }
    return { id: h.object.userData.part, point: h.point.toArray().map((n) => +n.toFixed(2)) };
  }
  // nothing hit: the desk plane z = 0
  const p = new THREE.Vector3();
  return ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), p) ? { id: null, point: p.toArray().map((n) => +n.toFixed(2)) } : null;
}

function inBox(rect) {
  const r = view.dom.getBoundingClientRect(), ids = [];
  for (const [id, o] of objects) {
    if (!o) continue;
    const mesh = o.children.find((c) => c.isMesh && c.userData.part);
    if (!mesh?.geometry.boundingBox) continue;
    let vis = true; for (let q = o; q; q = q.parent) if (!q.visible) vis = false;
    if (!vis) continue;
    const c = mesh.geometry.boundingBox.getCenter(new THREE.Vector3()).applyMatrix4(mesh.matrixWorld).project(view.camera);
    const x = (c.x + 1) / 2 * r.width + r.left, y = (1 - c.y) / 2 * r.height + r.top;
    if (x >= rect.x0 && x <= rect.x1 && y >= rect.y0 && y <= rect.y1 && c.z < 1) ids.push(id);
  }
  return ids;
}

export default function Interaction() {
  const [rect, setRect] = useState(null);
  useEffect(() => {
    let down = null;
    const st = useStore.getState;
    const onDown = (e) => {
      if (e.target !== view.dom || modalActive()) return;
      if (e.button === 2) {
        if (e.shiftKey) { const h = pick(e.clientX, e.clientY); h && useStore.setState({ cursor3d: h.point }); }
        else st().setMenu({ kind: "context", x: e.clientX, y: e.clientY });
        return;
      }
      if (e.button !== 0 || e.altKey || view.gizmo?.axis) return;
      st().setMenu(null);
      down = { x: e.clientX, y: e.clientY, shift: e.shiftKey, ctrl: e.ctrlKey || e.metaKey, box: false };
    };
    const onMove = (e) => {
      if (!down || modalActive()) return;
      if (!down.box && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5 && ["select", "move", "rotate", "scale"].includes(st().activeTool)) down.box = true;
      if (down.box) setRect({ x0: Math.min(down.x, e.clientX), y0: Math.min(down.y, e.clientY), x1: Math.max(down.x, e.clientX), y1: Math.max(down.y, e.clientY) });
    };
    const onUp = (e) => {
      if (!down) return;
      const d = down; down = null;
      if (d.box) {
        const r = { x0: Math.min(d.x, e.clientX), y0: Math.min(d.y, e.clientY), x1: Math.max(d.x, e.clientX), y1: Math.max(d.y, e.clientY) };
        const ids = inBox(r);
        setRect(null);
        if (d.ctrl) st().selectMany(st().selection.filter((id) => !ids.includes(id)));
        else st().selectMany(ids, d.shift);
        return;
      }
      const h = pick(e.clientX, e.clientY);
      const tool = st().activeTool;
      if (tool === "cursor") { if (h) useStore.setState({ cursor3d: h.point }); return; }
      if (tool === "measure") {
        if (!h) return;
        const m = st().measure;
        useStore.setState({ measure: !m?.a || m.b ? { a: h.point, b: null } : { ...m, b: h.point } });
        return;
      }
      if (h?.id) st().select(h.id, { extend: d.shift });
      else if (!d.shift) st().select(null);
    };
    const onDbl = (e) => {
      if (e.target !== view.dom) return;
      const h = pick(e.clientX, e.clientY);
      const parts = st().state.parts;
      let p = parts.find((q) => q.id === h?.id);
      while (p?.parent) p = parts.find((q) => q.id === p.parent) || null;
      if (p) st().select(p.id);
    };
    addEventListener("pointerdown", onDown);
    addEventListener("pointermove", onMove);
    addEventListener("pointerup", onUp);
    addEventListener("dblclick", onDbl);
    return () => { removeEventListener("pointerdown", onDown); removeEventListener("pointermove", onMove); removeEventListener("pointerup", onUp); removeEventListener("dblclick", onDbl); };
  }, []);
  if (!rect) return null;
  return <div className="pointer-events-none fixed z-40 border border-dashed border-cyan-glow/80 bg-cyan-glow/[0.06]"
    style={{ left: rect.x0, top: rect.y0, width: rect.x1 - rect.x0, height: rect.y1 - rect.y0 }} />;
}
