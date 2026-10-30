import { useState } from "react";
import { HEAVY, useStore } from "../store";
import FloatPanel from "./FloatPanel";
import Icon from "./Icon";
import { LineChart, SineLoader, Slider } from "./Charts";
import { Num } from "./Outliner";

function Section({ title, children, right, busy }) {
  return (
    <section className="space-y-2 border-t border-white/[0.06] px-3.5 py-3">
      <div className="flex items-center justify-between"><span className="label">{title}</span>{busy ? <SineLoader label="" /> : right}</div>
      {children}
    </section>
  );
}

function Stat({ k, v, hot }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-black/25 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-[0.14em] text-silver">{k}</div>
      <div className={`readout mt-0.5 truncate ${hot ? "text-cyan-glow" : ""}`}>{v}</div>
    </div>
  );
}

function EmptyHolo({ lab, busy, onRun }) {
  return (
    <div className="relative grid aspect-square place-items-center overflow-hidden rounded-[10px] bg-[radial-gradient(circle_at_50%_55%,rgba(95,225,255,.10),transparent_60%)]">
      <div className="absolute h-40 w-40 animate-[spin_14s_linear_infinite] rounded-full border border-dashed border-cyan-glow/20" />
      <div className="absolute h-28 w-28 animate-[spin_9s_linear_infinite_reverse] rounded-full border border-cyan-glow/15 border-t-cyan-glow/60" />
      <div className="relative space-y-2 text-center">
        <button onClick={onRun} disabled={busy} className="btn-accent rounded-full px-4">{busy ? "Computing…" : "Calculate hologram"}</button>
        <div className="font-mono text-[9.5px] text-silver">{lab ? "lab hologram follows the eye view" : "F12 · ~15 s on CPU"}</div>
      </div>
    </div>
  );
}

const Empty = ({ text }) => <div className="grid aspect-square place-items-center rounded-lg border border-dashed border-white/10 px-3 text-center text-[10.5px] text-silver">{text}</div>;

function Bars({ rows }) {
  return rows.map(([k, v, max = 100, color = "#5fe1ff"]) => (
    <div key={k} className="flex items-center gap-2">
      <span className="w-20 truncate text-[10.5px] text-silver">{k}</span>
      <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/[0.07]">
        <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.min(100, v / max * 100)}%`, background: color, boxShadow: `0 0 8px ${color}` }} />
      </div>
      <span className="readout w-11 text-right text-[11px]">{v}{max === 100 ? "%" : ""}</span>
    </div>
  ));
}

function Shot({ src, label, v, good }) {
  return (
    <div className="hud-frame relative">
      {src ? <img src={src} className="aspect-square w-full rounded-[10px] bg-black object-cover" /> : <div className="aspect-square rounded-[10px] bg-black/40" />}
      <span className="hud-tag absolute left-1.5 top-1.5 !text-[8.5px]">{label}</span>
      <span className={`absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[11px] ${good ? "text-ok" : "text-warn"}`}>{v}%</span>
    </div>
  );
}

// Closed loop: Muse Spark changes the design, the wave-optics eye model re-scores it, until every part is sharp.
function LoopCard({ opt }) {
  const b = opt.before, a = opt.after;
  return <>
    <div className="grid grid-cols-2 gap-2">
      <Shot src={opt.before_img} label="BEFORE" v={b.min_sharpness_pct} good={b.min_sharpness_pct >= opt.target_pct} />
      <Shot src={opt.after_img} label="AFTER" v={a.min_sharpness_pct} good={opt.pass} />
    </div>
    <div className="space-y-1">
      {opt.rounds.map((r) => (
        <div key={r.round} className="flex items-center gap-2 rounded-md border border-white/[0.06] bg-black/25 px-2 py-1 font-mono text-[10px]">
          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${r.pass ? "bg-ok" : "bg-warn"}`} />
          <span className="text-white/80">round {r.round}</span>
          <span className="truncate text-silver">{r.edits.map((e) => [e.position && `move→${e.position.map(Math.round).join(",")}`, e.rotation && `rot ${e.rotation.map(Math.round).join(",")}`, e.scale && `scale ${e.scale.map((x) => +x.toFixed(2)).join(",")}`].filter(Boolean).join(" ")).join(" · ")}</span>
          <span className="ml-auto text-cyan-glow">{r.min_sharpness_pct}%</span>
        </div>))}
    </div>
    <p className="text-[10.5px] leading-snug text-silver">
      Worst part {b.min_sharpness_pct}% → {a.min_sharpness_pct}% · parts ok {b.parts_ok} → {a.parts_ok}/{opt.parts} · height {b.design_z_mm.join("…")} → {a.design_z_mm.join("…")} mm.
      Images: eye focused on the top of the design. Simulation, not a built display.</p>
  </>;
}

function SamCard({ sam }) {
  if (sam.mode === "blueprint") return <>
    <img src={sam.overlay} className="w-full rounded-[10px] object-contain" />
    <div className="flex flex-wrap gap-1.5">{Object.entries(sam.found).map(([k, v]) => <span key={k} className="chip !text-[10px]">{k} × {v}</span>)}</div>
    <div className="scroll-thin max-h-28 space-y-0.5 overflow-y-auto font-mono text-[10px] text-silver">
      {sam.parts.map((p) => <div key={p.n} className="flex gap-2"><span className="w-5 text-cyan-glow">{p.n}</span><span className="w-12 truncate text-white/80">{p.label}</span>
        <span>{p.centre_mm.map(Math.round).join(",")}</span><span className="ml-auto">{p.radius_mm ? `r ${p.radius_mm}${p.lobes ? ` · ${p.lobes}T` : ""}` : `${Math.round(p.length_mm)}×${Math.round(p.width_mm)} ∠${p.angle_deg}°`}</span></div>)}
    </div>
    {sam.scale_source && <p className="font-mono text-[10px] text-silver">scale: <span className={sam.scale_source.startsWith("read") ? "text-cyan-glow" : "text-warn"}>{sam.scale_source}</span>{sam.view ? ` · view: ${sam.view}` : ""}</p>}
    <p className="text-[10.5px] leading-snug text-silver">{sam.read_by?.startsWith("Muse") ? "Muse Spark read the drawing and boxed each part; SAM 3.1 traced every box." : "SAM 3.1 searched the drawing once per part type."} Every part was rebuilt as the solid it is: involute gears that mesh (module and phase solved), pins through the stack, plates with their real holes, frame plates front and back. The drawing stands upright on the desk. Thicknesses are engineering rules, marked as assumed in each part.</p>
  </>;
  return <>
    <div className="grid grid-cols-[1fr_88px] gap-2">
      <img src={sam.overlay} className="w-full rounded-[10px] object-cover" />
      <div className="grid place-items-center rounded-[10px] bg-[conic-gradient(#ffffff10_25%,transparent_0_50%,#ffffff10_0_75%,transparent_0)] bg-[length:12px_12px]">
        <img src={sam.cutout} className="max-h-[88px] max-w-[84px] object-contain" />
      </div>
    </div>
    <div className="grid grid-cols-3 gap-1.5">
      <Stat k="size" v={`${Math.round(sam.width_mm)}×${Math.round(sam.height_mm)}`} />
      <Stat k="lobes" v={sam.lobes_around_centre || "—"} hot={sam.lobes_around_centre > 0} />
      <Stat k="hole" v={sam.centre_hole ? `r ${sam.centre_hole_radius_mm}` : "none"} />
      <Stat k="round" v={sam.circularity} /><Stat k="found" v={sam.found} />
      <Stat k="conf" v={sam.confidence != null ? sam.confidence.toFixed(2) : "—"} />
    </div>
    <p className="text-[10.5px] leading-snug text-silver">SAM 3.1 found “{sam.object}” in your photo{sam.tilt_corrected_deg ? `; the ${sam.tilt_corrected_deg}° camera tilt was corrected` : ""}. Lobes come from the FFT of the outline. Muse Spark rebuilt it from these numbers and the cut-out; depth is guessed from one view and the size is {sam.size_source || "assumed"}.</p>
  </>;
}

const DISPLAYS = [["desk1d", "Desk 1D"], ["full2d", "full 2D"], ["screen3d", "3D screen"]];

export default function PhysicsPanel() {
  const s = useStore((x) => x.state);
  const r = useStore((x) => x.results);
  const busy = useStore((x) => x.busy);
  const timing = useStore((x) => x.timing);
  const open = useStore((x) => x.panels.physics);
  const compute = useStore((x) => x.compute);
  const view = useStore((x) => x.view);
  const st = useStore.getState();
  const [k, setK] = useState(3);
  const [img, setImg] = useState("focus");
  const eyeShown = !!r.eye?.latest;
  const setEyeShown = (v) => r.eye && useStore.setState((x) => ({ results: { ...x.results, eye: { ...x.results.eye, latest: v } } }));
  const eyeDisplay = useStore((x) => x.eyeDisplay);
  const eyeColor = useStore((x) => x.eyeColor);
  const backend = useStore((x) => x.backend);
  const [opt, setOpt] = useState(false);
  const looping = useStore((x) => x.progress.some((p) => p.label === "desk_score"));
  const d = s.display, sweep = r.sweep;
  const setI = (i) => useStore.setState((x) => ({ results: { ...x.results, sweep: { ...x.results.sweep, i: Math.round(i) } } }));
  const anyBusy = HEAVY.some((h) => busy[h]);
  const lastT = timing.last && HEAVY.includes(timing.last) ? `${timing[timing.last]} ms` : "—";
  const ei = eyeShown || !sweep ? r.eye?.info : null;           // the single eye view, when it is what is shown
  const hero = ei ? { v: ei.sharpness_vs_full_2d_pct, z: ei.focus_z_mm, sp: ei.speckle_contrast_pct, out: ei.parts_outside_window_pct }
    : sweep ? { v: sweep.sharp[sweep.i], z: sweep.depths[sweep.i], sp: sweep.speckle, out: sweep.outside } : null;
  const pic = img === "focus" ? (eyeShown && r.eye ? r.eye.img : sweep?.imgs[sweep.i]) : img === "lab" ? r.recon?.img : r.hologram?.img;

  return (
    <FloatPanel id="physics" title="Physics Engine" icon="wave" open={open} busy={anyBusy}
      onClose={() => st.setPanel("physics", false)} className="bottom-[78px] right-3 top-[60px] w-[330px]">
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div className="px-3.5 pb-3">
          <div className="flex items-end justify-between">
            <div>
              <div className="label">sharp vs full 2D · same focus</div>
              <div className="mt-1 flex items-baseline gap-1">
                <span className={`hero-num text-[46px] ${hero ? "text-white glow-text" : "text-white/25"}`}>{hero ? Math.round(hero.v) : "--"}</span>
                <span className="font-display text-[18px] text-silver">%</span>
              </div>
              <div className="mt-1 font-mono text-[10px] text-silver">{hero ? <>focus <span className="text-cyan-glow">{hero.z} mm</span> · vs full 2D</> : "calculate to measure"}</div>
            </div>
            <div className="space-y-1.5 text-right">
              {[["speckle", hero?.sp != null ? `${hero.sp}%` : "--", hero?.sp > 4.4 ? "text-warn" : "text-white"],
                ["outside window", hero?.out != null ? `${hero.out}%` : "--", hero?.out > 0 ? "text-warn" : "text-white"],
                ["last run", lastT, "text-white"]].map(([k2, v, c]) => (
                <div key={k2}><div className="label !text-[8.5px]">{k2}</div><div className={`font-mono text-[12px] tabular-nums ${c}`}>{v}</div></div>))}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {[view.section && `cut ${view.section.toUpperCase()}`, view.explode > 0 && `exploded ${Math.round(view.explode * 100)}%`, view.xray && "x-ray"].filter(Boolean).map((t) =>
              <span key={t} className="chip !border-magenta-glow/30 !text-[10px] text-magenta-glow">{t}</span>)}
            <span className={`chip !text-[10px] ${compute === "modal" ? "!border-magenta-glow/30 text-magenta-glow" : ""}`}>{compute === "modal" ? `Modal ${backend?.startsWith("cupy") ? "T4 GPU" : backend ? "· " + backend.split(" ")[0] : "GPU"}` : "local CPU"}</span>
            <span className="chip !text-[10px]">{eyeColor ? "RGB 638 · 520 · 450 nm" : "λ 530 nm"}</span>
          </div>
        </div>

        {r.sam && <Section title={r.sam.mode === "blueprint" ? "SAM 3.1 · machine drawing" : "SAM 3.1 · photo of a real part"}><SamCard sam={r.sam} /></Section>}

        <Section title="AI design loop" busy={busy.chat && looping}
          right={<button className="btn whitespace-nowrap px-2 py-0.5 text-[11px]" disabled={busy.chat || !s.parts.length} onClick={() => st.optimize(80)}><Icon name="sparkle" />Fix for desk</button>}>
          {r.opt ? <LoopCard opt={r.opt} />
            : <p className="text-[11px] text-silver">Muse Spark moves, turns or scales the design; the wave-optics eye re-scores every part on the AETHER Desk; repeat until all parts are ≥80% sharp and inside the window.</p>}
        </Section>

        <Section title="Hologram · what your eye sees" busy={busy.make_hologram || busy.focus_sweep || busy.eye_view || busy.propagate || busy.desk_wave_view}
          right={<div className="flex gap-0.5 rounded-md bg-black/30 p-0.5">{[["focus", "eye"], ["lab", "lab"], ["holo", "phase"]].map(([kk, l]) => (
            <button key={kk} onClick={() => setImg(kk)} className={`rounded px-1.5 py-0.5 font-mono text-[9.5px] ${img === kk ? "bg-white/10 text-white" : "text-silver"}`}>{l}</button>))}</div>}>
          {img === "focus" && <div className="flex gap-0.5 rounded-md bg-black/30 p-0.5">{DISPLAYS.map(([kk, l]) => (
            <button key={kk} onClick={() => st.setEyeDisplay(kk)} disabled={busy.focus_sweep}
              className={`flex-1 rounded px-1 py-0.5 text-[10px] ${eyeDisplay === kk ? "bg-white/10 text-white" : "text-silver hover:text-white"}`}>{l}</button>))}
            <button onClick={() => st.setEyeColor(!eyeColor)} disabled={busy.focus_sweep} title={eyeColor ? "Full colour: red 638, green 520, blue 450 nm lasers" : "One green 530 nm laser"}
              className="ml-0.5 rounded px-1.5 py-0.5 font-mono text-[9.5px] font-semibold"
              style={eyeColor ? { background: "linear-gradient(90deg,#ff5a5a33,#5aff8a33,#5a8aff33)", color: "#fff" } : { color: "#6dffa0" }}>{eyeColor ? "RGB" : "530"}</button>
          </div>}
          <div className="flex gap-2.5">
            <div className="hud-frame relative flex-1">
              {pic ? <>
                <img src={pic} className="aspect-square w-full rounded-[10px] bg-black object-cover" />
                <div className="scanlines pointer-events-none absolute inset-0 rounded-[10px]" />
                <span className="hud-tag absolute right-2 top-2 !text-[8.5px]">{img === "focus" ? `SIMULATED RETINA · ${(sweep?.lasers || r.eye?.info.lasers_nm || [530]).join("/")} nm` : img === "lab" ? "LAB SLM DEMO · NOT THE DESK" : "PHASE · LAB SLM"}</span>
              </> : <EmptyHolo lab={img !== "focus"} busy={busy.eye_view || busy.focus_sweep || busy.make_hologram} onRun={() => st.hologram()} />}
              {img === "focus" && sweep && !eyeShown && <div className="absolute bottom-1.5 left-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-cyan-glow">focus {sweep.depths[sweep.i]} mm · {sweep.sharp[sweep.i]}%</div>}
              {img === "focus" && eyeShown && <button onClick={() => setEyeShown(false)} className="absolute bottom-1.5 left-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-cyan-glow">eye view · speckle {r.eye.info.speckle_contrast_pct}% ✕</button>}
              {img === "lab" && r.recon && <div className="absolute bottom-1.5 left-1.5 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-cyan-glow">lab reconstruction{r.recon.z != null ? ` · z ${r.recon.z} mm` : ""}</div>}
            </div>
            {sweep && img === "focus" && (
              <div className="flex gap-1">
                <div className="flex flex-col-reverse justify-between py-1 text-right font-mono text-[8.5px] tabular-nums">
                  {sweep.depths.map((z, i) => <span key={i} className={i === sweep.i ? "text-cyan-glow" : "text-silver/60"}>{Math.round(z)}</span>)}
                </div>
                <Slider vertical value={sweep.i} min={0} max={sweep.imgs.length - 1} step={1} onChange={(v) => { setEyeShown(false); setI(v); }} className="flex-1" />
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <button className="btn" disabled={busy.focus_sweep || busy.make_hologram} onClick={() => st.hologram()}><Icon name="holo" />Calculate</button>
            <button className="btn" disabled={!sweep || busy.eye_view} onClick={() => { setImg("focus"); st.eyeView(); }}><Icon name="eye" />Eye view</button>
            <button className="btn" disabled={!s.parts.length || busy.eye_view} title="Left and right eye, 63 mm apart: each eye gets its own view"
              onClick={() => { setImg("focus"); st.eyeView({ which_eye: "both" }); }}><Icon name="eye" />Both eyes</button>
            <button className="btn" disabled={!s.parts.length || busy.desk_wave_view} title="True-scale wave simulation of the desk panel (slower)"
              onClick={() => st.tool("desk_wave_view", sweep ? { focus_z_mm: sweep.depths[sweep.i] } : {})}><Icon name="wave" />Desk wave check</button>
          </div>
          {r.wave && <div className="space-y-1">
            <div className="grid grid-cols-2 gap-1.5">
              <div className="relative"><img src={r.wave.wave} className="aspect-square w-full rounded-[8px] bg-black object-cover" /><span className="hud-tag absolute left-1 top-1 !text-[8px]">WAVE · PANEL</span></div>
              <div className="relative"><img src={r.wave.model} className="aspect-square w-full rounded-[8px] bg-black object-cover" /><span className="hud-tag absolute left-1 top-1 !text-[8px]">EYE MODEL</span></div>
            </div>
            <p className="text-[10px] leading-snug text-silver">Left: the desk panel itself simulated at full size ({r.wave.info.projected_pitch_um} µm projected pitch, eye box {r.wave.info.eye_box_mm} mm, focus {r.wave.info.focus_z_mm} mm, {r.wave.info.encode === "none" ? "ideal complex modulation" : r.wave.info.encode}). Right: the fast eye model used everywhere else. They should agree.</p>
          </div>}
          <p className="text-[10.5px] leading-snug text-silver">
            {img === "focus" ? <>A seated viewer 70 cm away, eye focused at the slider height. Wave-optics eye (v9, 4 mm pupil), Window Law, 3×3 sparse-group speckle (v11). {sweep?.display}{view.section || view.explode || view.xray ? " · cut / exploded / x-ray as shown" : ""}. Simulation, not a built display.</>
              : img === "lab" ? <>Small lab-SLM demo (8 µm, 8 mm): the view shrunk about 40× and reconstructed by angular-spectrum propagation. Light does not shrink with the scene, so its focus and speckle are not the desk's. For the desk itself use “Desk wave check” below.</>
              : <>Phase pattern of subframe 1 (of {r.hologram?.info.subframes ?? 4}). This is what the modulator shows; it is not meant to look like the object.</>}
          </p>
        </Section>

        <Section title="Sharpness vs eye focus depth">
          {sweep ? <LineChart xs={sweep.depths} ys={sweep.sharp} yMax={100} xLabel="eye focus height (mm)" yLabel="% of full 2D, same focus" marker={sweep.i} fmtX={(v) => Math.round(v)} />
            : <p className="text-[11px] text-silver">Calculate to see how sharp each height looks to the eye.</p>}
        </Section>

        <Section title="AETHER Desk · sharpness vs height" busy={busy.desk_check || busy.search_column_width}
          right={<button className="btn px-2 py-0.5 text-[11px]" onClick={() => st.tool("desk_check")}>Run</button>}>
          {r.desk ? <>
            <LineChart xs={r.desk.rows.map((x) => x.height_cm)} ys={r.desk.rows.map((x) => x.sharpness_vs_full_hologram_pct)} yMax={100} threshold={80}
              xLabel="height above panel (cm)" yLabel="% of full hologram" color="#4d7cff" fmtX={(v) => `${v}`} />
            <div className="flex justify-between font-mono text-[10.5px] text-silver"><span>columns {r.desk.column_width_um} µm</span><span>eye box {r.desk.eye_box_mm} mm</span></div>
          </> : <p className="text-[11px] text-silver">27″ desk, viewer at 70 cm. Eye-model simulation (4 mm pupil, 15 c/deg).</p>}
          <button className="btn w-full" onClick={() => st.tool("search_column_width", { height_cm: 10, min_sharpness_pct: 80 })}>Widest column for 80% at 10 cm</button>
          {r.search && <div className="font-mono text-[11px] text-silver">best <span className="text-cyan-glow">{r.search.largest_column_width_um ?? "—"} µm</span> · {r.search.tried?.length} steps</div>}
        </Section>

        <Section title="Window Law · eye through panel" busy={busy.window_check}
          right={<button className="btn px-2 py-0.5 text-[11px]" onClick={() => st.tool("window_check")}>Check</button>}>
          {r.window ? <>
            <div className="flex items-baseline justify-between"><span className="text-[11.5px] text-white/80">Visible</span><span className="readout text-[16px] text-cyan-glow">{r.window.visible_pct}%</span></div>
            <Bars rows={r.window.parts.slice(0, 6).map((x) => [x.part, x.visible_pct])} />
            {r.window.outside_sharp_zone && <p className="text-[10.5px] text-warn">Part of the design leaves the sharp zone ({r.window.sharp_zone_mm.map(Math.round).join("…")} mm from this eye).</p>}
          </> : <p className="text-[11px] text-silver">H1: the eye sees a point only if the eye→point line hits the panel.</p>}
          <button className="btn w-full" disabled={busy.hand_check} onClick={() => st.tool("hand_check")}><Icon name="hand" />Hand occlusion (v13)</button>
          {r.hand?.hand_points ? <p className="text-[11px] text-white/80">conflicts <span className="readout">{r.hand.depth_conflict_pct}%</span> · natural <span className="readout">{r.hand.naturally_hidden_pct}%</span></p>
            : r.hand && <p className="text-[10.5px] text-silver">Switch to hand tracking so the camera can see your hand.</p>}
        </Section>

        <Section title="Speckle reduction (v11)" busy={busy.speckle_compare}
          right={<div className="flex gap-0.5">{[2, 3, 4].map((v) => <button key={v} onClick={() => setK(v)} className={`rounded px-1.5 font-mono text-[10px] ${k === v ? "bg-white/10 text-white" : "text-silver"}`}>{v}×{v}</button>)}</div>}>
          {r.speckle?.one_frame !== undefined ? <>
            <Bars rows={[["1 frame", r.speckle.one_frame, 1.1, "#ff4fd8"], [`${r.speckle.frames} random`, r.speckle.random_avg, 1.1, "#4d7cff"], [`${r.speckle.k}×${r.speckle.k} groups`, r.speckle.sparse_groups, 1.1, "#5fe1ff"]]} />
            <p className="text-[10.5px] text-silver">Contrast C = σ/μ. Visible above ≈0.04, so speckle is still an open problem.</p>
          </> : <p className="text-[11px] text-silver">Compares one frame, random-phase averaging and sparse point groups.</p>}
          <button className="btn w-full" onClick={() => st.tool("speckle_compare", { k })}>Compare speckle</button>
        </Section>

        <Section title="Optics settings" right={<button className="text-silver hover:text-white" onClick={() => setOpt(!opt)}><Icon name="chevron" className={`h-3.5 w-3.5 transition ${opt ? "rotate-90" : ""}`} /></button>}>
          {opt && <div className="grid grid-cols-3 gap-1.5">
            <Stat k="pixel" v={`${d.pitch_um} µm`} /><Stat k="grid" v={`${d.samples}²`} /><Stat k="method" v={s.method} />
            <Stat k="points" v={r.hologram ? r.hologram.info.points_used : s.points} /><Stat k="lab scale" v={r.hologram ? `×${r.hologram.info.lab_scale}` : "—"} />
            <Stat k="backend" v={r.hologram?.info.compute || compute} hot={compute === "modal"} />
          </div>}
          {opt && <div className="grid grid-cols-2 gap-2">
            {[["pitch_um", "pixel µm", 0.1], ["wavelength_nm", "λ nm", 1], ["samples", "pixels/side", 16], ["distance_mm", "distance mm", 1]].map(([kk, l, step]) => (
              <label key={kk} className="space-y-1"><div className="font-mono text-[9.5px] text-silver">{l}</div>
                <Num value={d[kk]} step={step} onCommit={(n) => st.tool("set_display", { [kk]: n })} /></label>
            ))}
            <label className="space-y-1"><div className="font-mono text-[9.5px] text-silver">surface points</div>
              <Num value={s.points} step={50} onCommit={(n) => st.tool("set_display", { points: Math.round(n) })} /></label>
            <label className="space-y-1"><div className="font-mono text-[9.5px] text-silver">method</div>
              <select className="field" value={s.method} onChange={(e) => st.tool("set_display", { method: e.target.value })}>
                <option value="wrp">WRP</option><option value="points">direct points</option><option value="layers">layers</option>
              </select></label>
          </div>}
        </Section>
      </div>
    </FloatPanel>
  );
}
