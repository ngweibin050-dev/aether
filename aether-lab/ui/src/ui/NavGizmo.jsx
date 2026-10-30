import { useEffect, useState } from "react";
import * as THREE from "three";
import { useStore } from "../store";
import { view } from "../scene/registry";
import { run } from "../commands";
import Icon from "./Icon";

const AX = [["x", [1, 0, 0], "#ff5d73", "right", "left"], ["y", [0, 1, 0], "#7ddc5a", "back", "front"], ["z", [0, 0, 1], "#5fa8ff", "top", "bottom"]];

// Blender's navigation gizmo: click an axis to look along it, drag to orbit; zoom / pan handles below.
export default function NavGizmo() {
  const [, tick] = useState(0);
  const [ortho, setOrtho] = useState(false);
  const physics = useStore((s) => s.panels.physics);
  useEffect(() => {
    let off, t = setInterval(() => { if (view.nav) { off = view.nav.onChange((n) => { tick((k) => k + 1); setOrtho(n.isOrtho); }); clearInterval(t); tick(1); } }, 100);
    return () => { clearInterval(t); off?.(); };
  }, []);
  const cam = view.nav?.camera;
  if (!cam) return null;
  const R = 34, C = 44;
  const q = cam.quaternion.clone().invert();
  const balls = AX.flatMap(([n, v, col, pos, neg]) => [1, -1].map((s) => {
    const p = new THREE.Vector3(...v).multiplyScalar(s).applyQuaternion(q);
    return { n, s, col, view: s > 0 ? pos : neg, x: C + p.x * R, y: C - p.y * R, z: p.z };
  })).sort((a, b) => a.z - b.z);
  const drag = (kind) => (e) => {
    e.preventDefault();
    let x = e.clientX, y = e.clientY, moved = false;
    const mv = (ev) => {
      const dx = ev.clientX - x, dy = ev.clientY - y; x = ev.clientX; y = ev.clientY;
      if (Math.abs(dx) + Math.abs(dy) > 0) moved = true;
      if (kind === "orbit") view.nav.orbit(-dx * 0.012, -dy * 0.012);
      else if (kind === "pan") view.nav.pan(dx, dy);
      else view.nav.zoom(Math.exp(dy * 0.008));
    };
    const up = (ev) => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); if (!moved && kind === "orbit") { const b = ev.target.dataset.view; b && view.nav.view(b); } };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  return (
    <div className="pointer-events-auto absolute top-[62px] z-20 flex flex-col items-center gap-1.5" style={{ right: physics ? 346 : 14 }}>
      <svg width={C * 2} height={C * 2} onPointerDown={drag("orbit")} className="cursor-grab rounded-full transition hover:bg-white/[0.06]">
        {balls.filter((b) => b.s > 0).map((b) => <line key={"l" + b.n} x1={C} y1={C} x2={b.x} y2={b.y} stroke={b.col} strokeWidth="2" strokeOpacity=".8" />)}
        {balls.map((b) => (
          <g key={b.n + b.s} style={{ cursor: "pointer" }}>
            <circle data-view={b.view} cx={b.x} cy={b.y} r={b.s > 0 ? 8.5 : 6.5} fill={b.s > 0 ? b.col : "rgba(10,12,18,.9)"} stroke={b.col} strokeWidth={b.s > 0 ? 0 : 1.4} opacity={0.65 + 0.35 * (b.z + 1) / 2} />
            {b.s > 0 && <text data-view={b.view} x={b.x} y={b.y + 3.2} fontSize="9" fontWeight="700" textAnchor="middle" fill="#05070b" fontFamily="JetBrains Mono">{b.n.toUpperCase()}</text>}
          </g>
        ))}
      </svg>
      {[["zoom", "zoom", "Drag to zoom"], ["pan", "pan", "Drag to pan"]].map(([k, ic, t]) => (
        <button key={k} title={t} onPointerDown={drag(k)} className="glass grid h-8 w-8 cursor-move place-items-center rounded-full text-white/75 hover:text-white"><Icon name={ic} /></button>
      ))}
      <button title="Viewer's eye (Numpad 0)" onClick={() => run("view.eye")} className="glass grid h-8 w-8 place-items-center rounded-full text-white/75 hover:text-white"><Icon name="camera" /></button>
      <button title="Perspective / Orthographic (Numpad 5)" onClick={() => run("view.ortho")}
        className={`glass grid h-8 w-8 place-items-center rounded-full ${ortho ? "text-cyan-glow" : "text-white/75"} hover:text-white`}><Icon name="ortho" /></button>
    </div>
  );
}
