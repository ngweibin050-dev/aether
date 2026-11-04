import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useStore } from "../store";

// Every picture in the app opens bigger on double-click (chat images, Explain renders, drawings, panel figures):
// a full-window viewer with zoom (wheel / buttons), drag to pan, download, and × / Esc to close.
// Any <img> works without wiring: one document-level double-click listener; data-nolightbox opts an image out.
export function useLightboxListener() {
  useEffect(() => {
    const on = (e) => {
      const img = e.target.closest?.("img");
      if (!img || img.closest("[data-nolightbox]") || !img.src) return;
      e.preventDefault();
      useStore.getState().openLightbox({ src: img.currentSrc || img.src, title: img.alt || img.title || "" });
    };
    document.addEventListener("dblclick", on);
    return () => document.removeEventListener("dblclick", on);
  }, []);
}

export default function Lightbox() {
  const lb = useStore((s) => s.lightbox);
  const close = () => useStore.getState().openLightbox(null);
  const [z, setZ] = useState(1);
  const [off, setOff] = useState([0, 0]);
  useEffect(() => { setZ(1); setOff([0, 0]); }, [lb?.src]);
  useEffect(() => {
    if (!lb) return;
    const k = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
    addEventListener("keydown", k, true);
    return () => removeEventListener("keydown", k, true);
  }, [lb]);
  if (!lb) return null;
  const drag = (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const x0 = e.clientX - off[0], y0 = e.clientY - off[1];
    const mv = (ev) => setOff([ev.clientX - x0, ev.clientY - y0]);
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  };
  const name = (lb.title || "image").replace(/[^\w.-]+/g, "_").slice(0, 60);
  return createPortal(
    <div className="fixed inset-0 z-[100] flex flex-col bg-black/85 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) close(); }}
      onWheel={(e) => setZ((v) => Math.min(8, Math.max(0.25, v * Math.exp(-e.deltaY * 0.0015))))}>
      <div className="flex shrink-0 items-center gap-2 px-4 py-2 text-[12px] text-slate-200">
        <span className="min-w-0 flex-1 truncate">{lb.title}</span>
        <button className="btn !py-1" onClick={() => setZ((v) => Math.max(0.25, v / 1.25))} title="Zoom out">−</button>
        <span className="w-12 text-center font-mono text-[11px]">{Math.round(z * 100)}%</span>
        <button className="btn !py-1" onClick={() => setZ((v) => Math.min(8, v * 1.25))} title="Zoom in">+</button>
        <button className="btn !py-1" onClick={() => { setZ(1); setOff([0, 0]); }}>Fit</button>
        <a className="btn !py-1" href={lb.src} download={/\.\w{2,4}$/.test(name) ? name : `${name}.png`}>Download</a>
        <button className="grid h-8 w-8 place-items-center rounded-lg bg-white/10 text-[18px] hover:bg-white/20" onClick={close} title="Close (Esc)">×</button>
      </div>
      <div className="relative min-h-0 flex-1 overflow-hidden" onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
        <img src={lb.src} alt={lb.title} data-nolightbox draggable={false} onPointerDown={drag}
          className="absolute left-1/2 top-1/2 max-h-[92%] max-w-[94%] cursor-grab select-none rounded-lg shadow-2xl active:cursor-grabbing"
          style={{ transform: `translate(calc(-50% + ${off[0]}px), calc(-50% + ${off[1]}px)) scale(${z})` }} />
      </div>
    </div>, document.body);
}
