import { useRef } from "react";

// Minimal line graph: thin neon line, soft area, mono tick labels.
export function LineChart({ xs, ys, xLabel, yLabel, color = "#5fe1ff", h = 92, yMax, marker, threshold, fmtX = (v) => v }) {
  if (!xs?.length) return null;
  const W = 280, H = h, L = 26, B = 16, T = 6, R = 6;
  const x0 = Math.min(...xs), x1 = Math.max(...xs), top = yMax ?? Math.max(...ys, 1);
  const px = (v) => L + ((v - x0) / Math.max(x1 - x0, 1e-9)) * (W - L - R);
  const py = (v) => T + (1 - v / top) * (H - T - B);
  const pts = xs.map((x, i) => `${px(x).toFixed(1)},${py(ys[i]).toFixed(1)}`).join(" ");
  const id = "g" + color.slice(1);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: h }}>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".28" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient>
        <filter id={id + "f"}><feGaussianBlur stdDeviation="2.2" /></filter>
      </defs>
      {[0, 0.5, 1].map((f) => <line key={f} x1={L} x2={W - R} y1={py(top * f)} y2={py(top * f)} stroke="rgba(255,255,255,.06)" />)}
      {[0, 0.5, 1].map((f) => <text key={"t" + f} x={L - 4} y={py(top * f) + 3} fontSize="8" textAnchor="end" fill="#7d8796" fontFamily="JetBrains Mono">{Math.round(top * f)}</text>)}
      {threshold !== undefined && <line x1={L} x2={W - R} y1={py(threshold)} y2={py(threshold)} stroke="#ff4fd8" strokeDasharray="3 3" strokeOpacity=".7" />}
      <polygon points={`${px(xs[0])},${py(0)} ${pts} ${px(xs[xs.length - 1])},${py(0)}`} fill={`url(#${id})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2.4" strokeOpacity=".35" filter={`url(#${id}f)`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.3" />
      {xs.map((x, i) => <circle key={i} cx={px(x)} cy={py(ys[i])} r={i === marker ? 3.2 : 1.6} fill={i === marker ? "#fff" : color} />)}
      <text x={L} y={H - 3} fontSize="8" fill="#7d8796" fontFamily="JetBrains Mono">{fmtX(x0)}</text>
      <text x={W - R} y={H - 3} fontSize="8" fill="#7d8796" fontFamily="JetBrains Mono" textAnchor="end">{fmtX(x1)}</text>
      <text x={(L + W) / 2} y={H - 3} fontSize="8" fill="#7d8796" textAnchor="middle">{xLabel}</text>
      {yLabel && <text x={L + 2} y={T + 7} fontSize="8" fill="#7d8796">{yLabel}</text>}
    </svg>
  );
}

// Loading state: a travelling sine wave (the Modal GPU / local engine is crunching).
export function SineLoader({ label = "computing", className = "" }) {
  const path = Array.from({ length: 121 }, (_, i) => `${i === 0 ? "M" : "L"}${i * 2},${10 + Math.sin(i / 120 * Math.PI * 8) * 6}`).join(" ");
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="relative h-5 w-24 overflow-hidden">
        <svg viewBox="0 0 240 20" className="absolute h-5 w-48 animate-wave" preserveAspectRatio="none">
          <path d={path} fill="none" stroke="#5fe1ff" strokeWidth="1.6" />
          <path d={path} fill="none" stroke="#5fe1ff" strokeWidth="4" strokeOpacity=".25" />
        </svg>
      </div>
      <span className="font-mono text-[10.5px] text-cyan-glow/90">{label}</span>
    </div>
  );
}

// Pointer-driven slider (works with the mouse, touch and the hand-mode air cursor).
export function Slider({ value, min = 0, max = 1, step = 0, onChange, onCommit, vertical = false, className = "", accent = "#5fe1ff" }) {
  const ref = useRef();
  const f = (value - min) / Math.max(max - min, 1e-9);
  const at = (e) => {
    const r = ref.current.getBoundingClientRect();
    let t = vertical ? 1 - (e.clientY - r.top) / r.height : (e.clientX - r.left) / r.width;
    t = Math.min(1, Math.max(0, t));
    let v = min + t * (max - min);
    if (step) v = Math.round(v / step) * step;
    return v;
  };
  const down = (e) => {
    e.preventDefault(); e.stopPropagation();
    let last = at(e); onChange?.(last);
    const mv = (ev) => { last = at(ev); onChange?.(last); };
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); onCommit?.(last); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  return (
    <div ref={ref} onPointerDown={down} className={`relative cursor-pointer touch-none ${vertical ? "w-6" : "h-5"} ${className}`}>
      <div className={`absolute rounded-full bg-white/10 ${vertical ? "inset-y-0 left-1/2 w-[3px] -translate-x-1/2" : "inset-x-0 top-1/2 h-[3px] -translate-y-1/2"}`} />
      <div className={`absolute rounded-full ${vertical ? "bottom-0 left-1/2 w-[3px] -translate-x-1/2" : "left-0 top-1/2 h-[3px] -translate-y-1/2"}`}
        style={{ [vertical ? "height" : "width"]: `${f * 100}%`, background: accent, boxShadow: `0 0 10px ${accent}` }} />
      <div className="absolute h-3.5 w-3.5 rounded-full border-2 bg-ink-950"
        style={{ borderColor: accent, boxShadow: `0 0 12px ${accent}`, ...(vertical ? { left: "50%", bottom: `calc(${f * 100}% - 7px)`, transform: "translateX(-50%)" } : { top: "50%", left: `calc(${f * 100}% - 7px)`, transform: "translateY(-50%)" }) }} />
    </div>
  );
}
