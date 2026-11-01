import { useEffect, useRef } from "react";

// Full-page interactive particle field: dots drift, link to near neighbours, flee the cursor, and a click sends a ripple.
export default function DotCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current, ctx = cv.getContext("2d");
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W = 0, H = 0, dpr = 1, raf = 0, pts = [];
    const mouse = { x: -9999, y: -9999 }, ripples = [];
    const COLORS = ["95,225,255", "111,139,255", "176,107,255"];
    const resize = () => {
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = innerWidth; H = innerHeight;
      cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + "px"; cv.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(120, Math.max(40, (W * H) / 13000)));
      pts = Array.from({ length: n }, () => ({
        x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
        r: 0.8 + Math.random() * 1.6, c: COLORS[(Math.random() * 3) | 0],
      }));
    };
    const move = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; };
    const leave = () => { mouse.x = mouse.y = -9999; };
    const click = (e) => {
      ripples.push({ x: e.clientX, y: e.clientY, t: 0 });
      for (const p of pts) {
        const dx = p.x - e.clientX, dy = p.y - e.clientY, d = Math.hypot(dx, dy);
        if (d < 260 && d > 0) { const f = (1 - d / 260) * 4; p.vx += (dx / d) * f; p.vy += (dy / d) * f; }
      }
    };
    const frame = () => {
      ctx.clearRect(0, 0, W, H);
      for (const p of pts) {
        const dx = p.x - mouse.x, dy = p.y - mouse.y, d = Math.hypot(dx, dy);
        if (d < 160 && d > 0) { const f = (1 - d / 160) * 0.6; p.vx += (dx / d) * f; p.vy += (dy / d) * f; }
        p.vx *= 0.96; p.vy *= 0.96;
        p.vx += (Math.random() - 0.5) * 0.02; p.vy += (Math.random() - 0.5) * 0.02;
        p.x += p.vx + 0; p.y += p.vy;
        if (p.x < -20) p.x = W + 20; if (p.x > W + 20) p.x = -20;
        if (p.y < -20) p.y = H + 20; if (p.y > H + 20) p.y = -20;
      }
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i];
        for (let j = i + 1; j < pts.length; j++) {
          const b = pts[j], d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < 120) {
            ctx.strokeStyle = `rgba(${a.c},${0.16 * (1 - d / 120)})`;
            ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
        const dm = Math.hypot(a.x - mouse.x, a.y - mouse.y);
        if (dm < 200) {
          ctx.strokeStyle = `rgba(95,225,255,${0.35 * (1 - dm / 200)})`;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
        }
        ctx.fillStyle = `rgba(${a.c},0.85)`;
        ctx.beginPath(); ctx.arc(a.x, a.y, a.r, 0, 6.2832); ctx.fill();
      }
      for (let k = ripples.length - 1; k >= 0; k--) {
        const r = ripples[k]; r.t += 1;
        const rad = r.t * 6, al = Math.max(0, 1 - r.t / 60);
        ctx.strokeStyle = `rgba(95,225,255,${0.5 * al})`; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(r.x, r.y, rad, 0, 6.2832); ctx.stroke();
        if (al <= 0) ripples.splice(k, 1);
      }
      if (!reduce) raf = requestAnimationFrame(frame);
    };
    resize(); frame();
    addEventListener("resize", resize); addEventListener("pointermove", move); addEventListener("pointerdown", click);
    document.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("resize", resize); removeEventListener("pointermove", move); removeEventListener("pointerdown", click);
      document.removeEventListener("pointerleave", leave);
    };
  }, []);
  return <canvas ref={ref} aria-hidden className="pointer-events-none fixed inset-0 z-0" />;
}
