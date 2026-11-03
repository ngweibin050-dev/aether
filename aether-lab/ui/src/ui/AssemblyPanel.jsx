import { useEffect, useMemo, useState } from "react";
import { useStore } from "../store";
import FloatPanel, { PanelIcon } from "./FloatPanel";
import Icon from "./Icon";
import { L, useLayout } from "./layout";

// The machine as a B-rep assembly (cad/assembly.py, OpenCascade): every part an exact solid built from its own
// parameters, checked by BRepCheck, with its mass properties; the assembly tree by sub-assembly; the mates found on
// the solids, each measured; contacts and interference; STEP export re-read and compared in a fresh process.
// Every number shown here comes from the worker's report, nothing is computed from the display mesh.

const f3 = (v) => (v == null ? "-" : Math.abs(v) >= 1e4 ? v.toExponential(3) : (+v).toFixed(3));
const MATE_ICON = { "Coaxial": "◎", "Concentric (pin in bore)": "⊙", "Gear mesh": "⚙", "Mate (face to face)": "▤" };

function Row({ k, v, cls = "text-slate-200" }) {
  return <div className="flex justify-between gap-3 border-b border-white/[0.05] py-0.5"><span className="text-slate-400">{k}</span>
    <span className={`text-right font-mono text-[10.5px] ${cls}`}>{v}</span></div>;
}

function Sec({ title, children, open: o = true }) {
  const [open, setOpen] = useState(o);
  return (
    <div className="mt-2">
      <button className="flex w-full items-center gap-1 text-left font-display text-[11.5px] font-semibold text-white" onClick={() => setOpen(!open)}>
        <Icon name="chevron" className={`h-3 w-3 transition ${open ? "rotate-90" : ""}`} />{title}</button>
      {open && <div className="mt-1 pl-1">{children}</div>}
    </div>
  );
}

function Tree({ asm, sel, onPick }) {
  const [shut, setShut] = useState({});
  const st = useStore();
  return (
    <div className="mt-2 font-mono text-[11px]">
      <div className="flex items-center gap-1.5 text-white"><span className="text-cyan-glow">▣</span>AETHER_ASSEMBLY
        <span className="text-slate-500">· {asm.summary.built} solids</span></div>
      {asm.groups.map((g) => (
        <div key={g.id} className="ml-2 border-l border-white/10 pl-2">
          <div className="group flex items-center gap-1 py-0.5">
            <button onClick={() => setShut({ ...shut, [g.id]: !shut[g.id] })} className="flex flex-1 items-center gap-1 text-left text-slate-100">
              <Icon name="chevron" className={`h-3 w-3 transition ${shut[g.id] ? "" : "rotate-90"}`} />
              <span className={g.id === "inferred" ? "text-amber-300" : ""}>{g.name}</span>
              <span className="text-slate-500">({g.parts.length})</span></button>
            <button className="hidden text-[10px] text-slate-400 hover:text-white group-hover:block" title="Isolate this sub-assembly"
              onClick={() => { st.selectMany(g.parts); st.setView({ isolate: g.parts }, { now: true }); }}>isolate</button>
          </div>
          {!shut[g.id] && g.parts.map((id) => {
            const r = asm.records[id];
            const ok = r?.validation?.valid;
            return (
              <button key={id} onClick={() => onPick(id)} title={r?.built ? r.exact : r?.reason}
                className={`ml-4 flex w-[calc(100%-1rem)] items-center gap-1.5 rounded px-1 py-[1px] text-left ${sel === id ? "bg-cyan-glow/15 text-white" : "text-slate-300 hover:bg-white/5"}`}>
                <span className={!r?.built ? "text-slate-500" : ok ? "text-emerald-300" : "text-rose-400"}>{!r?.built ? "○" : ok ? "●" : "✕"}</span>
                <span className="truncate">{r?.name || id}</span>
                <span className="ml-auto shrink-0 text-[9.5px] text-slate-500">{r?.type}</span>
              </button>);
          })}
        </div>
      ))}
    </div>
  );
}

function Mates({ asm, onPick }) {
  const st = useStore();
  const by = useMemo(() => asm.mates.reduce((a, m) => ({ ...a, [m.type]: [...(a[m.type] || []), m] }), {}), [asm]);
  const name = (id) => asm.records[id]?.name || id;
  return (
    <div className="mt-2 space-y-1">
      {Object.entries(by).map(([t, ms]) => (
        <Sec key={t} title={`${MATE_ICON[t] || "·"} ${t} (${ms.length}) · ${ms.filter((m) => m.satisfied).length} satisfied`}>
          {ms.map((m, i) => (
            <button key={i} title={`${m.check}\nsource: ${m.source}`} onClick={() => { st.selectMany([m.a, m.b]); onPick(m.a); }}
              className="flex w-full items-start gap-1.5 rounded px-1 py-0.5 text-left font-mono text-[10.5px] hover:bg-white/5">
              <span className={m.satisfied ? "text-emerald-300" : "text-rose-400"}>{m.satisfied ? "✓" : "✕"}</span>
              <span className="min-w-0 flex-1"><span className="text-slate-200">{name(m.a)}</span><span className="text-slate-500"> ↔ </span>
                <span className="text-slate-200">{name(m.b)}</span>
                <div className="truncate text-[9.5px] text-slate-500">{m.check}</div></span>
            </button>))}
        </Sec>))}
      {!asm.mates.length && <div className="text-slate-400">No mates found on the solids.</div>}
    </div>
  );
}

function Checks({ asm, onPick }) {
  const st = useStore();
  const name = (id) => asm.records[id]?.name || id;
  const inter = asm.pairs.filter((p) => p.status === "interference").sort((a, b) => b.common_mm3 - a.common_mm3);
  const bad = Object.values(asm.records).filter((r) => r.built && !r.validation?.valid);
  const notBuilt = Object.values(asm.records).filter((r) => !r.built);
  const s = asm.summary;
  return (
    <div className="mt-2 text-[11px]">
      <Row k="Solids passing BRepCheck" v={`${s.valid_solids} / ${s.built}`} cls={s.invalid_solids ? "text-rose-300" : "text-emerald-300"} />
      <Row k="Parts with no exact B-rep" v={s.not_built} cls={s.not_built ? "text-amber-300" : "text-slate-200"} />
      <Row k="Exact circles (bores, wheels, shafts)" v={s.exact_circles} />
      <Row k="Pairs checked (boxes touch)" v={s.pairs_checked} />
      <Row k="Contacts (distance ≤ 0.02 mm)" v={s.contacts} />
      <Row k="Interferences (common volume)" v={`${s.interferences} · ${f3(s.interference_mm3)} mm³`} cls={s.interferences ? "text-amber-300" : "text-emerald-300"} />
      <Row k="Time: build / validate / total" v={`${s.seconds.build} / ${s.seconds.validate} / ${s.seconds.total} s`} />
      {bad.length > 0 && <Sec title={`Invalid solids (${bad.length})`}>{bad.map((r) => (
        <button key={r.id} onClick={() => onPick(r.id)} className="block w-full truncate text-left font-mono text-[10.5px] text-rose-300">
          {r.name}: {r.validation?.error || (r.validation?.brepcheck_failures || []).map((x) => `${x.type} ${x.status.join("/")}`).join(", ") || `free edges ${r.validation?.free_edges}`}</button>))}</Sec>}
      {notBuilt.length > 0 && <Sec title={`Not built as B-rep (${notBuilt.length})`}>{notBuilt.map((r) => (
        <div key={r.id} className="font-mono text-[10.5px] text-amber-200">{r.name}: <span className="text-slate-400">{r.reason}</span></div>))}</Sec>}
      <Sec title={`Interference (${inter.length})`} open={inter.length > 0}>
        {inter.map((p, i) => (
          <button key={i} onClick={() => { st.selectMany([p.a, p.b]); onPick(p.a); }}
            className="flex w-full justify-between gap-2 rounded px-1 py-0.5 text-left font-mono text-[10.5px] hover:bg-white/5">
            <span className="truncate text-slate-200">{name(p.a)} × {name(p.b)}{p.note ? <span className="text-slate-500"> · {p.note}</span> : ""}</span>
            <span className="shrink-0 text-amber-300">{f3(p.common_mm3)} mm³</span></button>))}
        <p className="mt-1 text-[10px] leading-snug text-slate-500">Common volume of the two exact solids (Boolean). A pin drawn through a plate
          the reading gave no bore shows up here: the drawing does not show that hole, so it is reported, not hidden.</p>
      </Sec>
    </div>
  );
}

function Props({ asm, id }) {
  const caps = useStore((s) => s.caps);
  const r = asm.records[id];
  if (!r) return <div className="mt-3 text-slate-400">Select a part in the tree or the viewport.</div>;
  const v = r.validation || {};
  const g = asm.groups.find((x) => x.parts.includes(id));
  const mates = asm.mates.filter((m) => m.a === id || m.b === id);
  const dims = Object.entries(r.eng?.dims || {});
  return (
    <div className="mt-2 text-[11px]">
      <Sec title="Path [Instances]"><div className="font-mono text-[10.5px] leading-relaxed text-slate-300">AETHER_ASSEMBLY<br />
        &nbsp;&nbsp;{g?.name}<br />&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-cyan-glow">{r.name}</span></div></Sec>
      <Sec title="Geometry">
        <Row k="Built as" v={r.built ? r.exact : "not built"} cls={r.built ? "text-slate-200" : "text-amber-300"} />
        {!r.built && <Row k="Why" v={r.reason} cls="text-amber-200" />}
        {r.gear && <><Row k="Teeth / module" v={`${r.gear.teeth} / ${r.gear.module} mm`} /><Row k="Pitch / tip / root Ø" v={`${f3(2 * r.gear.pitch_radius)} / ${f3(2 * r.gear.tip_radius)} / ${f3(2 * r.gear.root_radius)} mm`} /></>}
        {r.circles?.length > 0 && <Row k="Exact circles" v={r.circles.map((c) => `${c.hole ? "bore " : ""}Ø${(2 * c.radius).toFixed(2)}`).join(", ")} />}
      </Sec>
      {r.built && <Sec title="Validation properties">
        <Row k="BRepCheck" v={v.brepcheck_valid ? "valid" : "INVALID"} cls={v.brepcheck_valid ? "text-emerald-300" : "text-rose-400"} />
        <Row k="Solids / shells / faces / edges" v={`${v.solids} / ${v.shells} / ${v.faces} / ${v.edges}`} />
        <Row k="Free edges (closed solid = 0)" v={v.free_edges} cls={v.free_edges ? "text-rose-300" : "text-emerald-300"} />
        <Row k="Orientation (far point outside)" v={String(v.far_point_outside)} />
        <Row k="Max tolerance" v={`${v.max_tolerance_mm} mm`} />
      </Sec>}
      {r.built && <Sec title="Mass properties (exact B-rep, model mm)">
        <Row k="Centroid" v={(v.centre_mm || []).map((x) => x.toFixed(3)).join(", ") + " mm"} />
        <Row k="Area" v={`${f3(v.area_mm2)} mm²`} />
        <Row k="Volume" v={`${f3(v.volume_mm3)} mm³`} />
        <Row k="Bounding box" v={v.bbox_mm ? `${(v.bbox_mm[3] - v.bbox_mm[0]).toFixed(2)} × ${(v.bbox_mm[4] - v.bbox_mm[1]).toFixed(2)} × ${(v.bbox_mm[5] - v.bbox_mm[2]).toFixed(2)} mm` : "-"} />
        {caps[id] && <Row k="Section area (current cut)" v={`${f3(caps[id].area_mm2)} mm²`} cls="text-fuchsia-300" />}
      </Sec>}
      {dims.length > 0 && <Sec title="Where each size comes from">{dims.map(([k, [val, src]]) => (
        <Row key={k} k={k.replace(/_/g, " ")} v={`${Array.isArray(val) ? val.join(" × ") : val} · ${src}`}
          cls={/assumed|guess|added|typical/i.test(src) ? "text-amber-200" : /read|traced|measured/i.test(src) ? "text-emerald-200" : "text-slate-200"} />))}</Sec>}
      {r.eng?.reason && <Sec title="Inferred by Muse Wonder"><div className="rounded border border-amber-300/25 bg-amber-300/5 px-2 py-1 text-amber-100">{r.eng.reason}
        <div className="mt-0.5 text-[10px] text-amber-300/80">Not on the drawing: added because the machine needs it.</div></div></Sec>}
      <Sec title={`Mates (${mates.length})`}>{mates.map((m, i) => (
        <div key={i} className="font-mono text-[10.5px]"><span className={m.satisfied ? "text-emerald-300" : "text-rose-400"}>{m.satisfied ? "✓" : "✕"}</span> {m.type} ↔ {asm.records[m.a === id ? m.b : m.a]?.name}
          <div className="pl-3 text-[9.5px] text-slate-500">{m.check}</div></div>))}</Sec>
    </div>
  );
}

function Step({ asm }) {
  const st = useStore();
  const busy = useStore((s) => s.busy.step);
  const s = asm.step;
  const rows = s ? Object.entries(s.components) : [];
  useEffect(() => {                                    // the round trip runs in the background: follow it while shown
    if (s?.roundtrip !== "running") return;
    const id = setInterval(() => useStore.getState().loadAsm(), 4000);
    return () => clearInterval(id);
  }, [s?.roundtrip]);
  return (
    <div className="mt-2 text-[11px]">
      <button className="btn w-full justify-center" disabled={busy || !!asm.stale} onClick={() => st.exportStep()}>
        <Icon name="upload" />{busy ? "Writing STEP and re-reading it in a fresh process…" : "Validate & export STEP (AP214)"}</button>
      {asm.stale && <div className="mt-1 text-amber-300">Stale: {asm.stale}. Rebuild the B-rep first.</div>}
      {s && <>
        <div className="mt-2 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-2">
          <Row k="Solids written" v={s.parts} />
          <Row k="Round trip (re-read in a fresh process)" v={s.roundtrip === "running" ? "verifying…" : s.roundtrip_all_pass ? "PASS" : "FAIL"}
            cls={s.roundtrip === "running" ? "text-amber-300" : s.roundtrip_all_pass ? "text-emerald-300" : "text-rose-400"} />
          {s.error && <Row k="Round-trip error" v={s.error} cls="text-rose-300" />}
          <Row k="Missing after re-read" v={s.missing.length ? s.missing.join(", ") : "none"} />
          <Row k="File" v={`${(s.bytes / 1024).toFixed(0)} KB · written in ${s.write_seconds} s${s.seconds != null ? ` · verified in ${s.seconds} s` : ""}`} />
          <a className="btn mt-2 w-full justify-center !py-1" href="/api/asm/export.step" download="aether-assembly.step">Download aether-assembly.step</a>
          <div className="mt-1 text-[10px] text-slate-500">Assembly tree inside: AETHER_ASSEMBLY → sub-assemblies → named, coloured parts. Opens in any
            STEP reader (OpenCascade CAD Assistant, FreeCAD, SolidWorks, Fusion).</div>
        </div>
        {s.left_out.length > 0 && <Sec title={`Left out of the STEP (${s.left_out.length})`}>{s.left_out.map((x) => (
          <div key={x.id} className="font-mono text-[10.5px] text-amber-200">{x.name}: <span className="text-slate-400">{x.why}</span></div>))}</Sec>}
        <Sec title="Per part: original vs re-imported" open={false}>
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-2 font-mono text-[9.5px]">
            <span className="text-slate-500">part</span><span className="text-slate-500">Δvol</span><span className="text-slate-500">max dist</span><span className="text-slate-500" />
            {rows.map(([id, c]) => [
              <span key={id + "n"} className="truncate text-slate-300">{asm.records[id]?.name || id}</span>,
              <span key={id + "v"}>{c.volume_rel_diff?.toExponential(1)}</span>,
              <span key={id + "d"}>{c.dist_orig_to_reimport_mm ? c.dist_orig_to_reimport_mm.max.toExponential(1) : "-"}</span>,
              <span key={id + "p"} className={c.pass ? "text-emerald-300" : "text-rose-400"}>{c.pass ? "✓" : "✕"}</span>])}
          </div>
        </Sec>
      </>}
    </div>
  );
}

export default function AssemblyPanel() {
  const open = useStore((s) => s.panels.asm);
  const asm = useStore((s) => s.asm);
  const busy = useStore((s) => s.busy.asm);
  const active = useStore((s) => s.state?.selected);
  const hasMachine = useStore((s) => (s.state?.parts || []).some((p) => p.eng));
  const st = useStore();
  const [tab, setTab] = useState("tree");
  useEffect(() => { if (open) st.loadAsm(); }, [open]);   // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (id) => { st.select(id); setTab("props"); };
  const s = asm?.summary;
  const lay = useLayout();
  const style = { left: lay.toolLeft + 56, top: L.top, bottom: L.bottom + 12, width: 390 };

  return (<>
    <PanelIcon id="asm" title="B-rep assembly" icon="cube" style={{ left: lay.toolLeft + 56, top: L.top }} busy={busy} />
    <FloatPanel id="asm" title="B-rep assembly · OpenCascade" icon="cube" open={open} busy={busy} onClose={() => st.setPanel("asm", false)} style={style}>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3.5 pb-3 text-[12px]">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
          <button className="btn w-full justify-center" disabled={busy || !hasMachine} onClick={() => st.buildAsm()}>
            <Icon name="cube" />{busy ? "Building exact solids, checking every pair…" : asm ? "Rebuild B-rep assembly" : "Build B-rep assembly"}</button>
          {!hasMachine && <div className="mt-1 text-[10.5px] text-slate-400">Build a machine from a drawing first: its parts become exact solids here.</div>}
          {asm?.stale && <div className="mt-1 text-[10.5px] text-amber-300">Stale: {asm.stale}. The checks below are of the last build.</div>}
          {s && <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[10.5px]">
            <span>solids <span className={s.invalid_solids ? "text-rose-300" : "text-emerald-300"}>{s.valid_solids}/{s.built} valid</span></span>
            <span>mates <span className={s.mates_satisfied < s.mates ? "text-amber-300" : "text-emerald-300"}>{s.mates_satisfied}/{s.mates} ok</span></span>
            <span>exact circles <span className="text-cyan-glow">{s.exact_circles}</span></span>
            <span>interference <span className={s.interferences ? "text-amber-300" : "text-emerald-300"}>{s.interferences}</span></span>
            {s.not_built > 0 && <span className="col-span-2 text-amber-300">{s.not_built} part(s) have no exact B-rep (listed in Checks)</span>}
            <span className="col-span-2 text-slate-500">built {asm.built_at} · {s.seconds.total} s</span>
          </div>}
        </div>
        {asm && <>
          <div className="mt-2 flex gap-1">
            {[["tree", "Assembly"], ["mates", "Mates"], ["checks", "Checks"], ["props", "Properties"], ["step", "STEP"]].map(([k, t]) =>
              <button key={k} onClick={() => setTab(k)} className={`btn !px-2 !py-0.5 text-[11px] ${tab === k ? "!border-cyan-glow/50 text-cyan-glow" : ""}`}>{t}</button>)}
          </div>
          {tab === "tree" && <Tree asm={asm} sel={active} onPick={pick} />}
          {tab === "mates" && <Mates asm={asm} onPick={pick} />}
          {tab === "checks" && <Checks asm={asm} onPick={pick} />}
          {tab === "props" && <Props asm={asm} id={active} />}
          {tab === "step" && <Step asm={asm} />}
        </>}
      </div>
    </FloatPanel>
  </>);
}
