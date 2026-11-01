import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useStore } from "../store";
import FloatPanel, { IconTile } from "./FloatPanel";
import { L, useLayout } from "./layout";
import Icon from "./Icon";
import { SineLoader } from "./Charts";

const NAMES = {
  build_assembly: "Build assembly", add_part: "Add part", update_part: "Edit part", delete_part: "Delete part",
  list_parts: "Read scene", set_display: "Set optics", set_eye: "Move eye", set_view: "Inspect view", make_hologram: "Calculate hologram",
  propagate: "Propagate light", focus_sweep: "Focus sweep", eye_view: "Eye view", window_check: "Window Law",
  hand_check: "Hand check", desk_check: "Desk sharpness", search_column_width: "Design search",
  speckle_compare: "Speckle", export_film: "Film export", desk_score: "Desk score", optimize_for_desk: "AI design loop",
  sam_3_1: "SAM 3.1 cut-out", turn_gear: "Turn gear", desk_wave_view: "Desk wave check", import_three_view: "Three-view → 3D", read_views: "Three-view drawing → 3D", classify_upload: "What the image is",
};
const KIND_NAME = { machine: "machine drawing (one view)", three_view: "three-view sheet", part: "photo of one part" };
function summary(t) {
  const r = t.result;
  if (r.error) return r.error.slice(0, 60);
  switch (t.tool) {
    case "build_assembly": return `${r.parts?.length} parts · ${r.size_mm?.map((v) => Math.round(v)).join("×")} mm`;
    case "make_hologram": return `${r.points_used} pts → ${r.hologram_px}² px`;
    case "focus_sweep": return `${r.depths_mm?.length} depths`;
    case "desk_check": return r.rows?.map((x) => `${x.height_cm}cm ${x.sharpness_vs_full_hologram_pct}%`).join(" · ");
    case "window_check": return `${r.visible_pct}% visible`;
    case "set_view": return [r.view?.section && `cut ${r.view.section}`, r.view?.explode && `explode ${r.view.explode}`, r.view?.xray && "x-ray"].filter(Boolean).join(" · ");
    case "search_column_width": return r.largest_column_width_um ? `best ${r.largest_column_width_um} µm` : r.result;
    case "speckle_compare": return `C ${r.one_frame} → ${r.sparse_groups}`;
    case "desk_score": return `${r.parts_ok}/${r.parts} parts ok · min ${r.min_sharpness_pct}%`;
    case "optimize_for_desk": return `${r.before?.min_sharpness_pct}% → ${r.after?.min_sharpness_pct}% · ${r.rounds?.length} rounds`;
    case "turn_gear": return r.turned?.map((x) => `${x.part} ${x.turned_deg}°`).join(" · ");
    case "classify_upload": return `${KIND_NAME[r.kind] || r.kind} · ${r.by}${r.fallback ? " · " + r.fallback : ""}`;
    case "read_views": return `${r.check?.views_found} views · side ${r.check?.view_match_iou_pct?.side}% · top ${r.check?.view_match_iou_pct?.top}% · front ${r.check?.view_match_iou_pct?.front}% match`;
    case "sam_3_1": return r.mode === "interpret" ? `${r.parts?.length} parts read · clean standard parts · ${r.scale_source?.startsWith("read") ? "scale read" : "scale assumed"}` : r.mode === "blueprint" ? `${r.parts?.length} parts traced · ${r.scale_source?.startsWith("read") ? "scale read" : "scale assumed"}` : `${r.width_mm}×${r.height_mm} mm${r.lobes_around_centre ? ` · ${r.lobes_around_centre} lobes` : ""}${r.centre_hole ? " · hole" : ""}`;
    default: return "";
  }
}

const EXAMPLES = [
  ["Tesla-style motor", "Generate a Tesla-style motor and place it 10 cm above the screen"],
  ["Cut and explode it", "Cut it in half and explode it so I can see the stator and rotor"],
  ["Is it sharp on the desk?", "Can AETHER Desk show this sharply? Check the Window Law too"],
  ["How grainy?", "How grainy will it look, and do sparse point groups help?"],
];

const STEP_LABEL = { build_assembly: "Building the model", focus_sweep: "Eye focus sweep (GPU)", eye_view: "Eye view (GPU)",
  make_hologram: "Lab phase hologram (GPU)", desk_check: "Desk sharpness check", window_check: "Window Law check", set_view: "Changing the view",
  sam_3_1: "SAM 3.1 cutting out the parts", classify_upload: "Measuring what the image is (drawing or photo, one view or three)", read_drawing: "Muse Spark reads the whole sheet and 4 close-ups at 2x", measure_circles: "Measuring every circle on the drawing (centres, radii, pivots)", complete_views: "Muse Spark completes the unseen views like a senior engineer (depths, planes, hidden shafts and bearings)", read_views: "Finding the side, front and top views and carving the 3D shape", layers: "Muse Spark stacks the parts in depth", rebuild_3d: "Rebuilding each part as a 3D solid (gears mesh, pins, plates)", desk_wave_view: "True-scale desk wave simulation", desk_score: "Physics scores the design (GPU)", update_part: "Muse Spark changes the design",
  optimize_for_desk: "AI design loop" };

// Muse Voice Transcribe takes 16 kHz mono WAV: decode the browser recording and re-encode it.
async function toWav(blob, rate = 16000) {
  const buf = await new AudioContext().decodeAudioData(await blob.arrayBuffer());
  const off = new OfflineAudioContext(1, Math.ceil(buf.duration * rate), rate);
  const src = off.createBufferSource(); src.buffer = buf; src.connect(off.destination); src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const v = new DataView(new ArrayBuffer(44 + pcm.length * 2));
  const str = (o, t) => [...t].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); str(8, "WAVEfmt "); v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, "data"); v.setUint32(40, pcm.length * 2, true);
  pcm.forEach((x, i) => v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, x)) * 0x7fff, true));
  return new Blob([v], { type: "audio/wav" });
}

// What the upload is decides the path. Auto: the server measures the image (line drawing or photo, one view or three).
const KINDS = [
  ["auto", "Auto", "The server measures the image: a line drawing with one view = machine, three matching views = three-view sheet, a photo = one part", 240],
  ["machine", "Machine drawing", "One view of a machine: Muse Spark reads every part like an engineer and completes the unseen views → 3D assembly", 240],
  ["three_view", "Three-view sheet", "Side, top and front views of one object (e.g. a car) → a solid built from named parts that matches every view", 180],
  ["part", "Part photo", "A phone photo of one part: SAM 3.1 cuts it out, AETHER measures it, Muse Spark rebuilds it", 80],
];

function PhotoForm({ image, onCancel }) {
  const askPhoto = useStore((s) => s.askPhoto);
  const [kind, setKind] = useState("auto");
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState(240);
  const [mode, setMode] = useState("interpret");
  const pick = (k) => { setKind(k); setSize(KINDS.find((x) => x[0] === k)[3]); };
  const machine = kind === "machine" || kind === "auto";
  return (
    <form onSubmit={(e) => { e.preventDefault(); onCancel(); askPhoto(image, prompt.trim(), Number(size) || 240, mode, kind); }}
      className="space-y-2 overflow-hidden rounded-xl border border-slate-400/[0.16] bg-gradient-to-br from-sky-400/[0.06] to-violet-500/[0.07] p-2">
      <div className="flex min-w-0 flex-wrap gap-1" role="radiogroup" aria-label="What is this image?">
        {KINDS.map(([k, label, tip]) => (
          <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => pick(k)} title={tip}
            className={`btn whitespace-nowrap !py-1 text-[11px] ${kind === k ? "!border-cyan-glow/50 text-cyan-glow" : ""}`}>{label}</button>))}
      </div>
      <div className="flex min-w-0 gap-2">
        <img src={image} className="h-[60px] w-[60px] shrink-0 rounded-lg border border-white/10 bg-white object-contain" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={kind === "part" ? "what it is, e.g. gear" : "optional: what it is, e.g. printing press"}
            title="Optional hint for Muse Spark (what the object is). It does not choose the path; the buttons above do."
            className="field w-full !py-1 text-[11.5px]" />
          <label className="flex min-w-0 items-center gap-1.5 font-mono text-[10px] text-slate-400">
            <input type="number" value={size} onChange={(e) => setSize(e.target.value)} className="field w-16 !py-1 text-[11px]"
              title={kind === "part" ? "ASSUMED longest side of the part (a photo has no scale)" : "ASSUMED real size of the drawing's longest side - used only if no dimension can be read on the drawing"} />
            <span className="truncate">mm (assumed)</span></label>
        </div>
      </div>
      <div className="flex min-w-0 flex-wrap gap-1.5">
          {machine && <button type="button" onClick={() => setMode(mode === "interpret" ? "trace" : "interpret")}
            title={mode === "interpret" ? "Interpret: Muse Spark reads each part's type, size and axis and draws a clean standard part (best for dense or sketchy drawings)" : "Trace: SAM 3.1 traces each part's exact outline (best for clean drawings with real outlines)"}
            className="btn whitespace-nowrap !py-1 text-[11px]">{mode === "interpret" ? "Interpret" : "Trace"}</button>}
          <button type="button" onClick={onCancel} className="btn ml-auto whitespace-nowrap !py-1 text-[11px]">Cancel</button>
      </div>
      <button className="btn-accent w-full whitespace-nowrap !py-1.5 text-[11.5px]" title={KINDS.find((x) => x[0] === kind)[2]}>
        {kind === "machine" ? "Build machine" : kind === "three_view" ? "Build from three views" : kind === "part" ? "Build part" : "Build 3D model"}</button>
    </form>
  );
}

// What Muse Spark is doing right now: one line per model call or tool, live from the server.
function LiveSteps() {
  const steps = useStore((s) => s.progress);
  const skew = useStore((s) => s.progressSkew || 0);
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((n) => n + 1), 250); return () => clearInterval(t); }, []);
  const list = steps.length ? steps : [{ label: "Muse Spark", state: "run" }];
  const secs = (st) => st.s != null ? st.s : st.t0 ? Math.max(0, Date.now() / 1000 - skew - st.t0) : null;
  const total = steps.length && steps[0].t0 ? Math.max(0, Date.now() / 1000 - skew - steps[0].t0) : null;
  return (
    <div className="space-y-1 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2">
      {total != null && <div className="flex font-mono text-[10px] text-slate-400"><span>steps</span><span className="ml-auto tabular-nums">{total.toFixed(0)} s total</span></div>}
      {list.map((st, i) => (
        <div key={i} className="flex items-center gap-2 font-mono text-[10.5px]" title={st.detail || undefined}>
          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${st.state === "run" ? "animate-pulse bg-cyan-glow shadow-glow" : st.state === "error" ? "bg-bad" : "bg-ok"}`} />
          <span className={`min-w-0 truncate ${st.state === "run" ? "text-white" : "text-silver"}`}>{st.label === "Muse Spark" ? "Muse Spark is thinking" : STEP_LABEL[st.label] || st.label.replace(/_/g, " ")}</span>
          {st.detail && <span className="min-w-0 truncate text-rose-300">{st.detail}</span>}
          {st.state === "run" && <SineLoader label="" className="ml-auto scale-75" />}
          {secs(st) != null && <span className={`${st.state === "run" ? "" : "ml-auto"} shrink-0 tabular-nums text-slate-400`}>{secs(st).toFixed(st.state === "run" ? 0 : 1)} s</span>}
        </div>
      ))}
    </div>
  );
}

export default function Orchestrator() {
  const chat = useStore((s) => s.chat);
  const busy = useStore((s) => s.busy.chat);
  const open = useStore((s) => s.panels.orchestrator);
  const ask = useStore((s) => s.ask);
  const notify = useStore((s) => s.notify);
  const [text, setText] = useState("");
  const [rec, setRec] = useState(null);
  const [photo, setPhoto] = useState(null);
  const file = useRef();
  const pickPhoto = (f) => { if (!f) return; const r = new FileReader(); r.onload = () => setPhoto(r.result); r.readAsDataURL(f); };
  const log = useRef();
  const input = useRef();

  useEffect(() => { log.current && (log.current.scrollTop = 1e9); }, [chat, busy]);
  useEffect(() => {
    const f = (e) => { if (e.key === "/" && e.ctrlKey) { e.preventDefault(); input.current?.focus(); } };
    addEventListener("keydown", f); return () => removeEventListener("keydown", f);
  }, []);

  const send = (q) => { const t = (q ?? text).trim(); if (!t || busy) return; setText(""); ask(t); };

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(stream), chunks = [];
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        try {
          const blob = await toWav(new Blob(chunks, { type: r.mimeType || "audio/webm" }));
          const res = await fetch("/api/transcribe", { method: "POST", headers: { "Content-Type": "audio/wav" }, body: blob });
          const j = await res.json();
          if (!res.ok) throw new Error(j.error);
          send(j.text);
        } catch (e) { notify("Voice: " + e.message, "error"); }
        setRec(null);
      };
      r.start(); setRec(r);
    } catch (e) { notify("Microphone: " + e.message, "error"); }
  }
  const stopRec = () => rec?.state === "recording" && rec.stop();

  const lay = useLayout();
  const minimised = open && lay.win.orchestrator === "min";
  const mode = useStore((s) => s.mode), setMode = useStore((s) => s.setMode);
  const modeSwitch = (
    <div className="mr-1 flex rounded-lg border border-white/10 bg-black/30 p-0.5">
      {[["laptop", "laptop", "Laptop mode (mouse and keyboard)"], ["hand", "hand", "Hand tracking (camera)"]].map(([m, ic, t]) => (
        <button key={m} title={t} onClick={() => setMode(m)}
          className={`flex h-6 items-center gap-1.5 rounded-md px-2 text-[11px] font-medium transition ${mode === m ? "tab-on" : "text-slate-400 hover:text-white"}`}>
          <Icon name={ic} className="h-3.5 w-3.5" /><span className="hidden xl:inline">{m === "laptop" ? "Laptop" : "Hand"}</span></button>))}
    </div>
  );
  // the top edge drags: up = taller chat, down = shorter; remembered in this browser
  const [h, setH] = useState(() => { try { return +localStorage.getItem("aether.orch.h") || null; } catch { return null; } });
  // while dragging, the height is written straight to the panel (no React render per mouse move, so it follows
  // the pointer exactly); React gets the final height on release
  const resizeTop = {
    start: (e) => {
      e.preventDefault();
      const grip = e.currentTarget, sec = grip.closest("section"), y0 = e.clientY, h0 = sec.getBoundingClientRect().height;
      const maxH = innerHeight - L.top - L.bottom - 8;
      let v = h0;
      if (!h) setH(Math.round(h0));               // once, so the chat log switches to fill the panel
      grip.setPointerCapture(e.pointerId);
      document.body.style.cursor = "ns-resize";
      const mv = (ev) => { v = Math.round(Math.min(maxH, Math.max(150, h0 + (y0 - ev.clientY)))); sec.style.height = v + "px"; };
      const up = () => {
        grip.removeEventListener("pointermove", mv); grip.removeEventListener("pointerup", up); grip.removeEventListener("pointercancel", up);
        document.body.style.cursor = "";
        setH(v); try { localStorage.setItem("aether.orch.h", v); } catch { /* private mode */ }
      };
      grip.addEventListener("pointermove", mv); grip.addEventListener("pointerup", up); grip.addEventListener("pointercancel", up);
    },
    reset: () => { setH(null); try { localStorage.removeItem("aether.orch.h"); } catch { /* private mode */ } },
  };
  const place = { left: lay.midLeft, right: lay.midRight, bottom: L.bottom, ...(h ? { height: Math.min(h, innerHeight - L.top - L.bottom - 8) } : {}) };

  if (minimised) return (
    <div className="pointer-events-none absolute z-20 flex items-end justify-center" style={{ left: place.left, right: place.right, bottom: L.bottom }}>
      <motion.button initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} onClick={() => useStore.getState().setWin("orchestrator", "normal")}
        className="glass pointer-events-auto flex h-11 items-center gap-2.5 rounded-xl pl-2 pr-4 text-[12.5px] font-semibold text-white" title="Open the AI orchestrator (Ctrl+/)">
        <IconTile icon="sparkle" big />Ask Muse Spark{busy && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-glow shadow-glow" />}
      </motion.button>
    </div>);

  return (
    <FloatPanel id="orchestrator" title="Muse Spark · AI orchestrator" icon="sparkle" open={open} busy={busy} right={modeSwitch} resizeTop={resizeTop}
      onClose={() => useStore.getState().setPanel("orchestrator", false)}
      style={place} className="mx-auto max-w-[760px]">
      <div className="flex min-h-0 flex-1 flex-col gap-2 px-3.5 pb-3">
        {(chat.length > 0 || busy || h) && (
          <div ref={log} className="scroll-thin min-h-0 flex-1 space-y-2 overflow-y-auto py-1.5 pr-1 [mask-image:linear-gradient(transparent,#000_12px,#000_calc(100%-12px),transparent)]"
            style={lay.win.orchestrator === "max" || h ? undefined : { maxHeight: "min(32vh, 300px)" }}>
            {chat.map((m, i) => m.role === "steps" ? (
              <div key={i} className="space-y-1">{m.trace.map((t, j) => (
                <div key={j} className="flex min-w-0 items-center gap-2 rounded-lg border border-white/[0.06] bg-black/25 px-2 py-1 text-[11px]">
                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${t.result.error ? "bg-bad" : "bg-cyan-glow shadow-glow"}`} />
                  <span className="shrink-0 whitespace-nowrap text-white/85">{NAMES[t.tool] || t.tool}</span>
                  <span className={`ml-auto min-w-0 truncate font-mono text-[10px] ${t.result.error ? "text-rose-300" : "text-cyan-glow/80"}`} title={summary(t)}>{summary(t)}</span>
                </div>))}</div>
            ) : (
              <div key={i} className={`whitespace-pre-wrap break-words rounded-xl px-3 py-2 text-[12px] leading-relaxed ${
                m.role === "user" ? "ml-auto w-fit max-w-[85%] border border-cyan-glow/20 bg-gradient-to-r from-sky-400/[0.10] to-violet-500/[0.10]"
                  : m.role === "error" ? "border border-bad/30 bg-bad/10 text-rose-200" : "mr-6 border border-white/[0.07] bg-white/[0.04] text-white/90"}`}>
                {m.img && <img src={m.img} className="mb-1.5 h-20 max-w-full rounded-lg object-cover" />}{m.text}</div>
            ))}
            {busy && <LiveSteps />}
          </div>
        )}
        {!chat.length && !busy && (
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLES.map(([short, q]) => (
              <button key={q} onClick={() => send(q)} title={q}
                className="max-w-full truncate rounded-lg border border-slate-400/[0.16] bg-white/[0.025] px-2.5 py-1 text-[11.5px] text-slate-300 transition hover:border-cyan-glow/35 hover:bg-white/[0.05] hover:text-white">{short}</button>))}
          </div>
        )}
        {photo && <PhotoForm image={photo} onCancel={() => setPhoto(null)} />}
        <form onSubmit={(e) => { e.preventDefault(); send(); }}
          className={`relative flex shrink-0 items-center gap-1.5 overflow-hidden rounded-xl border bg-black/35 p-1 transition ${busy ? "border-cyan-glow/40" : "border-white/10 focus-within:border-cyan-glow/50 focus-within:shadow-[0_0_24px_rgba(95,225,255,.18)]"}`}>
          <button type="button" title="Hold to talk (Muse Voice)" onPointerDown={startRec} onPointerUp={stopRec} onPointerLeave={stopRec}
            className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg transition ${rec ? "animate-pulse bg-magenta-glow/25 text-magenta-glow" : "text-silver hover:bg-white/10 hover:text-white"}`}>
            <Icon name="mic" /></button>
          <button type="button" title="Photo or drawing → 3D model" disabled={busy} onClick={() => file.current?.click()}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-silver transition hover:bg-white/10 hover:text-white disabled:opacity-40">
            <Icon name="camera" /></button>
          <input ref={file} id="photo-input" type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => { pickPhoto(e.target.files?.[0]); e.target.value = ""; }} />
          <input id="ai-input" ref={input} value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && e.target.blur()}
            placeholder={rec ? "Listening… release to send" : "Ask Muse Spark to design, change or check something…"}
            className="min-w-0 flex-1 truncate bg-transparent px-1 py-1.5 text-[12.5px] text-white outline-none placeholder:text-white/35" />
          <button className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-sky-400 via-indigo-500 to-violet-500 text-white shadow-[0_6px_18px_-6px_rgba(99,102,241,.9)] transition hover:brightness-110 disabled:bg-none disabled:bg-white/10 disabled:text-white/30 disabled:shadow-none"
            disabled={busy || !text.trim()}><Icon name="send" /></button>
          {busy && <div className="pointer-events-none absolute inset-0 busy-sheen" />}
        </form>
      </div>
    </FloatPanel>
  );
}
