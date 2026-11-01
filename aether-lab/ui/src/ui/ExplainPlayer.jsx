import { useEffect, useState } from "react";
import { useStore } from "../store";
import { view } from "../scene/registry";
import { sceneBox } from "../scene/Viewport";
import { useLayout } from "./layout";

// Explain this machine: Muse Spark's steps over the BUILT model (explain.py checks every part id and number against it).
// Each step selects its parts (the rest fade: x-ray), explodes or cuts if asked and moves the camera to them.
const STEP_MS = 9000;
const ISO = { theta: -Math.PI / 4, phi: Math.PI / 3 };

function stage(step) {
  const st = useStore.getState();
  st.selectMany(step.parts);
  const box = sceneBox();
  const patch = { xray: true, explode: step.explode ? 1 : 0, section: null };
  if (step.camera === "section" && !box.isEmpty()) Object.assign(patch, { section: "y", section_mm: +((box.min.y + box.max.y) / 2).toFixed(1) });
  st.setView(patch, { now: true });
  const nav = view.nav;
  if (!nav) return;
  if (step.camera === "iso") { nav.autoOrtho = false; nav.setOrtho(false); nav.animateTo(ISO); }
  else nav.view(step.camera === "top" ? "top" : "front");
  // frame the step's parts once the explode / turn has settled
  setTimeout(() => nav.frame(sceneBox(step.parts)), step.explode ? 750 : 420);
}

function Live({ steps, skew }) {
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 250); return () => clearInterval(t); }, []);
  const now = Date.now() / 1000 - skew;
  return (
    <div className="space-y-1 font-mono text-[10.5px]">
      {steps.map((s, i) => (
        <div key={i} className="flex justify-between gap-4">
          <span className={s.state === "error" ? "text-warn" : s.state === "ok" ? "text-silver" : "text-cyan-glow"}>{s.label}</span>
          <span className="readout">{(s.s ?? (now - (s.t0 || now))).toFixed(1)} s</span>
        </div>
      ))}
      {!steps.length && <div className="text-silver">starting…</div>}
    </div>
  );
}

export default function ExplainPlayer() {
  const { midLeft, midRight } = useLayout();
  const ex = useStore((s) => s.explain);
  const i = useStore((s) => s.explainStep);
  const busy = useStore((s) => !!s.busy.explain);
  const progress = useStore((s) => s.progress);
  const skew = useStore((s) => s.progressSkew || 0);
  const machine = useStore((s) => (s.state?.parts || []).some((p) => p.eng?.from_drawing && p.type !== "group" && !p.eng?.region));
  const [play, setPlay] = useState(false);
  const [big, setBig] = useState(false);
  const n = ex?.steps?.length || 0;
  const step = ex?.steps?.[i];

  useEffect(() => { if (step) stage(step); }, [ex, i]);
  useEffect(() => {
    if (!play || !n) return;
    if (i >= n - 1) { setPlay(false); return; }
    const t = setTimeout(() => useStore.getState().setExplainStep(i + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [play, i, n]);

  const go = (k) => { setPlay(false); useStore.getState().setExplainStep(Math.max(0, Math.min(n - 1, k))); };
  const box = "pointer-events-auto absolute z-30 rounded-2xl border border-white/10 bg-[#07111c]/90 shadow-2xl backdrop-blur";
  const pos = { top: 70, left: `max(${midLeft}px, calc(50% - 300px))`, right: `max(${midRight}px, calc(50% - 300px))` };

  if (busy) return (
    <div className={`${box} px-4 py-3`} style={pos}>
      <div className="label mb-2">Explain this machine</div>
      <Live steps={progress} skew={skew} />
    </div>
  );
  if (!ex) return machine ? (
    <button className={`${box} btn-accent !rounded-full px-4 py-1.5 text-[12px]`} style={{ top: 70, left: "50%", transform: "translateX(-50%)" }}
      onClick={() => useStore.getState().runExplain()}>Explain this machine</button>
  ) : null;

  const ill = ex.illustration;
  return (
    <section data-dock="top" data-mode="normal" className={`${box} flex gap-3 p-3`} style={pos}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="label truncate">{ex.machine || "Explain this machine"}</span>
          <span className="readout shrink-0 text-[10.5px]">step {i + 1} / {n}</span>
        </div>
        <div className="mt-1.5 text-[14px] font-semibold text-white">{step?.title}</div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-slate-200">{step?.text}</p>
        <div className="mt-2.5 flex items-center gap-1.5">
          <button className="btn py-1" disabled={i === 0} onClick={() => go(i - 1)}>Back</button>
          <button className="btn py-1" disabled={i >= n - 1} onClick={() => go(i + 1)}>Next</button>
          <button className="btn py-1" onClick={() => { if (i >= n - 1) go(0); setPlay(!play); }}>{play ? "Pause" : "Play"}</button>
          <button className="btn ml-auto py-1" onClick={() => { setPlay(false); useStore.getState().closeExplain(); }}>Close</button>
        </div>
        <div className="mt-2 font-mono text-[9.5px] text-slate-400">
          Muse Spark · explanation · {ex.timing?.spark_s} s · every part and number checked against the built model
          {ex.rejected_steps?.length ? ` · ${ex.rejected_steps.length} step(s) rejected` : ""}
          {ill?.s ? ` · Muse Image · illustration · ${ill.s} s` : ill?.error ? ` · Muse Image: ${ill.error}` : ""}
        </div>
      </div>
      {ill?.data_url && (
        <figure className="w-32 shrink-0 cursor-zoom-in" onClick={() => setBig(!big)}>
          <img src={ill.data_url} className={`${big ? "fixed left-1/2 top-1/2 z-50 w-[min(80vw,720px)] -translate-x-1/2 -translate-y-1/2" : "w-full"} rounded-lg border border-white/10`} />
          <figcaption className="mt-1 text-[9px] leading-tight text-warn">{ill.label}</figcaption>
        </figure>
      )}
    </section>
  );
}
