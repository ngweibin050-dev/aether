import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useStore } from "../store";
import FloatPanel, { IconTile } from "./FloatPanel";
import { L, useLayout } from "./layout";
import Icon from "./Icon";
import { SineLoader } from "./Charts";
import Markdown from "./Markdown";

const NAMES = {
  build_assembly: "Build assembly", add_part: "Add part", update_part: "Edit part", delete_part: "Delete part",
  list_parts: "Read scene", set_display: "Set optics", set_eye: "Move eye", set_view: "Inspect view", make_hologram: "Calculate hologram",
  propagate: "Propagate light", focus_sweep: "Focus sweep", eye_view: "Eye view", window_check: "Window Law",
  hand_check: "Hand check", desk_check: "Desk sharpness", search_column_width: "Design search",
  speckle_compare: "Speckle", export_film: "Film export", desk_score: "Desk score", optimize_for_desk: "AI design loop",
  sam_3_1: "SAM 3.1 cut-out", turn_gear: "Turn gear", desk_wave_view: "Desk wave check", classify_upload: "What the image is",
  calculate: "Calculate", web_search: "Web search", inspect: "Inspect model", explain_machine: "Explain the machine",
  create_model: "Create model", add_parts: "Add parts", modify: "Change", remove: "Remove", export_model: "Export file",
  make_drawing: "Technical drawing", build_from_drawing: "Build from drawing", import_file: "Import file", undo: "Undo",
  ask_user: "Question", open_panel: "Open panel",
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
    case "calculate": return `${r.expression} = ${r.result}`;
    case "web_search": return `${r.sources?.length || 0} source(s)`;
    case "modify": return (r.changed || []).join(" · ");
    case "remove": return (r.removed || []).join(", ");
    case "add_parts": return `${r.added?.length} part(s) → ${r.model}`;
    case "export_model": return r.file;
    case "make_drawing": return `${r.solids} solids · 3 views`;
    case "undo": return r.undone ? "done" : r.why;
    case "classify_upload": return `${KIND_NAME[r.kind] || r.kind} · ${r.by}${r.fallback ? " · " + r.fallback : ""}`;
    case "read_views": return `${r.check?.views_found} views · side ${r.check?.view_match_iou_pct?.side}% · top ${r.check?.view_match_iou_pct?.top}% · front ${r.check?.view_match_iou_pct?.front}% match`;
    case "sam_3_1": return r.mode === "interpret" ? `${r.parts?.length} parts read · clean standard parts · ${r.scale_source?.startsWith("read") ? "scale read" : "scale assumed"}` : r.mode === "blueprint" ? `${r.parts?.length} parts traced · ${r.scale_source?.startsWith("read") ? "scale read" : "scale assumed"}` : `${r.width_mm}×${r.height_mm} mm${r.lobes_around_centre ? ` · ${r.lobes_around_centre} lobes` : ""}${r.centre_hole ? " · hole" : ""}`;
    default: return "";
  }
}

const EXAMPLES = [
  ["Explain this machine", "Explain this machine step by step"],
  ["Make it more detailed", "Make the selected model more detailed"],
  ["Technical drawing", "Make a technical drawing of the model on the desk"],
  ["Export GLB", "Export the model on the desk to GLB and send it here"],
  ["Sharp on the desk?", "Can the AETHER Desk show this sharply? Check the Window Law too"],
];

// Every step says WHO did it (a Meta model, or AETHER's own engine on the Modal GPU / this computer) and WHAT.
const GPU = "gpu";
export const STEP = {
  "Muse Spark": ["Muse Spark", "thinking"], update_part: ["Muse Spark", "changes the design"],
  read_drawing: ["Muse Spark", "read drawing (sheet + 4 close-ups, twice)"], complete_views: ["Muse Wonder", "complete the unseen views"],
  layers: ["Muse Spark", "stack the parts in depth"], "explain · Muse Spark": ["Muse Spark", "explanation"],
  "illustration · Muse Image": ["Muse Image", "illustration"], sam_3_1: ["SAM 3.1", "outline"],
  voice: ["Muse Voice Transcribe", "speech to text"],
  read_views: [GPU, "find the views and carve the 3D shape (Muse Spark names the regions)"],
  classify_upload: ["AETHER engine", "what the image is (drawing, photo, three views)"],
  measure_circles: ["AETHER engine", "measure every circle on the ink"], rebuild_3d: ["AETHER engine", "rebuild each part in 3D"],
  build_assembly: ["AETHER engine", "build the model"], set_view: ["AETHER engine", "change the view"],
  window_check: ["AETHER engine", "Window Law check"], desk_score: [GPU, "desk sharpness score"],
  focus_sweep: [GPU, "eye focus sweep"], eye_view: [GPU, "eye view"], make_hologram: [GPU, "lab phase hologram"],
  desk_check: [GPU, "desk sharpness check"], desk_wave_view: [GPU, "true-scale desk wave simulation"],
  optimize_for_desk: ["Muse Spark + " + GPU, "design loop"],
};

export function StepRow({ st, now }) {
  const compute = useStore((s) => s.compute);
  const gpu = compute === "modal" ? "Modal T4 GPU" : "local engine";
  const [who0, what] = STEP[st.label] || ["AETHER engine", st.label.replace(/_/g, " ")];
  const who = st.who || who0;                    // the server names the model that actually answered
  const secs = st.s != null ? st.s : st.t0 && now ? Math.max(0, now - st.t0) : null;
  return (
    <div className="flex items-center gap-2 font-mono text-[10.5px]" title={st.detail || undefined}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${st.state === "run" ? "animate-pulse bg-cyan-glow shadow-glow" : st.state === "error" ? "bg-bad" : "bg-ok"}`} />
      <span className={`min-w-0 truncate ${st.state === "run" ? "text-white" : "text-silver"}`}>
        <span className="text-cyan-glow">{who.replace(GPU, gpu)}</span> · {what}</span>
      {st.detail && <span className="min-w-0 truncate text-rose-300">{st.detail}</span>}
      {st.state === "run" && <SineLoader label="" className="ml-auto scale-75" />}
      {secs != null && <span className={`${st.state === "run" ? "" : "ml-auto"} shrink-0 tabular-nums text-slate-400`}>{secs.toFixed(st.state === "run" ? 0 : 1)} s</span>}
    </div>
  );
}

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
        {kind === "machine" ? "Build machine" : kind === "three_view" ? "Build CAD from three views" : kind === "part" ? "Build part" : "Build 3D model"}</button>
    </form>
  );
}

// errors in words a user can act on (the technical text stays on hover)
function friendlyError(t = "") {
  if (/Failed to fetch|NetworkError|ECONNREFUSED/i.test(t)) return "The AETHER server is not reachable. Is python server.py still running?";
  if (/timed? ?out|timeout/i.test(t)) return "Muse Spark took too long to answer. Try again, or ask for something smaller.";
  if (/META_API/i.test(t)) return "No Meta API key: put META_API=... in the .env file and restart the server.";
  if (/HTTP 4(29|03)|rate/i.test(t)) return "The Meta API is busy or refused the request (rate limit). Wait a moment and try again.";
  return "Something went wrong on the server: " + t.replace(/^[A-Za-z]+Error: /, "").slice(0, 160);
}

const FILE_ICON = { image: "camera", pdf: "film", mesh: "cube", cad: "holo", other: "upload" };

function Chip({ f, onRemove }) {
  return (
    <span className="flex max-w-[220px] items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.05] px-2 py-1 text-[11px] text-slate-200">
      <Icon name={FILE_ICON[f.kind] || "upload"} className="h-3.5 w-3.5 shrink-0 text-cyan-glow" />
      <span className="truncate">{f.name}</span>
      {f.page_count ? <span className="shrink-0 font-mono text-[9.5px] text-slate-500">{f.page_count} p</span> : null}
      {f.uploading && <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-cyan-glow" />}
      {onRemove && <button type="button" onClick={onRemove} className="shrink-0 text-slate-500 hover:text-white" title="Remove">×</button>}
    </span>
  );
}

// What the assistant did, as the scene itself reports it, plus its files, sources and question
function Extras({ x, onOption }) {
  if (!x) return null;
  return (
    <div className="mt-2 space-y-2">
      {x.changes?.length > 0 && (
        <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/[0.05] px-2.5 py-1.5">
          <div className="mb-0.5 font-mono text-[9.5px] uppercase tracking-wide text-emerald-300/90">What changed</div>
          {x.changes.map((c, i) => <div key={i} className="text-[11.5px] text-slate-200">• {c}</div>)}
          <button type="button" onClick={() => onOption("undo")} className="mt-1 font-mono text-[10px] text-slate-400 hover:text-white">↶ undo this</button>
        </div>)}
      {x.downloads?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {x.downloads.map((d) => (
            <a key={d.url} href={d.url} download={d.name}
              className="flex items-center gap-2 rounded-lg border border-cyan-glow/30 bg-cyan-glow/[0.07] px-2.5 py-1.5 text-[11.5px] text-white hover:bg-cyan-glow/15">
              <Icon name="upload" className="h-3.5 w-3.5 rotate-180 text-cyan-glow" />
              <span><span className="block font-semibold">{d.label}</span><span className="font-mono text-[9.5px] text-slate-400">{d.name} · {(d.bytes / 1024).toFixed(0)} KB</span></span>
            </a>))}
        </div>)}
      {x.question?.options?.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {x.question.options.map((o) => (
            <button key={o} type="button" onClick={() => onOption(o)}
              className="rounded-lg border border-violet-300/30 bg-violet-400/10 px-2.5 py-1 text-[11.5px] text-violet-100 hover:bg-violet-400/20">{o}</button>))}
        </div>)}
      {x.sources?.length > 0 && (
        <div className="space-y-0.5">
          <div className="font-mono text-[9.5px] uppercase tracking-wide text-slate-500">Sources</div>
          {x.sources.map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer" className="block truncate text-[11px] text-sky-300 hover:underline">{i + 1}. {s.title}</a>)}
        </div>)}
      {x.notes?.map((n, i) => <div key={i} className="text-[10.5px] text-amber-200/90">{n}</div>)}
    </div>
  );
}

// What Muse Spark is doing right now: one line per model call or tool, live from the server.
function LiveSteps() {
  const steps = useStore((s) => s.progress);
  const skew = useStore((s) => s.progressSkew || 0);
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((n) => n + 1), 250); return () => clearInterval(t); }, []);
  const list = steps.length ? steps : [{ label: "Muse Spark", state: "run" }];
  const now = Date.now() / 1000 - skew;
  const total = steps.length && steps[0].t0 ? Math.max(0, now - steps[0].t0) : null;
  return (
    <div className="space-y-1 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2">
      {total != null && <div className="flex font-mono text-[10px] text-slate-400"><span>steps</span><span className="ml-auto tabular-nums">{total.toFixed(0)} s total</span></div>}
      {list.map((st, i) => <StepRow key={i} st={st} now={now} />)}
    </div>
  );
}

// The finished turn's steps stay in the chat, folded to one line (who did what, in how many seconds on click).
function Timeline({ steps }) {
  const [open, setOpen] = useState(false);
  const total = steps.reduce((a, st) => a + (st.s || 0), 0);
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/10 px-3 py-1.5">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 font-mono text-[10px] text-slate-400 hover:text-white">
        <Icon name="chevron" className={`h-3 w-3 transition ${open ? "rotate-90" : ""}`} />
        <span>{steps.length} step{steps.length === 1 ? "" : "s"} · {[...new Set(steps.map((s) => (STEP[s.label] || [s.who || "AETHER engine"])[0]))].slice(0, 3).join(", ")}</span>
        <span className="ml-auto tabular-nums">{total.toFixed(1)} s</span></button>
      {open && <div className="mt-1 space-y-1">{steps.map((st, i) => <StepRow key={i} st={st} />)}</div>}
    </div>
  );
}

function ToolSteps({ trace }) {
  const [open, setOpen] = useState(false);
  const bad = trace.filter((t) => t.result?.error).length;
  return (
    <div className="rounded-lg border border-white/[0.06] bg-black/25 px-2 py-1 text-[11px]">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full min-w-0 items-center gap-2 text-left text-white/80 hover:text-white">
        <Icon name="chevron" className={`h-3 w-3 shrink-0 transition ${open ? "rotate-90" : ""}`} />
        <span className="truncate">{[...new Set(trace.map((t) => NAMES[t.tool] || t.tool))].join(" · ")}</span>
        {bad > 0 && <span className="ml-auto shrink-0 font-mono text-[10px] text-amber-300" title="Tool calls that failed and were retried">{bad} retried</span>}
      </button>
      {open && <div className="mt-1 space-y-1">{trace.map((t, j) => (
        <div key={j} className="flex min-w-0 items-center gap-2 pl-5">
          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${t.result?.error ? "bg-bad" : "bg-cyan-glow shadow-glow"}`} />
          <span className="shrink-0 whitespace-nowrap text-white/85">{NAMES[t.tool] || t.tool}</span>
          <span className={`ml-auto min-w-0 truncate font-mono text-[10px] ${t.result?.error ? "text-rose-300" : "text-cyan-glow/80"}`} title={summary(t)}>{summary(t)}</span>
        </div>))}</div>}
    </div>
  );
}

function MsgActions({ text, onRetry }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-1.5 flex gap-3 font-mono text-[10px] text-slate-500 opacity-0 transition group-hover:opacity-100">
      <button type="button" className="hover:text-white" onClick={() => { navigator.clipboard?.writeText(text || ""); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
        {copied ? "copied" : "copy"}</button>
      {onRetry && <button type="button" className="hover:text-white" onClick={onRetry} title="Send the previous message again">retry</button>}
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
  const [files, setFiles] = useState([]);           // attachments of the message being written (uploaded at once)
  const [drag, setDrag] = useState(false);
  const file = useRef();
  const attach = async (list) => {
    for (const f of [...(list || [])]) {
      const tmp = { name: f.name, kind: "other", uploading: true, key: Math.random() };
      setFiles((x) => [...x, tmp]);
      try {
        const meta = await useStore.getState().upload(f);
        setFiles((x) => x.map((y) => (y.key === tmp.key ? meta : y)));
      } catch (e) { setFiles((x) => x.filter((y) => y.key !== tmp.key)); notify(`${f.name}: ${e.message}`, "error"); }
    }
  };
  const log = useRef();
  const input = useRef();

  useEffect(() => { log.current && (log.current.scrollTop = 1e9); }, [chat, busy]);
  useEffect(() => {
    const f = (e) => { if (e.key === "/" && e.ctrlKey) { e.preventDefault(); input.current?.focus(); } };
    addEventListener("keydown", f); return () => removeEventListener("keydown", f);
  }, []);

  const send = (q) => {
    const t = (q ?? text).trim();
    const ready = files.filter((f) => !f.uploading);
    if ((!t && !ready.length) || busy || files.some((f) => f.uploading)) return;
    setText(""); setFiles([]);
    ask(t || "Here is a file.", ready);
  };
  // voice: the transcript goes to Muse Spark, tagged with the model and its seconds; "Explain this machine" (or
  // "explain the machine / this / it") starts the step-by-step explanation directly
  const fromVoice = (t0, sec) => {
    const t = (t0 || "").replace(/[。．｡]+\s*$/, "").trim();   // the transcript may end with a CJK full stop
    const via = `Muse Voice Transcribe · speech to text · ${sec.toFixed(1)} s`;
    if (/\bexplain\b.*\b(machine|this|it|model|mechanism|gearbox)\b/i.test(t) || /^\s*explain\s*[.!。]?\s*$/i.test(t)) {
      useStore.setState((s) => ({ chat: [...s.chat, { role: "user", text: t, via: via + " → Explain" }] }));
      return useStore.getState().runExplain();
    }
    if (!t.trim() || busy) return;
    useStore.getState().turn("/api/chat", { text: t.trim() }, { role: "user", text: t.trim(), via });
  };

  async function startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(stream), chunks = [];
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        try {
          const blob = await toWav(new Blob(chunks, { type: r.mimeType || "audio/webm" }));
          const t0 = performance.now();
          const res = await fetch("/api/transcribe", { method: "POST", headers: { "Content-Type": "audio/wav" }, body: blob });
          const j = await res.json();
          if (!res.ok) throw new Error(j.error);
          fromVoice(j.text || "", (performance.now() - t0) / 1000);
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
      <div className={`relative flex min-h-0 flex-1 flex-col gap-2 px-3.5 pb-3 ${drag ? "ring-2 ring-inset ring-cyan-glow/50" : ""}`}
        onDragOver={(e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); setDrag(true); } }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { if (e.dataTransfer?.files?.length) { e.preventDefault(); setDrag(false); attach(e.dataTransfer.files); } }}>
        {(chat.length > 0 || busy || h) && (
          <div ref={log} className="scroll-thin min-h-0 flex-1 space-y-2 overflow-y-auto py-1.5 pr-1 [mask-image:linear-gradient(transparent,#000_12px,#000_calc(100%-12px),transparent)]"
            style={lay.win.orchestrator === "max" || h ? undefined : { maxHeight: "min(32vh, 300px)" }}>
            {chat.map((m, i) => m.role === "timeline" ? <Timeline key={i} steps={m.steps} /> : m.role === "steps" ? (
              <ToolSteps key={i} trace={m.trace} />
            ) : (
              <div key={i} className={`group break-words rounded-xl px-3 py-2 text-[12px] leading-relaxed ${m.role === "ai" ? "" : "whitespace-pre-wrap"} ${
                m.role === "user" ? "ml-auto w-fit max-w-[85%] border border-cyan-glow/20 bg-gradient-to-r from-sky-400/[0.10] to-violet-500/[0.10]"
                  : m.role === "error" ? "border border-bad/30 bg-bad/10 text-rose-200" : "mr-6 border border-white/[0.07] bg-white/[0.04] text-white/90"}`}
                title={m.role === "error" ? m.text : undefined}>
                {m.files?.length > 0 && <div className="mb-1.5 flex flex-wrap gap-1">{m.files.map((f) => <Chip key={f.name} f={f} />)}</div>}
                {m.img && <img src={m.img} className="mb-1.5 max-h-64 max-w-full rounded-lg bg-white object-contain" />}
                <div className="select-text">{m.role === "ai" ? <Markdown text={m.text} /> : m.role === "error" ? friendlyError(m.text) : m.text}</div>
                {m.role === "error" && <button type="button" className="mt-1 font-mono text-[10px] text-rose-200/80 hover:text-white"
                  onClick={() => { const prev = chat.slice(0, i).reverse().find((x) => x.role === "user"); if (prev) ask(prev.text, prev.files || []); }}>try again</button>}
                {m.via && <div className="mt-1 font-mono text-[9.5px] text-cyan-glow/80">{m.via}</div>}
                {m.role === "ai" && <Extras x={m.extras} onOption={(o) => send(o)} />}
                {m.role === "ai" && <MsgActions text={m.text} onRetry={busy ? null : () => {
                  const prev = chat.slice(0, i).reverse().find((x) => x.role === "user");
                  if (prev) ask(prev.text, prev.files || []);
                }} />}</div>
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
        {files.length > 0 && <div className="flex shrink-0 flex-wrap gap-1.5">{files.map((f, i) => (
          <Chip key={f.key || f.name} f={f} onRemove={() => setFiles((x) => x.filter((_, j) => j !== i))} />))}</div>}
        <form onSubmit={(e) => { e.preventDefault(); send(); }}
          className={`relative flex shrink-0 items-center gap-1.5 overflow-hidden rounded-xl border bg-black/35 p-1 transition ${busy ? "border-cyan-glow/40" : "border-white/10 focus-within:border-cyan-glow/50 focus-within:shadow-[0_0_24px_rgba(95,225,255,.18)]"}`}>
          <button type="button" title="Hold to talk (Muse Voice)" onPointerDown={startRec} onPointerUp={stopRec} onPointerLeave={stopRec}
            className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg transition ${rec ? "animate-pulse bg-magenta-glow/25 text-magenta-glow" : "text-silver hover:bg-white/10 hover:text-white"}`}>
            <Icon name="mic" /></button>
          <button type="button" title="Attach files: drawings, photos, PDF, GLB / STL / OBJ, STEP (or paste / drop them here)" disabled={busy}
            onClick={() => file.current?.click()}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-silver transition hover:bg-white/10 hover:text-white disabled:opacity-40">
            <Icon name="plus" /></button>
          <input ref={file} id="photo-input" type="file" multiple className="hidden"
            accept="image/*,.pdf,.glb,.gltf,.stl,.obj,.step,.stp"
            onChange={(e) => { attach(e.target.files); e.target.value = ""; }} />
          <input id="ai-input" ref={input} value={text} onChange={(e) => setText(e.target.value)}
            onPaste={(e) => { if (e.clipboardData?.files?.length) { e.preventDefault(); attach(e.clipboardData.files); } }}
            onKeyDown={(e) => e.key === "Escape" && e.target.blur()}
            placeholder={rec ? "Listening… release to send" : "Ask Muse Spark to design, change or check something…"}
            className="min-w-0 flex-1 truncate bg-transparent px-1 py-1.5 text-[12.5px] text-white outline-none placeholder:text-white/35" />
          {busy && <button type="button" title="Stop (after the current step)"
            onClick={() => { fetch("/api/chat/stop", { method: "POST", body: "{}" }); notify("Stopping after the current step…"); }}
            className="relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/10 text-white hover:bg-rose-500/40">
            <span className="h-2.5 w-2.5 rounded-sm bg-white" /></button>}
          {!busy && <button className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-sky-400 via-indigo-500 to-violet-500 text-white shadow-[0_6px_18px_-6px_rgba(99,102,241,.9)] transition hover:brightness-110 disabled:bg-none disabled:bg-white/10 disabled:text-white/30 disabled:shadow-none"
            disabled={(!text.trim() && !files.length) || files.some((f) => f.uploading)}><Icon name="send" /></button>}
          {busy && <div className="pointer-events-none absolute inset-0 busy-sheen" />}
        </form>
      </div>
    </FloatPanel>
  );
}
