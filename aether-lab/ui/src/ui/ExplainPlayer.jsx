import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import { view } from "../scene/registry";
import { sceneBox } from "../scene/Viewport";
import FloatPanel from "./FloatPanel";
import { L, useLayout } from "./layout";

// Explain this machine (explain.py): an engineer's walk-through of ONE built model. Tabs:
//   Walkthrough  - the steps (overview, architecture, why, each subsystem, power / load path, interfaces, assembly,
//                  what was assumed); each step has a render of THIS model and also stages the 3D view (its parts
//                  selected, the rest x-ray, exploded / cut / turned as the step says); the assembly step animates
//                  the model coming together
//   Architecture - the subsystems (colour-coded on a render), why it is arranged this way, the assembly order
//   Quiz         - check yourself
//   Source       - the drawing this model was built from (its own, not the last one built)
// Every part id and number in it was checked against the model (explain.validate). Double-click a picture to enlarge.
const STEP_MS = 10000;
const ISO = { theta: -Math.PI / 4, phi: Math.PI / 3 };
const KIND = { overview: "Overview", architecture: "Architecture", why: "Why this design", subsystem: "Subsystem",
  flow: "Power / load path", interfaces: "Interfaces", assembly: "Assembly", assumptions: "Measured vs assumed" };

function animateExplode(from, to, ms = 2600) {
  const st = useStore.getState(), t0 = performance.now();
  const tick = () => {
    const k = Math.min(1, (performance.now() - t0) / ms), e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
    st.setView({ explode: +(from + (to - from) * e).toFixed(3) });
    if (k < 1) requestAnimationFrame(tick);
  };
  tick();
}

function stage(step) {
  const st = useStore.getState();
  st.selectMany(step.parts);
  const box = sceneBox();
  const patch = { xray: true, explode: step.explode ? 1 : 0, section: null };
  if (step.camera === "section" && !box.isEmpty()) Object.assign(patch, { section: "y", section_mm: +((box.min.y + box.max.y) / 2).toFixed(1) });
  st.setView(patch, { now: true });
  if (step.kind === "assembly") setTimeout(() => animateExplode(1, 0), 1600);    // pulled apart, then put together
  const nav = view.nav;
  if (!nav) return;
  if (step.camera === "iso" || step.camera === "section") { nav.autoOrtho = false; nav.setOrtho(false); nav.animateTo(ISO); }
  else nav.view({ front: "front", rear: "back", left: "left", top: "top" }[step.camera] || "front");
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

// A recorded demo run is on screen: say so all the time (CLAUDE.md rule 5: a saved result only with a "recorded" label)
export function RecordedBanner() {
  const rec = useStore((s) => s.recorded);
  if (!rec) return null;
  return (
    <div className="pointer-events-auto absolute bottom-10 left-1/2 z-40 -translate-x-1/2 rounded-full border border-warn/40 bg-black/80 px-4 py-1 font-mono text-[11px] text-warn">
      RECORDED run · {rec.title} · {rec.at} · not live
      <button className="ml-3 text-silver underline" onClick={() => useStore.setState({ recorded: null })}>hide</button>
    </div>
  );
}

function Pic({ src, alt, className = "" }) {
  if (!src) return null;
  return <img src={src} alt={alt} title="Double-click to enlarge"
    className={`w-full cursor-zoom-in rounded-lg border border-white/10 bg-[#0c0f16] object-contain ${className}`} />;
}

function Walkthrough({ ex, i, go, play, setPlay }) {
  const n = ex.steps.length, step = ex.steps[i];
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {ex.steps.map((s, k) => (
          <button key={k} onClick={() => go(k)} title={s.title}
            className={`h-1.5 flex-1 rounded-full transition ${k === i ? "bg-cyan-glow" : k < i ? "bg-cyan-glow/40" : "bg-white/10 hover:bg-white/25"}`} />))}
      </div>
      <div className="flex min-h-0 flex-1 gap-3 max-[700px]:flex-col">
        <div className="min-w-0 flex-1 overflow-y-auto scroll-thin">
          <div className="font-mono text-[10px] uppercase tracking-wider text-cyan-glow/80">{KIND[step?.kind] || "Step"} · {i + 1} / {n}</div>
          <div className="mt-0.5 text-[15px] font-semibold text-white">{step?.title}</div>
          <p className="mt-1.5 select-text text-[12.5px] leading-relaxed text-slate-200">{step?.text}</p>
          {step?.kind === "assembly" && <div className="mt-2 font-mono text-[10px] text-slate-400">The 3D view pulls the model apart, then puts it together.</div>}
        </div>
        <div className="w-[46%] shrink-0 max-[700px]:w-full"><Pic src={step?.image} alt={`${ex.machine}: ${step?.title}`} /></div>
      </div>
      <div className="flex items-center gap-1.5">
        <button className="btn py-1" disabled={i === 0} onClick={() => go(i - 1)}>Back</button>
        <button className="btn py-1" disabled={i >= n - 1} onClick={() => go(i + 1)}>Next</button>
        <button className="btn py-1" onClick={() => { if (i >= n - 1) go(0); setPlay(!play); }}>{play ? "Pause" : "Play"}</button>
      </div>
    </div>
  );
}

function Architecture({ ex }) {
  const st = useStore();
  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1 scroll-thin">
      {ex.overview && <p className="select-text text-[12.5px] leading-relaxed text-slate-200">{ex.overview}</p>}
      <div className="flex gap-3 max-[700px]:flex-col">
        <div className="min-w-0 flex-1 space-y-1.5">
          {ex.subsystems.map((s, k) => (
            <button key={k} onClick={() => { st.selectMany(s.parts); view.nav?.frame(sceneBox(s.parts)); }}
              className="block w-full rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-left hover:bg-white/[0.07]">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
                <span className="text-[12.5px] font-semibold text-white">{s.name}</span>
                <span className="ml-auto font-mono text-[10px] text-slate-500">{s.parts.length} part{s.parts.length > 1 ? "s" : ""}</span>
              </div>
              <div className="mt-0.5 pl-[18px] text-[11.5px] text-slate-400">{s.role}</div>
            </button>))}
        </div>
        <div className="w-[44%] shrink-0 max-[700px]:w-full">
          <Pic src={ex.architecture_image} alt={`${ex.machine}: subsystems, exploded`} />
          <div className="mt-1 font-mono text-[9.5px] text-slate-500">Exploded, each subsystem in its colour</div>
        </div>
      </div>
      {ex.design_rationale?.length > 0 && (
        <div>
          <div className="label mb-1">Why it is arranged this way <span className="normal-case text-slate-500">(engineering reasoning, not measured)</span></div>
          <ul className="ml-4 list-disc space-y-0.5 text-[12px] text-slate-200 marker:text-slate-500">{ex.design_rationale.map((w, k) => <li key={k} className="select-text">{w}</li>)}</ul>
        </div>)}
      {ex.assembly_order?.length > 0 && (
        <div>
          <div className="label mb-1">Assembly order</div>
          <div className="flex flex-wrap items-center gap-1 text-[11.5px] text-slate-200">
            {ex.assembly_order.map((a, k) => <span key={k} className="flex items-center gap-1">{k > 0 && <span className="text-slate-500">→</span>}
              <span className="rounded-md border border-white/10 px-1.5 py-0.5">{k + 1}. {a}</span></span>)}
          </div>
        </div>)}
    </div>
  );
}

function Quiz({ quiz }) {
  const [pick, setPick] = useState({});
  if (!quiz?.length) return <div className="text-[12px] text-slate-400">No quiz for this model.</div>;
  const right = quiz.filter((q, k) => pick[k] === q.answer).length;
  return (
    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1 scroll-thin">
      {quiz.map((q, k) => (
        <div key={k}>
          <div className="text-[12.5px] font-semibold text-white">{k + 1}. {q.question}</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {q.options.map((o, j) => {
              const done = pick[k] != null, ok = j === q.answer, mine = pick[k] === j;
              return <button key={j} disabled={done} onClick={() => setPick({ ...pick, [k]: j })}
                className={`rounded-lg border px-2.5 py-1 text-[11.5px] ${!done ? "border-white/15 hover:bg-white/10" : ok ? "border-emerald-400/50 bg-emerald-400/15 text-emerald-100" : mine ? "border-rose-400/50 bg-rose-400/15 text-rose-100" : "border-white/10 text-slate-500"}`}>{o}</button>;
            })}
          </div>
        </div>))}
      {Object.keys(pick).length === quiz.length && <div className="font-mono text-[11px] text-cyan-glow">{right} / {quiz.length} right</div>}
    </div>
  );
}

export default function ExplainPlayer() {
  const lay = useLayout();
  const open = useStore((s) => s.panels.explain);
  const ex = useStore((s) => s.explain);
  const i = useStore((s) => s.explainStep);
  const busy = useStore((s) => !!s.busy.explain);
  const progress = useStore((s) => s.progress);
  const skew = useStore((s) => s.progressSkew || 0);
  const [play, setPlay] = useState(false);
  const [tab, setTab] = useState("walk");
  const n = ex?.steps?.length || 0;
  const step = ex?.steps?.[i];
  const staged = useRef(null);

  useEffect(() => { setTab("walk"); }, [ex]);
  useEffect(() => {
    if (step && open && tab === "walk" && staged.current !== step) { staged.current = step; stage(step); }
  }, [ex, i, open, tab]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!play || !n) return;
    if (i >= n - 1) { setPlay(false); return; }
    const t = setTimeout(() => useStore.getState().setExplainStep(i + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [play, i, n]);

  const go = (k) => { setPlay(false); useStore.getState().setExplainStep(Math.max(0, Math.min(n - 1, k))); };
  const close = () => { setPlay(false); staged.current = null; useStore.getState().closeExplain(); };
  // beside the model, not over it: on the right of the free view (drag / resize / dock it like any panel)
  const style = { right: lay.midRight + 8, top: L.top, width: "min(640px, calc(100vw - 560px))", height: "min(560px, 64vh)" };
  const TABS = [["walk", "Walkthrough"], ["arch", "Architecture"], ["quiz", "Quiz"], ...(ex?.source_image ? [["src", "Source drawing"]] : [])];

  return (
    <FloatPanel id="explain" title={ex?.machine ? `Explain · ${ex.model?.name || ex.machine}` : "Explain this machine"} icon="layers"
      open={open} onClose={close} style={style} busy={busy}>
      <div className="flex min-h-0 flex-1 flex-col gap-2 px-3 pb-3">
        {busy ? <div className="py-2"><div className="label mb-2">Muse Spark is studying the model</div><Live steps={progress} skew={skew} /></div>
          : !ex ? (
            <div className="py-3 text-[12px] text-slate-300">
              Explains the selected model (or the newest one) like an engineer: its architecture, why it is built that
              way, each subsystem, how power or load flows, how it is assembled, and what was assumed.
              <div className="mt-2"><button className="btn-accent btn" onClick={() => useStore.getState().runExplain()}>Explain this machine</button></div>
            </div>)
          : (<>
            <div className="flex flex-wrap items-center gap-1">
              {TABS.map(([k, t]) => <button key={k} onClick={() => setTab(k)}
                className={`rounded-md px-2 py-0.5 text-[11.5px] ${tab === k ? "bg-white/15 text-white" : "text-slate-400 hover:text-white"}`}>{t}</button>)}
              <span className="ml-auto truncate font-mono text-[9.5px] text-slate-500">
                {ex.recorded_at && <span className="mr-1.5 rounded bg-warn/20 px-1 text-warn">RECORDED {ex.recorded_at}</span>}
                Muse Spark · {ex.timing?.total_s ?? ex.timing?.spark_s} s · parts and numbers checked against the model
                {ex.rejected_steps?.length ? ` · ${ex.rejected_steps.length} step(s) rejected` : ""}
              </span>
            </div>
            {ex.scale && !ex.scale.real_size_known && <div className="font-mono text-[9.5px] text-warn">model scale · real size unknown ({ex.scale.note || "no dimension given"})</div>}
            {tab === "walk" && n > 0 && <Walkthrough ex={ex} i={Math.min(i, n - 1)} go={go} play={play} setPlay={setPlay} />}
            {tab === "arch" && <Architecture ex={{ subsystems: [], ...ex }} />}
            {tab === "quiz" && <Quiz quiz={ex.quiz} />}
            {tab === "src" && <div className="min-h-0 flex-1 overflow-auto"><Pic src={ex.source_image} alt="Source drawing of this model" /></div>}
          </>)}
      </div>
    </FloatPanel>
  );
}
