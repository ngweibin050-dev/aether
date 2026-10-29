import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import Icon from "./Icon";

const NAMES = {
  build_assembly: "Build assembly", add_part: "Add part", update_part: "Edit part", delete_part: "Delete part",
  list_parts: "Read scene", set_display: "Set optics", set_eye: "Move eye", make_hologram: "Calculate hologram",
  propagate: "Propagate light", focus_sweep: "Focus sweep", eye_view: "Eye view", window_check: "Window Law",
  hand_check: "Hand check", desk_check: "Desk sharpness", search_column_width: "Design search",
  speckle_compare: "Speckle", export_film: "Film export",
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
    case "search_column_width": return r.largest_column_width_um ? `best ${r.largest_column_width_um} µm` : r.result;
    case "speckle_compare": return `C ${r.one_frame} → ${r.sparse_groups}`;
    case "eye_view": return `eye x ${r.eye_mm?.[0]} mm`;
    default: return "";
  }
}

const EXAMPLES = [
  "Design a compact brushless electric motor and show me its hologram",
  "Build a simplified rocket engine with a bell nozzle and turbopump",
  "Can AETHER Desk show this sharply? Check the Window Law too",
  "How grainy will it look, and do sparse point groups help?",
];

export default function Assistant() {
  const chat = useStore((s) => s.chat);
  const busy = useStore((s) => s.busy.chat);
  const ask = useStore((s) => s.ask);
  const notify = useStore((s) => s.notify);
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [rec, setRec] = useState(null);
  const log = useRef();
  const input = useRef();

  useEffect(() => { if (chat.length) setOpen(true); }, [chat.length]);
  useEffect(() => { log.current && (log.current.scrollTop = 1e9); }, [chat, busy]);
  useEffect(() => {
    const f = (e) => { if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); input.current.focus(); } };
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
        const blob = new Blob(chunks, { type: r.mimeType || "audio/webm" });
        try {
          const res = await fetch("/api/transcribe", { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
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
    <div className="pointer-events-auto absolute bottom-4 left-1/2 z-30 w-[min(640px,calc(100vw-900px))] min-w-[420px] -translate-x-1/2">
      {open && (
        <div className="glass mb-2 max-h-[38vh] overflow-hidden animate-floatin">
          <div className="flex items-center justify-between border-b border-line px-4 py-2">
            <div className="flex items-center gap-2 font-display text-[13px] font-semibold"><Icon name="sparkle" className="h-4 w-4 text-cyan-glow" />AETHER · Muse Spark</div>
            <button className="text-slate-400 hover:text-white" onClick={() => setOpen(false)}><Icon name="close" /></button>
          </div>
          <div ref={log} className="scroll-thin max-h-[30vh] space-y-2.5 overflow-y-auto px-4 py-3">
            {!chat.length && (
              <div className="grid grid-cols-2 gap-2">{EXAMPLES.map((q) => (
                <button key={q} onClick={() => send(q)} className="rounded-xl border border-line bg-white/[0.03] px-3 py-2 text-left text-[12.5px] text-slate-300 hover:border-cyan-glow/40 hover:text-white">{q}</button>))}</div>
            )}
            {chat.map((m, i) => m.role === "steps" ? (
              <div key={i} className="space-y-1">{m.trace.map((t, j) => (
                <div key={j} className="flex items-center gap-2.5 rounded-lg border border-cyan-glow/15 bg-cyan-glow/[0.05] px-2.5 py-1.5 text-[11.5px] animate-floatin">
                  <span className={`h-1.5 w-1.5 rounded-full ${t.result.error ? "bg-bad" : "bg-cyan-glow shadow-glow"}`} />
                  <span className="font-medium text-slate-200">{NAMES[t.tool] || t.tool}</span>
                  <span className="ml-auto truncate font-mono text-[10.5px] text-cyan-glow/90">{summary(t)}</span>
                </div>))}</div>
            ) : (
              <div key={i} className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed animate-floatin ${
                m.role === "user" ? "ml-auto bg-gradient-to-br from-cyan-glow/20 to-violet-glow/20 border border-cyan-glow/25"
                  : m.role === "error" ? "border border-bad/40 bg-bad/10 text-rose-200" : "border border-line bg-white/[0.04]"}`}>{m.text}</div>
            ))}
            {busy && <div className="flex gap-1.5 px-1 py-2">{[0, 1, 2].map((k) => <i key={k} className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-glow" style={{ animationDelay: `${k * 150}ms` }} />)}<span className="ml-2 text-[11.5px] text-slate-400">planning and running tools…</span></div>}
          </div>
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); send(); }}
        className={`glass flex items-center gap-2 p-1.5 transition ${busy ? "busy-sheen" : ""} focus-within:border-cyan-glow/50`}>
        <button type="button" title="Hold to talk" onPointerDown={startRec} onPointerUp={stopRec} onPointerLeave={stopRec}
          className={`grid h-10 w-10 place-items-center rounded-xl border transition ${rec ? "border-bad/60 bg-bad/20 text-bad animate-pulse" : "border-line bg-white/[0.04] text-slate-200 hover:border-cyan-glow/50"}`}>
          <Icon name="mic" /></button>
        <input ref={input} value={text} onChange={(e) => setText(e.target.value)} onFocus={() => setOpen(true)}
          placeholder={rec ? "Listening… release to send" : "Ask AETHER to design, edit or analyse…   ( / )"}
          className="min-w-0 flex-1 bg-transparent px-2 py-2 text-[14px] text-slate-100 outline-none placeholder:text-slate-500" />
        <button className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-cyan-glow to-violet-glow text-ink-950 disabled:opacity-40" disabled={busy || !text.trim()}>
          <Icon name="send" /></button>
      </form>
    </div>
  );
}
