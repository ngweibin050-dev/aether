import { useEffect, useRef } from "react";
import * as THREE from "three";
import { view } from "../scene/registry";
import { useLayout } from "./layout";

const AX = [["x", [1, 0, 0], "#ff5d73", "right", "left"], ["y", [0, 1, 0], "#7ddc5a", "back", "front"], ["z", [0, 0, 1], "#5fa8ff", "top", "bottom"]];
const R = 34, C = 44, DPR = Math.min(2, window.devicePixelRatio || 1);

// the axis balls for the current camera, back to front
function balls(cam) {
  const q = cam.quaternion.clone().invert();
  return AX.flatMap(([n, v, col, pos, neg]) => [1, -1].map((s) => {
    const p = new THREE.Vector3(...v).multiplyScalar(s).applyQuaternion(q);
    return { n, s, col, view: s > 0 ? pos : neg, x: C + p.x * R, y: C - p.y * R, z: p.z };
  })).sort((a, b) => a.z - b.z);
}

// Blender's navigation gizmo: click an axis to look along it, drag to orbit (zoom: wheel; pan: Shift + middle drag).
// Drawn on its own small 2D canvas, outside React: rewriting an SVG through React on every camera step repainted the
// page around it and cost ~8 fps while orbiting on an integrated GPU.
export default function NavGizmo() {
  const lay = useLayout();
  const ref = useRef();
  const hover = useRef(false);
  useEffect(() => {
    const cv = ref.current;
    const ctx = cv.getContext("2d");
    let raf = 0, off = null;
    const draw = () => {
      raf = 0;
      const cam = view.nav?.camera;
      if (!cam) return;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, C * 2, C * 2);
      if (hover.current) { ctx.fillStyle = "rgba(255,255,255,.06)"; ctx.beginPath(); ctx.arc(C, C, C, 0, 2 * Math.PI); ctx.fill(); }
      const bs = balls(cam);
      ctx.lineWidth = 2;
      for (const b of bs) if (b.s > 0) { ctx.strokeStyle = b.col; ctx.globalAlpha = 0.8; ctx.beginPath(); ctx.moveTo(C, C); ctx.lineTo(b.x, b.y); ctx.stroke(); }
      for (const b of bs) {
        ctx.globalAlpha = 0.65 + 0.35 * (b.z + 1) / 2;
        ctx.beginPath(); ctx.arc(b.x, b.y, b.s > 0 ? 8.5 : 6.5, 0, 2 * Math.PI);
        if (b.s > 0) { ctx.fillStyle = b.col; ctx.fill(); }
        else { ctx.fillStyle = "rgba(10,12,18,.9)"; ctx.fill(); ctx.lineWidth = 1.4; ctx.strokeStyle = b.col; ctx.stroke(); }
        if (b.s > 0) {
          ctx.globalAlpha = 1; ctx.fillStyle = "#05070b"; ctx.font = "700 9px 'JetBrains Mono', monospace"; ctx.textAlign = "center";
          ctx.fillText(b.n.toUpperCase(), b.x, b.y + 3.2);
        }
      }
      ctx.globalAlpha = 1;
    };
    const ask = () => { if (!raf) raf = requestAnimationFrame(draw); };
    const t = setInterval(() => { if (view.nav) { off = view.nav.onChange(ask); clearInterval(t); ask(); } }, 100);
    cv._redraw = ask;
    return () => { clearInterval(t); off?.(); cancelAnimationFrame(raf); };
  }, []);

  const pick = (e) => {                                 // the axis ball under the pointer (front-most first)
    const cam = view.nav?.camera;
    if (!cam) return null;
    const r = e.currentTarget.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    return balls(cam).reverse().find((b) => Math.hypot(b.x - x, b.y - y) <= (b.s > 0 ? 9 : 7))?.view || null;
  };
  const orbit = (e) => {                             // drag = orbit; a click on an axis ball looks along that axis
    e.preventDefault();
    const target = pick(e);
    let x = e.clientX, y = e.clientY, moved = false;
    const mv = (ev) => {
      const dx = ev.clientX - x, dy = ev.clientY - y; x = ev.clientX; y = ev.clientY;
      if (Math.abs(dx) + Math.abs(dy) > 0) moved = true;
      view.nav.orbit(-dx * 0.012, -dy * 0.012);
    };
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); if (!moved && target) view.nav.view(target); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  return (
    <div className="pointer-events-auto absolute z-20 flex flex-col items-center gap-1.5 transition-[right] duration-300" style={{ right: lay.navRight, top: lay.navTop }}>
      <canvas ref={ref} width={C * 2 * DPR} height={C * 2 * DPR} style={{ width: C * 2, height: C * 2 }} onPointerDown={orbit}
        onPointerMove={(e) => { e.currentTarget.style.cursor = pick(e) ? "pointer" : "grab"; }}
        onPointerEnter={(e) => { hover.current = true; e.currentTarget._redraw?.(); }}
        onPointerLeave={(e) => { hover.current = false; e.currentTarget._redraw?.(); }}
        title="Drag to orbit · click an axis to look along it" className="rounded-full" />
    </div>
  );
}
