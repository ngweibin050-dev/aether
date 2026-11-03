import { useMemo, useState } from "react";
import { useStore } from "../store";
import FloatPanel, { PanelIcon } from "./FloatPanel";
import { L, useLayout } from "./layout";

// The drawing as Muse Spark read it, ballooned like an inspection sheet: every part kept from the reading carries a
// numbered balloon at the place it was read, linked to the solid it became. Status per balloon:
//   agreed   - both temperature-0 readings found it (whole sheet or a close-up)
//   measured - an exact circle measured on the ink (compass-style), not a model's guess
//   dropped  - only one reading saw it and nothing on the ink confirms it: shown, never built
// Parts Muse Wonder added (not on the drawing) are listed with their reason, without a balloon.

const STATUS = {
  agreed: ["✓", "text-emerald-300", "#f97316", "Agreed by both Muse Spark readings"],
  measured: ["◉", "text-cyan-300", "#0ea5e9", "Exact circle measured on the drawing"],
  dropped: ["✕", "text-slate-500", "#64748b", "Not confirmed: dropped, not built"],
};

export default function DrawingPanel() {
  const open = useStore((s) => s.panels.drawing);
  const sam = useStore((s) => s.results.sam);
  const recorded = useStore((s) => s.recorded);
  const parts = useStore((s) => s.state?.parts || []);
  const asm = useStore((s) => s.asm);
  const active = useStore((s) => s.state?.selected);
  const st = useStore();
  const [tab, setTab] = useState("parts");
  const [hover, setHover] = useState(null);

  const src = recorded?.id ? `/demo/${recorded.id}.png` : "/api/drawing";
  const W = sam?.photo_px?.[0] || 1, H = sam?.photo_px?.[1] || 1, mm = sam?.mm_per_px || 1;
  const rows = useMemo(() => {
    if (!sam?.parts) return [];
    return sam.parts.map((p) => {
      const solid = parts.find((q) => q.eng?.from_drawing === p.label && q.name.endsWith(` ${p.n}`))
        || parts.find((q) => q.name === `${p.label} ${p.n}`);
      const x = (p.centre_mm[0] / mm + W / 2) / W, y = (H / 2 - p.centre_mm[1] / mm) / H;
      return { ...p, status: p.read_from ? "agreed" : "measured", x, y, solid };
    });
  }, [sam, parts, W, H, mm]);
  const dropped = useMemo(() => (sam?.reading?.dropped || []).map((d, i) => ({ ...d, i,
    x1: d.box[0] / W, y1: d.box[1] / H, x2: d.box[2] / W, y2: d.box[3] / H })), [sam, W, H]);
  const inferred = parts.filter((p) => p.eng?.reason);
  const verified = rows.length;
  const total = rows.length + dropped.length;

  const pick = (r) => { if (r.solid) { st.select(r.solid.id); } setHover(r.n); };
  const lay = useLayout();
  const style = { left: lay.toolLeft + 56, right: lay.navRight + 56, top: L.top, bottom: L.bottom + 12 };

  return (<>
    <PanelIcon id="drawing" title="Drawing reading" icon="search" style={{ left: lay.toolLeft + 56, top: L.top + 56 }} />
    <FloatPanel id="drawing" title="Drawing reading · Muse Spark" icon="search" open={open} onClose={() => st.setPanel("drawing", false)} style={style}>
      {!sam?.parts ? <div className="px-4 py-4 text-slate-400">No drawing read yet: build a machine from a drawing (Demo menu or upload).</div> :
        <div className="flex min-h-0 flex-1 gap-3 px-3 pb-3">
          <div className="relative min-h-0 min-w-0 flex-1 overflow-auto rounded-lg border border-white/10 bg-[#f4f1ea]">
            <div className="relative" style={{ aspectRatio: `${W} / ${H}` }}>
              <img src={src} alt="The drawing that was read" className="absolute inset-0 h-full w-full object-contain" />
              <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
                {tab === "dropped" && dropped.map((d) => <rect key={d.i} x={d.x1} y={d.y1} width={d.x2 - d.x1} height={d.y2 - d.y1}
                  fill="none" stroke="#64748b" strokeWidth="0.002" strokeDasharray="0.006 0.004" />)}
              </svg>
              {tab !== "dropped" && rows.map((r) => {
                const on = hover === r.n || (r.solid && r.solid.id === active);
                return (
                  <button key={r.n} onClick={() => pick(r)} onMouseEnter={() => setHover(r.n)} title={`${r.label} · ${STATUS[r.status][3]}`}
                    style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, background: on ? "#facc15" : "#fff", borderColor: STATUS[r.status][2] }}
                    className={`absolute grid h-[22px] min-w-[22px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 px-0.5 font-mono text-[10px] font-bold text-slate-900 shadow ${on ? "z-10 scale-125" : ""}`}>
                    {r.n}</button>);
              })}
            </div>
          </div>
          <div className="flex w-[300px] shrink-0 flex-col">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px]">
              <div className="font-mono text-slate-200">{verified}/{total} kept · {dropped.length} dropped</div>
              <div className="text-[10px] text-slate-500">{sam.reading?.settings || sam.read_by}</div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10"><i className="block h-full bg-emerald-400" style={{ width: `${(100 * verified) / Math.max(total, 1)}%` }} /></div>
              <div className="mt-1 text-[10px] text-slate-500">Scale: {sam.scale_source} ({mm} mm/px)</div>
            </div>
            <div className="mt-2 flex gap-1">
              {[["parts", `Parts ${rows.length}`], ["dropped", `Dropped ${dropped.length}`], ["inferred", `Inferred ${inferred.length}`]].map(([k, t]) =>
                <button key={k} onClick={() => setTab(k)} className={`btn !px-2 !py-0.5 text-[11px] ${tab === k ? "!border-cyan-glow/50 text-cyan-glow" : ""}`}>{t}</button>)}
            </div>
            <div className="scroll-thin mt-2 min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
              {tab === "parts" && rows.map((r) => {
                const rec = r.solid && asm?.records?.[r.solid.id];
                return (
                  <button key={r.n} onClick={() => pick(r)} onMouseEnter={() => setHover(r.n)}
                    className={`flex w-full items-center gap-2 rounded-md border px-2 py-1 text-left text-[11px] ${hover === r.n || (r.solid && r.solid.id === active) ? "border-amber-300/50 bg-amber-300/10" : "border-white/[0.07] hover:bg-white/5"}`}>
                    <span className="grid h-5 min-w-5 place-items-center rounded-full px-1 font-mono text-[10px] font-bold text-white" style={{ background: STATUS[r.status][2] }}>{r.n}</span>
                    <span className="min-w-0 flex-1"><span className="block truncate text-slate-100">{r.label}</span>
                      <span className="block truncate font-mono text-[9.5px] text-slate-500">{r.kind} · {r.length_mm}×{r.width_mm} mm{r.read_from ? ` · ${r.read_from}` : ""}</span></span>
                    <span className={`font-mono text-[10px] ${STATUS[r.status][1]}`} title={STATUS[r.status][3]}>{STATUS[r.status][0]}</span>
                    {rec && <span title={rec.validation?.valid ? "Its B-rep solid passes BRepCheck" : "Its B-rep solid failed validation"}
                      className={`font-mono text-[9.5px] ${rec.validation?.valid ? "text-emerald-300" : "text-rose-400"}`}>solid</span>}
                  </button>);
              })}
              {tab === "dropped" && dropped.map((d) => (
                <div key={d.i} className="rounded-md border border-white/[0.07] px-2 py-1 text-[11px]">
                  <div className="text-slate-300"><span className="text-slate-500">✕</span> {d.label} <span className="font-mono text-[9.5px] text-slate-500">{d.type} · {d.from}</span></div>
                  <div className="text-[10px] text-slate-500">{d.why}</div></div>))}
              {tab === "inferred" && inferred.map((p) => (
                <button key={p.id} onClick={() => st.select(p.id)} className="block w-full rounded-md border border-amber-300/20 bg-amber-300/5 px-2 py-1 text-left text-[11px]">
                  <div className="text-amber-100">{p.name}</div><div className="text-[10px] text-amber-300/80">{p.eng.reason}</div></button>))}
            </div>
          </div>
        </div>}
    </FloatPanel>
  </>);
}
