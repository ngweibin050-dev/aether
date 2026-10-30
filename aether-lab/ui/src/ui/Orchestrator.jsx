import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useStore } from "../store";
import FloatPanel from "./FloatPanel";
import Icon from "./Icon";
import { SineLoader } from "./Charts";

const NAMES = {
  build_assembly: "Build assembly", add_part: "Add part", update_part: "Edit part", delete_part: "Delete part",
  list_parts: "Read scene", set_display: "Set optics", set_eye: "Move eye", set_view: "Inspect view", make_hologram: "Calculate hologram",
  propagate: "Propagate light", focus_sweep: "Focus sweep", eye_view: "Eye view", window_check: "Window Law",
  hand_check: "Hand check", desk_check: "Desk sharpness", search_column_width: "Design search",
  speckle_compare: "Speckle", export_film: "Film export", desk_score: "Desk score", optimize_for_desk: "AI design loop",
  sam_3_1: "SAM 3.1 cut-out", turn_gear: "Turn gear", desk_wave_view: "Desk wave check", import_three_view: "Three-view → 3D",
};
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
    case "sam_3_1": return r.mode === "blueprint" ? `${r.parts?.length} parts traced · ${r.scale_source?.startsWith("read") ? "scale read" : "scale assumed"}` : `${r.width_mm}×${r.height_mm} mm${r.lobes_around_centre ? ` · ${r.lobes_around_centre} lobes` : ""}${r.centre_hole ? " · hole" : ""}`;
    default: return "";
  }
}

const EXAMPLES = [
  "Generate a Tesla-style motor and place it 10 cm above the screen",
  "Cut it in half and explode it so I can see the stator and rotor",
  "Can AETHER Desk show this sharply? Check the Window Law too",
  "How grainy will it look, and do sparse point groups help?",
];

function ModeSwitch() {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  return (
    <div className="relative grid grid-cols-2 rounded-xl border border-white/10 bg-black/30 p-1">
      <motion.div layout transition={{ type: "spring", stiffness: 400, damping: 32 }}
        className="absolute inset-y-1 w-[calc(50%-4px)] rounded-lg bg-cyan-glow/15 shadow-inner"
        style={{ left: mode === "laptop" ? 4 : "calc(50%)" }} />
      {[["laptop", "laptop", "Laptop mode"], ["hand", "hand", "Hand tracking"]].map(([m, ic, label]) => (
        <button key={m} onClick={() => setMode(m)}
          className={`relative z-10 flex items-center justify-center gap-2 rounded-lg py-1.5 text-[12px] font-medium transition ${mode === m ? "text-cyan-50" : "text-silver hover:text-white"}`}>
          <Icon name={ic} className="h-3.5 w-3.5" />{label}
          <span className={`h-1.5 w-1.5 rounded-full ${mode === m ? "bg-cyan-glow shadow-glow" : "bg-white/15"}`} />
        </button>
      ))}
    </div>
  );
}

const STEP_LABEL = { build_assembly: "Building the model", focus_sweep: "Eye focus sweep (GPU)", eye_view: "Eye view (GPU)",
  make_hologram: "Lab phase hologram (GPU)", desk_check: "Desk sharpness check", window_check: "Window Law check", set_view: "Changing the view",
  sam_3_1: "SAM 3.1 cutting out the parts", read_drawing: "Muse Spark reads the drawing", layers: "Muse Spark stacks the parts in depth", rebuild_3d: "Rebuilding each part as a 3D solid (gears mesh, pins, plates)", desk_wave_view: "True-scale desk wave simulation", desk_score: "Physics scores the design (GPU)", update_part: "Muse Spark changes the design",
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

// Phone photo of a real part: SAM 3.1 cuts it out, Muse Spark rebuilds it, then the physics runs.
function PhotoForm({ image, onCancel }) {
  const askPhoto = useStore((s) => s.askPhoto);
  const [prompt, setPrompt] = useState("gear");
  const [size, setSize] = useState(80);
  const many = prompt.split(",").filter((x) => x.trim()).length > 1;
  return (
    <form onSubmit={(e) => { e.preventDefault(); onCancel(); askPhoto(image, prompt.trim() || "object", Number(size) || 80); }}
      className="flex gap-2 rounded-xl border border-cyan-glow/25 bg-cyan-glow/[0.05] p-2">
      <img src={image} className="h-16 w-16 shrink-0 rounded-lg object-cover" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex gap-1.5">
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="gear  ·  or a drawing: gear, wheel, lever" title="One noun = one part. Several nouns, comma separated = a drawing of a whole machine: SAM 3.1 finds every part of each kind."
            className="field min-w-0 flex-1 !py-1 text-[11.5px]" />
          <label className="flex items-center gap-1 font-mono text-[10px] text-silver">
            <input type="number" value={size} onChange={(e) => setSize(e.target.value)} className="field w-14 !py-1 text-[11px]" title={many ? "ASSUMED real size of the drawing's longest side - used only if Muse Spark cannot read a dimension on the drawing" : "ASSUMED longest side of the part (a photo has no scale)"} />mm?</label>
        </div>
        <div className="flex gap-1.5">
          <button type="button" onClick={() => { setPrompt("gear, wheel, lever, shaft"); setSize(240); }} title="A drawing of a whole machine"
            className={`btn !py-1 text-[11px] ${many ? "!border-cyan-glow/40 text-cyan-glow" : ""}`}>Blueprint</button>
          <button className="btn-accent flex-1 !py-1 text-[11px]">{many ? "SAM 3.1 → machine" : "SAM 3.1 → model"}</button>
          <button type="button" onClick={onCancel} className="btn !py-1 text-[11px]">Cancel</button>
        </div>
      </div>
    </form>
  );
}

// What Muse Spark is doing right now: one line per model call or tool, live from the server.
function LiveSteps() {
  const steps = useStore((s) => s.progress);
  const list = steps.length ? steps : [{ label: "Muse Spark", state: "run" }];
  return (
    <div className="space-y-1 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2">
      {list.map((st, i) => (
        <div key={i} className="flex items-center gap-2 font-mono text-[10.5px]">
          <span className={`h-1.5 w-1.5 rounded-full ${st.state === "run" ? "animate-pulse bg-cyan-glow shadow-glow" : st.state === "error" ? "bg-bad" : "bg-ok"}`} />
          <span className={st.state === "run" ? "text-white" : "text-silver"}>{st.label === "Muse Spark" ? "Muse Spark is thinking" : STEP_LABEL[st.label] || st.label.replace(/_/g, " ")}</span>
          {st.state === "run" && <SineLoader label="" className="ml-auto scale-75" />}
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

  return (
    <FloatPanel id="orchestrator" title="Orchestrator" icon="sparkle" open={open} busy={busy}
      onClose={() => useStore.getState().setPanel("orchestrator", false)}
      className="left-3 top-[60px] w-[310px] max-h-[calc(50vh-30px)]">
      <div className="space-y-2.5 px-3.5 pb-3">
        <ModeSwitch />
        <form onSubmit={(e) => { e.preventDefault(); send(); }}
          className={`relative flex items-center gap-1.5 overflow-hidden rounded-xl border bg-black/35 p-1 transition ${busy ? "border-cyan-glow/40" : "border-white/10 focus-within:border-cyan-glow/50 focus-within:shadow-[0_0_24px_rgba(95,225,255,.18)]"}`}>
          <button type="button" title="Hold to talk (Muse Voice)" onPointerDown={startRec} onPointerUp={stopRec} onPointerLeave={stopRec}
            className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg transition ${rec ? "animate-pulse bg-magenta-glow/25 text-magenta-glow" : "text-silver hover:bg-white/10 hover:text-white"}`}>
            <Icon name="mic" /></button>
          <button type="button" title="Photo of a real part → SAM 3.1 → model" disabled={busy} onClick={() => file.current?.click()}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-silver transition hover:bg-white/10 hover:text-white disabled:opacity-40">
            <Icon name="camera" /></button>
          <input ref={file} id="photo-input" type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => { pickPhoto(e.target.files?.[0]); e.target.value = ""; }} />
          <input id="ai-input" ref={input} value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && e.target.blur()}
            placeholder={rec ? "Listening… release to send" : "Ask Muse Spark to design or analyse…"}
            className="min-w-0 flex-1 bg-transparent px-1 py-1.5 text-[12.5px] text-white outline-none placeholder:text-white/35" />
          <button className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-cyan-glow/90 text-ink-950 transition hover:bg-cyan-glow disabled:bg-white/10 disabled:text-white/30"
            disabled={busy || !text.trim()}><Icon name="send" /></button>
          {busy && <div className="pointer-events-none absolute inset-0 busy-sheen" />}
        </form>
        {photo && <PhotoForm image={photo} onCancel={() => setPhoto(null)} />}
        <div ref={log} className="scroll-thin max-h-[calc(50vh-190px)] min-h-0 space-y-2 overflow-y-auto pr-1">
          {!chat.length && EXAMPLES.map((q) => (
            <button key={q} onClick={() => send(q)} className="block w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-2.5 py-1.5 text-left text-[11.5px] leading-snug text-white/70 transition hover:border-cyan-glow/30 hover:text-white">{q}</button>))}
          {chat.map((m, i) => m.role === "steps" ? (
            <div key={i} className="space-y-1">{m.trace.map((t, j) => (
              <div key={j} className="flex items-center gap-2 rounded-md border border-white/[0.06] bg-black/25 px-2 py-1 text-[11px]">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${t.result.error ? "bg-bad" : "bg-cyan-glow shadow-glow"}`} />
                <span className="text-white/85">{NAMES[t.tool] || t.tool}</span>
                <span className="ml-auto truncate font-mono text-[10px] text-cyan-glow/80">{summary(t)}</span>
              </div>))}</div>
          ) : (
            <div key={i} className={`whitespace-pre-wrap rounded-xl px-3 py-2 text-[12px] leading-relaxed ${
              m.role === "user" ? "ml-6 border border-cyan-glow/20 bg-cyan-glow/[0.08]"
                : m.role === "error" ? "border border-bad/30 bg-bad/10 text-rose-200" : "mr-2 border border-white/[0.07] bg-white/[0.04] text-white/90"}`}>
              {m.img && <img src={m.img} className="mb-1.5 h-20 rounded-lg object-cover" />}{m.text}</div>
          ))}
          {busy && <LiveSteps />}
        </div>
      </div>
    </FloatPanel>
  );
}
