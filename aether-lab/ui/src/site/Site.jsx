import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { motion, useInView, useScroll, useSpring, useTransform, animate } from "framer-motion";
import Lenis from "lenis";
import DotCanvas from "./DotCanvas";
import Icon from "./Icons";
import { CURVE, FEATURES, NOT_YET, PIPELINE, PROVEN, RESULTS, STATS, TECH, VISION } from "./data";

const HoloGears = lazy(() => import("./HoloGears"));

const NAV = [["vision", "Vision"], ["pipeline", "How it works"], ["physics", "Physics"], ["lab", "Lab"], ["status", "Status"]];
const ease = [0.2, 0.7, 0.2, 1];
const up = { hidden: { opacity: 0, y: 28 }, show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease, delay: i * 0.08 } }) };

let lenis = null;
const go = (id) => (e) => {
  e?.preventDefault();
  const el = document.getElementById(id);
  if (!el) return;
  if (lenis) lenis.scrollTo(el, { offset: -72 });
  else el.scrollIntoView({ behavior: "smooth" });
};

function Reveal({ children, i = 0, className = "" }) {
  return (
    <motion.div className={className} variants={up} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }}>
      {children}
    </motion.div>
  );
}

function Heading({ pill, title, lead }) {
  return (
    <div className="mx-auto mb-12 max-w-[720px] text-center md:mb-16">
      <Reveal><span className="s-pill">{pill}</span></Reveal>
      <Reveal i={1}><h2 className="s-h2 mt-5">{title}</h2></Reveal>
      {lead && <Reveal i={2}><p className="s-lead mt-4">{lead}</p></Reveal>}
    </div>
  );
}

/* ---------- nav ---------- */
function Nav() {
  const [solid, setSolid] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = () => setSolid(scrollY > 24);
    on(); addEventListener("scroll", on, { passive: true });
    return () => removeEventListener("scroll", on);
  }, []);
  return (
    <header className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${solid || open ? "border-b border-white/[0.06] bg-[#04060b]/75 backdrop-blur-xl" : ""}`}>
      <div className="container-x flex h-16 items-center justify-between gap-4">
        <a href="#/" onClick={go("top")} className="flex shrink-0 items-center gap-2.5">
          <span className="relative grid h-7 w-7 place-items-center rounded-full border border-cyan-glow/60 shadow-glow">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-glow" />
          </span>
          <span className="text-[15px] font-bold tracking-[0.22em]">AETHER</span>
        </a>
        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map(([id, l]) => (
            <a key={id} href={`#${id}`} onClick={go(id)} className="rounded-lg px-3 py-2 text-[14px] text-slate-400 transition hover:bg-white/[0.05] hover:text-white">{l}</a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <a href="#/lab" className="grad-btn inline-flex h-10 items-center gap-2 rounded-xl px-4 text-[14px] font-semibold text-white transition hover:brightness-110">
            Open Lab <Icon n="arrow" className="h-4 w-4" />
          </a>
          <button onClick={() => setOpen(!open)} aria-label="Menu" className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-slate-300 md:hidden">
            <Icon n={open ? "x" : "menu"} />
          </button>
        </div>
      </div>
      {open && (
        <div className="container-x grid gap-1 pb-4 md:hidden">
          {NAV.map(([id, l]) => (
            <a key={id} href={`#${id}`} onClick={(e) => { setOpen(false); go(id)(e); }} className="rounded-lg px-3 py-2.5 text-[15px] text-slate-300 hover:bg-white/[0.05]">{l}</a>
          ))}
        </div>
      )}
    </header>
  );
}

/* ---------- hero ---------- */
function Hero() {
  const cardRef = useRef(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const onMove = (e) => {
    const r = cardRef.current.getBoundingClientRect();
    setTilt({ x: ((e.clientY - r.top) / r.height - 0.5) * -6, y: ((e.clientX - r.left) / r.width - 0.5) * 8 });
  };
  return (
    <section id="top" className="relative pt-32 md:pt-40">
      <div className="container-x grid items-center gap-12 lg:grid-cols-[1.05fr_1fr] lg:gap-14">
        <div className="min-w-0">
          <Reveal>
            <span className="s-pill"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> Meta AI Hackathon · Push the Frontier</span>
          </Reveal>
          <Reveal i={1}>
            <h1 className="mt-6 text-[clamp(40px,6.2vw,72px)] font-extrabold [text-wrap:balance] leading-[1.02] tracking-[-0.035em]">
              Design in the air.<br /><span className="grad-text">See it in true 3D.</span>
            </h1>
          </Reveal>
          <Reveal i={2}>
            <p className="s-lead mt-6 max-w-[540px]">
              AETHER is a holographic design studio. Import a STEP solid or try the existing multi-view CAD route,
              then use wave-optics simulation to assess how a design may look. Other reconstruction routes remain unavailable.
            </p>
          </Reveal>
          <Reveal i={3}>
            <div className="mt-9 flex flex-wrap gap-3">
              <a href="#/lab" className="grad-btn inline-flex h-12 items-center gap-2 rounded-xl px-6 text-[15px] font-semibold text-white transition hover:brightness-110">
                Launch the Lab <Icon n="arrow" className="h-4 w-4" />
              </a>
              <a href="#physics" onClick={go("physics")} className="inline-flex h-12 items-center gap-2 rounded-xl border border-white/12 bg-white/[0.03] px-6 text-[15px] font-semibold text-slate-200 transition hover:border-cyan-glow/40 hover:bg-white/[0.06]">
                <Icon n="play" className="h-4 w-4" /> Explore the physics
              </a>
            </div>
          </Reveal>
          <Reveal i={4}>
            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-[12px] text-slate-500">
              <span>React Three Fiber</span><span className="hidden h-1 w-1 rounded-full bg-slate-600 sm:block" />
              <span>Muse Spark + SAM 3.1</span><span className="hidden h-1 w-1 rounded-full bg-slate-600 sm:block" />
              <span>Modal GPU</span>
            </div>
          </Reveal>
        </div>

        <Reveal i={2} className="min-w-0">
          <div ref={cardRef} onPointerMove={onMove} onPointerLeave={() => setTilt({ x: 0, y: 0 })}
            className="s-card overflow-hidden p-3 transition-transform duration-300 ease-out sm:p-4"
            style={{ transform: `perspective(1200px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)` }}>
            <div className="flex items-center justify-between px-2 pb-3 pt-1">
              <div className="flex gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" /><span className="h-2.5 w-2.5 rounded-full bg-amber-300/70" /><span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" /></div>
              <span className="truncate pl-3 font-mono text-[11px] text-slate-500">aether-desk · live hologram preview</span>
            </div>
            <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl border border-white/[0.06] bg-[radial-gradient(ellipse_at_50%_70%,rgba(56,189,248,.14),transparent_65%),#050912]">
              <Suspense fallback={<div className="grid h-full place-items-center font-mono text-[12px] text-slate-500">loading hologram…</div>}>
                <HoloGears />
              </Suspense>
              <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-cyan-glow/25 bg-black/40 px-2.5 py-1.5 font-mono text-[10.5px] text-cyan-glow backdrop-blur">z24 × z14 · ratio −24/14</div>
              <div className="pointer-events-none absolute bottom-3 right-3 rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 font-mono text-[10.5px] text-slate-300 backdrop-blur">move the mouse to tilt</div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              {STATS.map((s, i) => (
                <div key={i} className="min-w-0 rounded-xl border border-white/[0.07] bg-white/[0.025] px-3.5 py-3">
                  <div className="truncate text-[clamp(17px,2vw,22px)] font-bold tracking-tight">
                    <span className="grad-text">{s.v}</span><span className="ml-1 text-[13px] font-medium text-slate-400">{s.u}</span>
                  </div>
                  <div className="mt-1 text-[12px] leading-snug text-slate-400">{s.l}</div>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Marquee() {
  const row = [...TECH, ...TECH];
  return (
    <div className="marquee-mask relative mt-24 overflow-hidden border-y border-white/[0.06] bg-white/[0.015] py-5 md:mt-32">
      <div className="marquee">
        {row.map((t, i) => (
          <span key={i} className="flex shrink-0 items-center gap-3 px-6 font-mono text-[13px] uppercase tracking-[0.14em] text-slate-400">
            <span className="h-1.5 w-1.5 rotate-45 bg-gradient-to-br from-cyan-300 to-violet-500" />{t}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------- vision ---------- */
function Vision() {
  return (
    <section id="vision" className="s-section">
      <div className="container-x">
        <Heading pill="Vision" title={<>A workshop where the <span className="grad-text">model floats in front of you</span></>}
          lead="Inspired by the design labs of science fiction, built on real physics. Here is what AETHER is for." />
        <div className="grid gap-5 md:grid-cols-3">
          {VISION.map((v, i) => (
            <Reveal key={v.k} i={i} className="min-w-0">
              <div className="s-card s-card-hover group h-full overflow-hidden p-7">
                <div className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl transition-opacity duration-500 group-hover:opacity-100 md:opacity-0" />
                <div className="font-mono text-[13px] text-cyan-glow">{v.k}</div>
                <h3 className="mt-4 text-[21px] font-bold tracking-tight">{v.t}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-slate-400">{v.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- pipeline timeline ---------- */
function Pipeline() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 70%", "end 60%"] });
  const h = useSpring(useTransform(scrollYProgress, [0, 1], ["0%", "100%"]), { stiffness: 120, damping: 30 });
  return (
    <section id="pipeline" className="s-section">
      <div className="container-x">
        <Heading pill="How it works" title={<>From an idea to a <span className="grad-text">checked hologram</span></>}
          lead="Five steps, each one a real tool the agent calls. Scroll to follow the light." />
        <div ref={ref} className="relative mx-auto max-w-[860px]">
          <div className="absolute bottom-2 left-[19px] top-2 w-px bg-white/[0.08] md:left-1/2 md:-translate-x-1/2" />
          <motion.div style={{ height: h }} className="absolute left-[19px] top-2 w-px bg-gradient-to-b from-cyan-300 via-indigo-400 to-violet-500 shadow-[0_0_12px_rgba(95,225,255,.8)] md:left-1/2 md:-translate-x-1/2" />
          <div className="grid gap-8 md:gap-10">
            {PIPELINE.map((p, i) => {
              const right = i % 2 === 1;
              return (
                <div key={i} className="relative grid grid-cols-[40px_1fr] items-start gap-4 md:grid-cols-[1fr_40px_1fr] md:gap-8">
                  <div className={`hidden md:block ${right ? "" : "md:col-start-1"}`}>
                    {!right && <Step p={p} i={i} align="right" />}
                  </div>
                  <div className="relative z-10 col-start-1 row-start-1 grid h-10 w-10 place-items-center rounded-full border border-cyan-glow/40 bg-[#070b14] font-mono text-[13px] font-semibold text-cyan-glow shadow-glow md:col-start-2">
                    {i + 1}
                  </div>
                  <div className="col-start-2 row-start-1 min-w-0 md:col-start-3">
                    {right ? <Step p={p} i={i} /> : <div className="md:hidden"><Step p={p} i={i} /></div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function Step({ p, i, align = "left" }) {
  return (
    <Reveal i={0} className="min-w-0">
      <div className={`s-card s-card-hover p-6 ${align === "right" ? "md:text-right" : ""}`}>
        <span className="s-tag">{p.tag}</span>
        <h3 className="mt-3 text-[19px] font-bold tracking-tight">{p.t}</h3>
        <p className="mt-2 text-[14.5px] leading-relaxed text-slate-400">{p.d}</p>
      </div>
    </Reveal>
  );
}

/* ---------- interactive physics ---------- */
function Physics() {
  const [k, setK] = useState(17); // z = +50 mm
  const narrow = useNarrow();
  const W = narrow ? 360 : 640, H = narrow ? 260 : 300, L = 34, R = 12, T = 16, B = 40;
  const x = (z) => L + ((z + 120) / 240) * (W - L - R);
  const y = (v) => T + (1 - v / 100) * (H - T - B);
  const path = (arr) => arr.map((v, i) => `${i ? "L" : "M"}${x(CURVE.z[i]).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const z = CURVE.z[k], d = CURVE.desk[k], s = CURVE.screen[k];
  const sharp = d >= 80;
  return (
    <section id="physics" className="s-section">
      <div className="container-x">
        <Heading pill="Interactive physics" title={<>Drag the model <span className="grad-text">up and down</span></>}
          lead="How sharp does a part look at each height above the desk? A simulated eye (4 mm pupil, MTF at 15 cpd, looking down at 50°) compares AETHER's 1D desk hologram with a perfect full 2D hologram and with an ordinary 3D screen." />
        <div className="grid gap-5 lg:grid-cols-[1.55fr_1fr]">
          <Reveal className="min-w-0">
            <div className="s-card h-full p-5 sm:p-7">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12.5px] text-slate-400">
                <span className="flex items-center gap-2"><span className="h-0.5 w-5 rounded bg-cyan-300" />AETHER desk (1D hologram)</span>
                <span className="flex items-center gap-2"><span className="h-0.5 w-5 rounded border-t-2 border-dashed border-violet-400" />Ordinary 3D screen</span>
                <span className="flex items-center gap-2"><span className="h-0.5 w-5 rounded bg-white/50" />Full 2D hologram</span>
              </div>
              <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 block h-auto w-full" role="img" aria-label="Sharpness versus height chart">
                <defs>
                  <linearGradient id="dg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#5fe1ff" stopOpacity=".28" /><stop offset="1" stopColor="#5fe1ff" stopOpacity="0" /></linearGradient>
                </defs>
                <rect x={x(-108)} y={T} width={x(87) - x(-108)} height={H - T - B} fill="rgba(52,211,153,.06)" />
                <text x={(x(-108) + x(87)) / 2} y={H - B - 10} textAnchor="middle" fill="#34d399" fontSize="11" fontFamily="JetBrains Mono Variable">sharp zone −108…+87 mm</text>
                {[0, 25, 50, 75, 100].map((v) => (
                  <g key={v}>
                    <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="rgba(255,255,255,.06)" />
                    <text x={L - 8} y={y(v) + 4} textAnchor="end" fill="#64748b" fontSize="11" fontFamily="JetBrains Mono Variable">{v}</text>
                  </g>
                ))}
                {(narrow ? [-120, 0, 120] : [-120, -60, 0, 60, 120]).map((v) => (
                  <text key={v} x={x(v)} y={H - B + 20} textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="JetBrains Mono Variable">{v > 0 ? "+" + v : v}</text>
                ))}
                <text x={W - R} y={H - 4} textAnchor="end" display={narrow ? "none" : undefined} fill="#475569" fontSize="10.5" fontFamily="JetBrains Mono Variable">height above panel (mm)</text>
                <line x1={L} x2={W - R} y1={y(100)} y2={y(100)} stroke="rgba(255,255,255,.45)" strokeWidth="1.5" />
                <path d={`${path(CURVE.desk)}L${x(120)},${y(0)}L${x(-120)},${y(0)}Z`} fill="url(#dg)" />
                <path d={path(CURVE.screen)} fill="none" stroke="#a78bfa" strokeWidth="2" strokeDasharray="6 5" />
                <path d={path(CURVE.desk)} fill="none" stroke="#5fe1ff" strokeWidth="2.5" style={{ filter: "drop-shadow(0 0 6px rgba(95,225,255,.7))" }} />
                <line x1={x(z)} x2={x(z)} y1={T} y2={H - B} stroke="rgba(255,255,255,.35)" strokeDasharray="3 4" />
                <circle cx={x(z)} cy={y(s)} r="5" fill="#a78bfa" />
                <circle cx={x(z)} cy={y(d)} r="6" fill="#5fe1ff" stroke="#fff" strokeWidth="2" />
              </svg>
              <div className="mt-5 flex items-center gap-4">
                <span className="shrink-0 font-mono text-[12px] text-slate-500">−120</span>
                <input type="range" min={0} max={CURVE.z.length - 1} value={k} onChange={(e) => setK(+e.target.value)} className="s-range" aria-label="Height above the panel" />
                <span className="shrink-0 font-mono text-[12px] text-slate-500">+120</span>
              </div>
            </div>
          </Reveal>
          <Reveal i={1} className="min-w-0">
            <div className="s-card flex h-full flex-col p-5 sm:p-7">
              <div className="font-mono text-[12px] uppercase tracking-[0.16em] text-slate-500">at height</div>
              <div className="mt-1 text-[44px] font-extrabold leading-none tracking-tight">{z > 0 ? "+" : ""}{z}<span className="ml-1.5 text-[18px] font-semibold text-slate-400">mm</span></div>
              <div className={`mt-4 inline-flex w-fit items-center gap-2 rounded-full px-3 py-1 text-[12.5px] font-semibold ${sharp ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${sharp ? "bg-emerald-400" : "bg-amber-400"}`} />{sharp ? "inside the sharp zone" : "outside the sharp zone"}
              </div>
              <div className="mt-6 grid gap-4">
                <Bar label="AETHER desk" v={d} c="from-cyan-300 to-sky-500" />
                <Bar label="Ordinary 3D screen" v={s} c="from-violet-400 to-fuchsia-500" />
                <Bar label="Full 2D hologram" v={100} c="from-slate-300 to-slate-400" />
              </div>
              <p className="mt-auto pt-6 text-[13px] leading-relaxed text-slate-500">
                % of a full 2D hologram's sharpness at the same eye focus. Simulation, not a measurement of a built panel.
              </p>
            </div>
          </Reveal>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {RESULTS.map((r, i) => <Result key={i} r={r} i={i} />)}
        </div>
      </div>
    </section>
  );
}

function useNarrow() {
  const q = "(max-width: 640px)";
  const [n, setN] = useState(() => matchMedia(q).matches);
  useEffect(() => { const m = matchMedia(q), on = () => setN(m.matches); m.addEventListener("change", on); return () => m.removeEventListener("change", on); }, []);
  return n;
}

function Bar({ label, v, c }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-[13.5px]"><span className="text-slate-300">{label}</span><span className="font-mono font-semibold text-white">{v.toFixed(1)}%</span></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div className={`h-full rounded-full bg-gradient-to-r ${c}`} animate={{ width: `${v}%` }} transition={{ type: "spring", stiffness: 140, damping: 22 }} />
      </div>
    </div>
  );
}

function Counter({ to, dec }) {
  const ref = useRef(null);
  const seen = useInView(ref, { once: true });
  useEffect(() => {
    if (!seen) return;
    const c = animate(0, to, { duration: 1.4, ease: "easeOut", onUpdate: (x) => { if (ref.current) ref.current.textContent = x.toFixed(dec); } });
    return () => c.stop();
  }, [seen, to, dec]);
  return <span ref={ref}>{(0).toFixed(dec)}</span>;
}

function Result({ r, i }) {
  return (
    <Reveal i={i} className="min-w-0">
      <div className="s-card s-card-hover h-full p-6">
        <div className="text-[34px] font-extrabold tracking-tight"><span className="grad-text"><Counter to={r.v} dec={r.pct ? 1 : 3} /></span>{r.pct && <span className="ml-0.5 text-[18px] text-slate-400">%</span>}</div>
        <div className="mt-2 text-[15px] font-semibold">{r.l}</div>
        <div className="mt-1 text-[13px] leading-snug text-slate-400">{r.s}</div>
      </div>
    </Reveal>
  );
}

/* ---------- lab features ---------- */
function Lab() {
  return (
    <section id="lab" className="s-section">
      <div className="container-x">
        <Heading pill="The Lab" title={<>Everything you need to <span className="grad-text">build in the air</span></>}
          lead="The AETHER Lab is a Blender-style 3D editor with an AI agent, hand tracking and a physics panel that grades every design." />
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.t} i={i % 3} className="min-w-0">
              <Spot className="h-full p-7">
                <div className="grid h-12 w-12 place-items-center rounded-xl border border-cyan-glow/25 bg-gradient-to-br from-cyan-400/15 to-violet-500/15 text-cyan-glow">
                  <Icon n={f.i} className="h-6 w-6" />
                </div>
                <h3 className="mt-5 text-[19px] font-bold tracking-tight">{f.t}</h3>
                <p className="mt-2 text-[14.5px] leading-relaxed text-slate-400">{f.d}</p>
              </Spot>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// card with a light that follows the cursor
function Spot({ children, className = "" }) {
  const [p, setP] = useState(null);
  return (
    <div onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); setP([e.clientX - r.left, e.clientY - r.top]); }}
      onPointerLeave={() => setP(null)} className={`s-card s-card-hover overflow-hidden ${className}`}>
      <div className="pointer-events-none absolute inset-0 transition-opacity duration-300" style={{
        opacity: p ? 1 : 0,
        background: p ? `radial-gradient(320px circle at ${p[0]}px ${p[1]}px, rgba(95,225,255,.12), transparent 60%)` : "none",
      }} />
      <div className="relative">{children}</div>
    </div>
  );
}

/* ---------- honest status ---------- */
function Status() {
  return (
    <section id="status" className="s-section">
      <div className="container-x">
        <Heading pill="Honest status" title={<>What is <span className="grad-text">proven</span>, and what is not yet</>}
          lead="AETHER is a simulation-first project. Every number on this page comes from code you can run; none of it is a photo of a finished device." />
        <div className="grid gap-5 md:grid-cols-2">
          <Reveal className="min-w-0">
            <div className="s-card h-full p-7">
              <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-emerald-400/10 text-emerald-300"><Icon n="check" /></span><h3 className="text-[19px] font-bold">Proven in simulation</h3></div>
              <ul className="mt-5 grid gap-3">
                {PROVEN.map((t) => <li key={t} className="flex gap-3 text-[14.5px] leading-relaxed text-slate-300"><Icon n="check" className="mt-1 h-4 w-4 shrink-0 text-emerald-400" sw={2.2} />{t}</li>)}
              </ul>
            </div>
          </Reveal>
          <Reveal i={1} className="min-w-0">
            <div className="s-card h-full p-7">
              <div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-amber-400/10 text-amber-300"><Icon n="loop" /></span><h3 className="text-[19px] font-bold">Not built yet</h3></div>
              <ul className="mt-5 grid gap-3">
                {NOT_YET.map((t) => <li key={t} className="flex gap-3 text-[14.5px] leading-relaxed text-slate-300"><span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />{t}</li>)}
              </ul>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="pb-24 pt-4 md:pb-32">
      <div className="container-x">
        <Reveal>
          <div className="relative overflow-hidden rounded-[28px] border border-white/10 px-6 py-14 text-center sm:px-12 md:py-20"
            style={{ background: "radial-gradient(ellipse at 20% 0%, rgba(56,189,248,.25), transparent 55%), radial-gradient(ellipse at 90% 100%, rgba(168,85,247,.28), transparent 55%), #070b16" }}>
            <h2 className="s-h2 mx-auto max-w-[680px]">Ready to build your first machine in the air?</h2>
            <p className="s-lead mx-auto mt-4 max-w-[560px]">Open the Lab to import a STEP solid or try the supported multi-view CAD route. Machine and part-photo reconstruction are unavailable.</p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <a href="#/lab" className="grad-btn inline-flex h-12 items-center gap-2 rounded-xl px-7 text-[15px] font-semibold text-white transition hover:brightness-110">Open AETHER Lab <Icon n="arrow" className="h-4 w-4" /></a>
              <a href="#top" onClick={go("top")} className="inline-flex h-12 items-center rounded-xl border border-white/15 px-7 text-[15px] font-semibold text-slate-200 transition hover:bg-white/[0.06]">Back to top</a>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.06] py-8">
      <div className="container-x flex flex-col items-center justify-between gap-3 text-center text-[13px] text-slate-500 md:flex-row md:text-left">
        <span>© 2026 AETHER · Ng Wei Bin · Holographic design research</span>
        <span className="font-mono text-[12px]">Tip: move and click anywhere, the light field reacts.</span>
      </div>
    </footer>
  );
}

/* ---------- intro reveal ---------- */
function Intro({ onDone }) {
  const [out, setOut] = useState(false);
  useEffect(() => { const t = setTimeout(() => setOut(true), 1500); return () => clearTimeout(t); }, []);
  useEffect(() => { if (out) { const t = setTimeout(onDone, 1000); return () => clearTimeout(t); } }, [out, onDone]);
  return (
    <div onClick={() => setOut(true)} className="fixed inset-0 z-[70] grid cursor-pointer place-items-center bg-[#04060b] transition-[clip-path,opacity] duration-1000 ease-[cubic-bezier(.7,0,.2,1)]"
      style={{ clipPath: out ? "circle(0% at 50% 50%)" : "circle(150% at 50% 50%)" }}>
      <div className="text-center">
        <div className="relative mx-auto grid h-20 w-20 place-items-center">
          <span className="absolute inset-0 animate-ping rounded-full border border-cyan-glow/40" />
          <span className="absolute inset-2 rounded-full border border-cyan-glow/60 shadow-glow" />
          <span className="h-4 w-4 rounded-full bg-cyan-glow shadow-glow" />
        </div>
        <div className="mt-6 text-[22px] font-bold tracking-[0.5em] text-white">AETHER</div>
        <div className="mt-2 font-mono text-[11px] uppercase tracking-[0.3em] text-slate-500">click to enter</div>
      </div>
    </div>
  );
}

export default function Site() {
  const [intro, setIntro] = useState(() => { try { return !sessionStorage.getItem("aether-intro"); } catch { return true; } });
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    lenis = new Lenis({ lerp: 0.1 });
    let id = requestAnimationFrame(function raf(t) { lenis.raf(t); id = requestAnimationFrame(raf); });
    return () => { cancelAnimationFrame(id); lenis.destroy(); lenis = null; document.documentElement.classList.remove("lenis", "lenis-smooth"); };
  }, []);
  useEffect(() => { document.title = "AETHER · Design in the air"; }, []);
  const done = () => { setIntro(false); try { sessionStorage.setItem("aether-intro", "1"); } catch { /* private mode */ } };
  return (
    <div className="site relative min-h-screen overflow-x-clip bg-[#04060b]">
      <div className="pointer-events-none fixed inset-0 z-0" style={{ background: "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(56,189,248,.14), transparent), radial-gradient(ellipse 60% 40% at 100% 60%, rgba(139,92,246,.10), transparent)" }} />
      <DotCanvas />
      <div className="relative z-10">
        <Nav />
        <main>
          <Hero />
          <Marquee />
          <Vision />
          <Pipeline />
          <Physics />
          <Lab />
          <Status />
          <CTA />
        </main>
        <Footer />
      </div>
      {intro && <Intro onDone={done} />}
    </div>
  );
}
