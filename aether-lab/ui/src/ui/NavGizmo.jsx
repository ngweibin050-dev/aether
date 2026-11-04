import { useEffect, useRef } from "react";
import * as THREE from "three";
import { view } from "../scene/registry";
import { useLayout } from "./layout";
import Icon from "./Icon";

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
  // the hand: drag it to move the VIEW (not a model), as Blender's pan button
  const pan = (e) => {
    e.preventDefault();
    let x = e.clientX, y = e.clientY;
    const mv = (ev) => { view.nav?.pan(ev.clientX - x, ev.clientY - y); x = ev.clientX; y = ev.clientY; };
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  const btn = "grid h-8 w-8 place-items-center rounded-full bg-black/35 text-white/75 hover:bg-white/15 hover:text-white";
  return (<>
    <div className="pointer-events-auto absolute z-20 flex flex-col items-center gap-1.5 transition-[right] duration-300" style={{ right: lay.navRight, top: lay.navTop }}>
      <canvas ref={ref} width={C * 2 * DPR} height={C * 2 * DPR} style={{ width: C * 2, height: C * 2 }} onPointerDown={orbit}
        onPointerMove={(e) => { e.currentTarget.style.cursor = pick(e) ? "pointer" : "grab"; }}
        onPointerEnter={(e) => { hover.current = true; e.currentTarget._redraw?.(); }}
        onPointerLeave={(e) => { hover.current = false; e.currentTarget._redraw?.(); }}
        title="Drag to orbit · click an axis to look along it" className="rounded-full" />
      <div className="flex gap-1.5">
        <button className={`${btn} cursor-grab active:cursor-grabbing`} onPointerDown={pan} title="Drag to move the view (or right-drag / Space + drag in the viewport)"><Icon name="hand" /></button>
        <button className={btn} onClick={() => view.nav?.home()} title="Back to the AETHER desk (Ctrl+Home)"><Icon name="home" /></button>
      </div>
    </div>
    <DeskPointer />
  </>);
}

// When the desk is out of view (panned or zoomed far away), an arrow on the edge of the free view (between the side
// panels) points to it; click = back. Written outside React, and only when it changes (it moves with the camera).
function DeskPointer() {
  const ref = useRef();
  const lay = useLayout();
  const area = useRef(lay);
  area.current = lay;
  useEffect(() => {
    let off = null, raf = 0, shown = false;
    const v = new THREE.Vector3();
    const upd = () => {
      raf = 0;
      const nav = view.nav, el = ref.current;
      if (!nav || !el) return;
      const r = nav.dom.getBoundingClientRect();
      v.set(0, 0, 0).project(nav.camera);
      const behind = v.z > 1;
      const inside = !behind && Math.abs(v.x) < 0.98 && Math.abs(v.y) < 0.98;
      if (inside) { if (shown) { el.style.display = "none"; shown = false; } return; }
      let x = behind ? -v.x : v.x, y = behind ? -v.y : v.y;
      const k = 0.9 / Math.max(Math.abs(x), Math.abs(y), 1e-6);
      x *= k; y *= k;
      const a = area.current;
      const px = Math.min(Math.max(r.left + (x + 1) / 2 * r.width, a.midLeft + 24), r.right - a.midRight - 24);
      const py = Math.min(Math.max(r.top + (1 - y) / 2 * r.height, 84), r.bottom - 64);
      el.style.transform = `translate(${px - 18}px, ${py - 18}px)`;
      el.firstChild.style.transform = `rotate(${Math.atan2(-y, x)}rad)`;
      if (!shown) { el.style.display = "grid"; shown = true; }
    };
    const ask = () => { if (!raf) raf = requestAnimationFrame(upd); };
    const t = setInterval(() => { if (view.nav) { off = view.nav.onChange(ask); clearInterval(t); ask(); } }, 100);
    return () => { clearInterval(t); off?.(); cancelAnimationFrame(raf); };
  }, []);
  return (
    <button ref={ref} onClick={() => view.nav?.home()} title="The AETHER desk is this way: click to go back" style={{ display: "none" }}
      className="pointer-events-auto fixed left-0 top-0 z-30 h-9 w-9 place-items-center rounded-full border border-cyan-glow/50 bg-black/60 text-cyan-glow shadow-glow">
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M5 12h13M13 6l6 6-6 6" /></svg>
    </button>
  );
}
