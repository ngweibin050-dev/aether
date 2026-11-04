import { useStore } from "../store";
import { run } from "../commands";
import FloatPanel, { PanelIcon } from "./FloatPanel";
import { LineChart } from "./Charts";
import { L, useLayout } from "./layout";

// The optics results of the current design as one lettered figure (a-f), the way a paper shows them. Every panel is a
// result the wave-optics engine computed for THIS model (focus_sweep, desk_score, speckle, window law); nothing here is
// drawn for effect. The AETHER Desk is simulated, not built: the figure says so.

function P({ k, title, children, wide }) {
  return (
    <figure className={`min-w-0 rounded-lg border border-white/10 bg-black/30 p-2 ${wide ? "col-span-2" : ""}`}>
      <figcaption className="mb-1 flex items-baseline gap-1.5"><b className="font-display text-[15px] text-white">{k}</b>
        <span className="text-[11px] text-slate-300">{title}</span></figcaption>
      {children}
    </figure>
  );
}

function ZoneBar({ zone, design }) {
  const lo = Math.min(zone[0], design[0]) - 15, hi = Math.max(zone[1], design[1]) + 15;
  const y = (v) => 8 + (1 - (v - lo) / (hi - lo)) * 124;
  return (
    <svg viewBox="0 0 220 140" className="w-full" style={{ height: 140 }}>
      <rect x="40" y={y(zone[1])} width="50" height={y(zone[0]) - y(zone[1])} fill="#5fe1ff" fillOpacity=".18" stroke="#5fe1ff" />
      <text x="65" y={y(zone[1]) - 3} fontSize="8" fill="#9ff3ff" textAnchor="middle">sharp zone</text>
      <rect x="110" y={y(design[1])} width="50" height={y(design[0]) - y(design[1])} fill="#ff4fd8" fillOpacity=".2" stroke="#ff4fd8" />
      <text x="135" y={y(design[1]) - 3} fontSize="8" fill="#ffb3f0" textAnchor="middle">design</text>
      <line x1="30" x2="175" y1={y(0)} y2={y(0)} stroke="#e5e7eb" strokeDasharray="3 3" />
      <text x="178" y={y(0) + 3} fontSize="8" fill="#cbd5e1">panel</text>
      {[zone[0], zone[1]].map((v) => <text key={v} x="36" y={y(v) + 3} fontSize="8" fill="#9ff3ff" textAnchor="end">{v.toFixed(0)}</text>)}
      {[design[0], design[1]].map((v) => <text key={v} x="164" y={y(v) + 3} fontSize="8" fill="#ffb3f0">{v.toFixed(0)}</text>)}
      <text x="4" y="136" fontSize="8" fill="#7d8796">height above the desk surface (mm)</text>
    </svg>
  );
}

export default function OpticsFigure() {
  const open = useStore((s) => s.panels.optics);
  const r = useStore((s) => s.results);
  const st = useStore();
  const sw = r.sweep, sc = r.score;
  const rows = (sc?.rows || []).slice().sort((a, b) => a.worst_sharpness_pct - b.worst_sharpness_pct).slice(0, 10);
  const lay = useLayout();
  const style = { left: lay.toolLeft + 56, right: lay.navRight + 56, top: L.top, bottom: L.bottom + 12 };
  return (<>
    <PanelIcon id="optics" title="Optics figure" icon="wave" style={{ left: lay.toolLeft + 56, top: L.top + 112 }} />
    <FloatPanel id="optics" title="Computational optics · AETHER Desk (simulated, not built)" icon="wave" open={open} onClose={() => st.setPanel("optics", false)} style={style}>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {!sw && !sc ? <div className="py-4 text-slate-400">No optics results yet. They show how sharply the AETHER Desk (simulated) would display
          the model on the desk: run one on the current model.
          <div className="mt-2 flex gap-2"><button className="btn text-[11.5px]" onClick={() => run("holo.desk")}>Desk sharpness check</button>
            <button className="btn text-[11.5px]" onClick={() => run("holo.prop")}>Focus sweep</button></div></div> :
          <div className="grid grid-cols-2 gap-2 xl:grid-cols-3">
            {sw && <P k="a" title={`What the eye sees at each focus height · ${sw.display} · ${sw.lasers?.join(", ")} nm`} wide>
              <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${sw.imgs.length}, minmax(0, 1fr))` }}>
                {sw.imgs.map((src, i) => (
                  <div key={i} className="relative"><img src={src} alt={`eye focused at ${sw.depths[i]} mm`} className="aspect-square w-full rounded bg-black object-cover" />
                    <span className="absolute bottom-0.5 left-1 font-mono text-[9px] text-white/90">z = {Math.round(sw.depths[i])} mm</span></div>))}
              </div>
            </P>}
            {sw && <P k="b" title="Sharpness vs eye focus (% of a full 2D hologram)">
              <LineChart xs={sw.depths} ys={sw.sharp} yMax={100} threshold={80} xLabel="focus height (mm)" fmtX={(v) => Math.round(v)} h={120} />
            </P>}
            {sc && <P k="c" title="Viewing zone: where the desk is ≥ 80 % sharp vs the design's depth">
              <ZoneBar zone={sc.sharp_zone_mm} design={sc.design_z_mm} />
            </P>}
            {sc && <P k="d" title={`Worst-case sharpness per part (lowest 10 of ${sc.parts}) · target ${sc.target_pct} %`}>
              <div className="space-y-0.5">
                {rows.map((x) => (
                  <div key={x.id} className="flex items-center gap-1.5 font-mono text-[9.5px]">
                    <span className="w-24 truncate text-slate-300">{x.part}</span>
                    <span className="relative h-2 flex-1 rounded bg-white/10"><i className="absolute inset-y-0 left-0 rounded" style={{ width: `${x.worst_sharpness_pct}%`, background: x.ok ? "#34d399" : "#fb7185" }} />
                      <i className="absolute inset-y-[-2px] w-px bg-fuchsia-400" style={{ left: `${sc.target_pct}%` }} /></span>
                    <span className="w-9 text-right text-slate-200">{x.worst_sharpness_pct}</span>
                  </div>))}
              </div>
            </P>}
            {sw?.inFocus && <P k="e" title="Share of the design inside the eye's depth of field (±0.25 D)">
              <LineChart xs={sw.depths} ys={sw.inFocus} yMax={100} color="#a78bfa" xLabel="focus height (mm)" fmtX={(v) => Math.round(v)} h={120} />
            </P>}
            <P k="f" title="Summary">
              <div className="space-y-0.5 font-mono text-[10.5px] text-slate-200">
                {sc && <div>parts ≥ {sc.target_pct} %: <b className={sc.pass ? "text-emerald-300" : "text-rose-300"}>{sc.parts_ok}/{sc.parts}</b> (worst {sc.min_sharpness_pct} %)</div>}
                {sc && <div>sharp zone: {sc.sharp_zone_mm[0]} … +{sc.sharp_zone_mm[1]} mm · design {sc.design_z_mm[0]} … {sc.design_z_mm[1]} mm</div>}
                {sw?.speckle != null && <div>speckle contrast: {sw.speckle} %</div>}
                {sw?.outside != null && <div>parts outside the window (Window Law): {sw.outside} %</div>}
                <div className="pt-1 text-[10px] leading-snug text-amber-200/90">Wave-optics simulation of a display we are designing. The AETHER Desk has not been built:
                  these are predictions, not measurements.</div>
              </div>
            </P>
          </div>}
      </div>
    </FloatPanel>
  </>);
}
