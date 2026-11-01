import { useCallback, useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import { api } from "../api";
import FloatPanel, { PanelIcon } from "./FloatPanel";
import { L } from "./layout";

// The CAD document of the current model (cad/ worker): maturity and recompute status, the feature tree with each
// feature's status, every parameter with its provenance (measured / derived / inferred / assumed / user-confirmed),
// editable (a transactional recompute: rolled back if it fails), the assumptions, and the exports. The 3D view shows a
// tessellation of the validated B-rep; this panel edits the document, never the mesh.

const PROV = {
  measured: ["measured", "text-emerald-300", "On the drawing (px), converted with the scale"],
  derived: ["derived", "text-sky-300", "Computed from measured values and stated relations"],
  inferred: ["inferred", "text-amber-300", "Estimated from projections, conventions or Muse Wonder (bounded by the drawing)"],
  assumed: ["assumed", "text-orange-400", "Not in the drawing: a stated default"],
  unresolved: ["unresolved", "text-rose-400", "Not determined: needs your decision"],
  user_confirmed: ["user", "text-violet-300", "Entered or confirmed by you"],
  external_reference: ["external", "text-slate-300", "From outside the drawing, with its source"],
};
const ST = { ok: "text-emerald-300", failed: "text-rose-400", blocked: "text-slate-500", stale: "text-amber-300" };

function Num({ p, onCommit, busy }) {
  const [v, setV] = useState(String(+Number(p.value).toFixed(3)));
  useEffect(() => setV(String(+Number(p.value).toFixed(3))), [p.value]);
  const commit = () => { const n = parseFloat(v); if (!Number.isNaN(n) && Math.abs(n - p.value) > 1e-9) onCommit(n); else setV(String(+Number(p.value).toFixed(3))); };
  return <input className="field !py-0.5 w-24 text-right font-mono text-[11px]" disabled={busy} value={v}
    onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && e.target.blur()} />;
}

export default function CadPanel() {
  const open = useStore((s) => s.panels.cad);
  const st = useStore();
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState("params");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const hasCad = useStore((s) => (s.state?.parts || []).some((p) => p.type === "cad"));

  const load = useCallback(() => {
    fetch("/api/cad/document").then((r) => r.json()).then((j) => { if (j.error) { setErr(j.error); setDoc(null); } else { setErr(null); setDoc(j); } })
      .catch((e) => setErr(String(e)));
  }, []);
  useEffect(() => { if (open || hasCad) load(); }, [open, hasCad, load]);
  useEffect(() => { if (hasCad && !useStore.getState().panels.cad) useStore.getState().setPanel("cad", true); }, [hasCad]);

  const edit = async (id, value, clear) => {
    setBusy(true);
    try {
      const j = await api("/api/cad/param", clear ? { id, clear_override: true } : { id, value });
      useStore.getState().applyState(j.state);
      const ok = j.edit.status.state === "ok";
      st.notify(ok ? `${id} = ${value} · recomputed ${j.edit.status.rebuilt_features} feature(s) in ${j.edit.seconds} s`
        : `Recompute failed at ${j.edit.status.failed}: ${j.edit.status.error} - edit rolled back`, ok ? "info" : "error");
    } catch (e) { st.notify(e.message, "error"); }
    setBusy(false);
    load();
  };

  const params = useMemo(() => (doc?.parameters || []).filter((p) => typeof p.value === "number" && !p.id.endsWith("._scale"))
    .filter((p) => !q || p.id.toLowerCase().includes(q.toLowerCase()) || (p.note || "").toLowerCase().includes(q.toLowerCase())), [doc, q]);
  const counts = useMemo(() => (doc?.parameters || []).reduce((a, p) => ({ ...a, [p.provenance]: (a[p.provenance] || 0) + 1 }), {}), [doc]);
  const s = doc?.status || {};
  const style = { right: L.right + 2 * L.gap, top: L.top, bottom: L.bottom + 170, width: 380 };

  return (<>
    <PanelIcon id="cad" title="CAD document" icon="holo" style={{ right: L.right + 2 * L.gap, top: L.top }} busy={busy} />
    <FloatPanel id="cad" title="CAD document" icon="holo" open={open} busy={busy} onClose={() => st.setPanel("cad", false)} style={style}>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3.5 pb-3 text-[12px]">
        {!doc && <div className="py-4 text-slate-400">{err ? `No CAD document yet (${err}). Upload a three-view sheet: it is rebuilt as parametric CAD.` : "Loading…"}</div>}
        {doc && <>
          <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
            <div className="truncate font-display text-[13px] font-bold text-white">{doc.title}</div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10.5px]">
              <span>maturity <span className="text-cyan-glow">{doc.maturity.replace(/_/g, " ")}</span></span>
              <span>recompute <span className={ST[s.state] || "text-slate-300"}>{s.state}</span>{s.seconds != null && ` · ${s.seconds} s`}</span>
              {doc.stale && <span className="text-amber-300">geometry shown is STALE (last valid)</span>}
            </div>
            {s.state === "failed" && <div className="mt-1 text-rose-300">Failed at {s.failed}: {s.error}</div>}
            {s.last_failed_edit && <div className="mt-1 text-amber-300">Last edit rolled back: {s.last_failed_edit.param}</div>}
            <div className="mt-1.5 flex flex-wrap gap-1.5 font-mono text-[10px]">
              {Object.entries(counts).map(([k, n]) => <span key={k} title={PROV[k]?.[2]} className={PROV[k]?.[1]}>{PROV[k]?.[0] || k} {n}</span>)}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[["STEP", "/api/cad/export.step", "model.step"], ["GLB", "/api/cad/export.glb", "model.glb"],
                [".aethercad", "/api/cad/export.aethercad", "model.aethercad"], ["Report", "/api/cad/report.json", "report.json"]].map(([t, u, f]) =>
                <a key={t} className="btn !py-0.5 text-[11px]" href={u} download={f} title={`Download ${f} (from the validated B-rep)`}>{t}</a>)}
            </div>
          </div>
          <div className="mt-2 flex gap-1">
            {[["params", "Parameters"], ["features", "Feature tree"], ["assumptions", "Assumptions"], ["checks", "Checks"]].map(([k, t]) =>
              <button key={k} onClick={() => setTab(k)} className={`btn !py-0.5 text-[11px] ${tab === k ? "!border-cyan-glow/50 text-cyan-glow" : ""}`}>{t}</button>)}
          </div>
          {tab === "params" && <>
            <input className="field mt-2 w-full !py-1 text-[11.5px]" placeholder="filter, e.g. wheelbase, st12, depth" value={q} onChange={(e) => setQ(e.target.value)} />
            <div className="mt-1.5 space-y-0.5">
              {params.slice(0, 160).map((p) => (
                <div key={p.id} className="flex items-center gap-2 border-b border-white/[0.05] py-1" title={[p.note, ...(p.evidence || [])].filter(Boolean).join("\n")}>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-mono text-[11px] text-slate-200">{p.id}</div>
                    <div className="font-mono text-[9.5px]"><span className={PROV[p.provenance]?.[1]}>{PROV[p.provenance]?.[0]}</span>
                      <span className="text-slate-500"> · {p.kind}{p.unit ? ` · ${p.unit}` : ""}</span></div>
                  </div>
                  {p.kind === "override" && <button className="text-[10px] text-slate-400 hover:text-white" title="Remove your value: back to the drawing-derived one" onClick={() => edit(p.id, null, true)}>reset</button>}
                  <Num p={p} busy={busy} onCommit={(n) => edit(p.id, n)} />
                </div>))}
              {params.length > 160 && <div className="py-1 text-slate-500">… {params.length - 160} more: filter to find them</div>}
            </div>
          </>}
          {tab === "features" && <div className="mt-2 space-y-0.5">
            {doc.features.map((f) => (
              <div key={f.id} className="border-b border-white/[0.05] py-1" title={`${f.op}\ninputs: ${f.inputs.join(", ") || "-"}\nparameters: ${f.params.join(", ")}`}>
                <div className="flex items-center gap-2"><span className={`font-mono text-[10px] ${ST[f.status] || "text-slate-400"}`}>●</span>
                  <span className="truncate text-slate-200">{f.label || f.id}</span></div>
                <div className="pl-4 font-mono text-[9.5px] text-slate-500">{f.id} · {f.op}{f.error ? ` · ${f.error}` : ""}</div>
              </div>))}
          </div>}
          {tab === "assumptions" && <div className="mt-2 space-y-1.5">
            {doc.assumptions.map((a) => (
              <div key={a.id} className="rounded-md border border-white/[0.07] px-2 py-1.5">
                <div className="font-mono text-[10px]"><span className="text-slate-400">{a.id}</span> <span className={PROV[a.class]?.[1]}>{a.class}</span></div>
                <div className="text-slate-200">{a.text}</div>
                {a.editable_via?.length > 0 && <div className="font-mono text-[9.5px] text-slate-500">edit: {a.editable_via.join(", ")}</div>}
              </div>))}
            {Object.entries(doc.decisions || {}).map(([k, d]) => d && typeof d === "object" && (
              <div key={k} className="font-mono text-[10px] text-slate-400">{k}: <span className="text-slate-200">{String(d.value)}</span> <span className={PROV[d.provenance]?.[1]}>{d.provenance}</span></div>))}
          </div>}
          {tab === "checks" && <div className="mt-2 space-y-2">
            {doc.validation?.summary && <div className="font-mono text-[10.5px] text-slate-300">
              all solids valid: {String(doc.validation.summary.all_valid)} · STEP round trip: {String(doc.validation.summary.step_roundtrip_pass)}
              <div>reprojection IoU: {Object.entries(doc.validation.summary.reprojection_iou || {}).map(([k, v]) => `${k} ${v}`).join(" · ")}</div>
            </div>}
            {["side", "top", "front", "rear"].map((v) => <img key={v} alt={`${v} view reprojection`} className="w-full rounded border border-white/10"
              src={`/api/cad/image/reproject_${v}.png?t=${doc.status?.param_hash || ""}`} />)}
            <div className="text-[10.5px] text-slate-400">Grey: drawing. Cyan: model outline. Red: drawn, not covered. Magenta: model where nothing is drawn.
              A matching silhouette does not prove the hidden shape: the sections between the end views are inferred.</div>
          </div>}
        </>}
      </div>
    </FloatPanel>
  </>);
}
