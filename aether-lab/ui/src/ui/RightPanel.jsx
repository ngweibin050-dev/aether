import { useEffect, useState } from "react";
import { selectedPart, useStore } from "../store";
import Icon from "./Icon";

function Num({ value, onCommit, step = 1, className = "" }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  const commit = () => { const n = parseFloat(v); if (!Number.isNaN(n) && n !== value) onCommit(n); else setV(value); };
  return <input className={`field ${className}`} value={v} step={step} type="number"
    onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && e.target.blur()} />;
}

function Vec({ label, value, onCommit }) {
  return (
    <div>
      <div className="label mb-1">{label}</div>
      <div className="grid grid-cols-3 gap-1.5">
        {["x", "y", "z"].map((a, i) => (
          <div key={a} className="relative">
            <span className={`absolute left-2 top-1/2 -translate-y-1/2 font-mono text-[10px] ${["text-rose-400", "text-emerald-400", "text-sky-400"][i]}`}>{a}</span>
            <Num className="pl-5" value={+(value[i] ?? 0).toFixed(2)} onCommit={(n) => { const v = [...value]; v[i] = n; onCommit(v); }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Section({ title, children, right }) {
  return (
    <section className="space-y-2.5 border-b border-line px-4 py-3.5 last:border-0">
      <div className="flex items-center justify-between"><div className="label">{title}</div>{right}</div>
      {children}
    </section>
  );
}

function Bar({ pct }) {
  const c = pct >= 80 ? "#5eead4" : pct >= 65 ? "#fbbf77" : "#fb7185";
  return (
    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
      <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${pct}%`, background: c, boxShadow: `0 0 10px ${c}66` }} />
    </div>
  );
}

function ObjectTab() {
  const p = useStore(selectedPart);
  const tool = useStore((s) => s.tool);
  if (!p) return <div className="px-4 py-6 text-[12.5px] text-slate-400">Select a part in the scene or the outliner. Or ask AETHER to build something.</div>;
  const up = (args) => tool("update_part", { id: p.id, ...args });
  return (
    <>
      <Section title="Part" right={<button className="text-slate-400 hover:text-bad" title="Delete" onClick={() => tool("delete_part", { id: p.id })}><Icon name="trash" /></button>}>
        <input className="field font-sans text-[13px]" defaultValue={p.name} key={p.id + p.name}
          onBlur={(e) => e.target.value !== p.name && up({ name: e.target.value })} />
        <div className="font-mono text-[11px] text-slate-500">{p.type} · {p.id}</div>
      </Section>
      <Section title="Transform · mm / deg">
        <Vec label="Position" value={p.position} onCommit={(v) => up({ position: v })} />
        <Vec label="Rotation" value={p.rotation} onCommit={(v) => up({ rotation: v })} />
        <Vec label="Scale" value={p.scale} onCommit={(v) => up({ scale: v })} />
      </Section>
      {p.type !== "group" && p.type !== "mesh" && (
        <Section title="Parameters">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(p.params).filter(([, v]) => typeof v === "number").map(([k, v]) => (
              <label key={k} className="space-y-1"><div className="font-mono text-[10.5px] text-slate-400">{k}</div>
                <Num value={v} onCommit={(n) => up({ params: { [k]: n } })} /></label>
            ))}
          </div>
        </Section>
      )}
      <Section title="Optical brightness">
        <div className="flex items-center gap-3">
          <input type="range" min="0.1" max="1" step="0.05" defaultValue={p.brightness ?? 1} key={p.id}
            className="flex-1" onChange={(e) => (e.target.dataset.v = e.target.value)}
            onMouseUp={(e) => up({ brightness: +e.target.value })} />
          <span className="readout w-10 text-right">{(p.brightness ?? 1).toFixed(2)}</span>
        </div>
        <p className="text-[11px] text-slate-500">Monochrome laser light: brightness sets how much light this part's surface gets in the hologram.</p>
      </Section>
    </>
  );
}

function OpticsTab() {
  const s = useStore((x) => x.state);
  const r = useStore((x) => x.results);
  const busy = useStore((x) => x.busy);
  const tool = useStore((x) => x.tool);
  const [eyeX, setEyeX] = useState(0);
  const [k, setK] = useState(3);
  const d = s.display;
  const set = (args) => tool("set_display", args);
  return (
    <>
      <Section title="Lab hologram (full wave simulation)">
        <div className="grid grid-cols-2 gap-2">
          {[["pitch_um", "pixel µm"], ["wavelength_nm", "λ nm"], ["samples", "pixels/side"], ["distance_mm", "distance mm"]].map(([kk, l]) => (
            <label key={kk} className="space-y-1"><div className="font-mono text-[10.5px] text-slate-400">{l}</div>
              <Num value={d[kk]} onCommit={(n) => set({ [kk]: n })} /></label>
          ))}
          <label className="space-y-1"><div className="font-mono text-[10.5px] text-slate-400">surface points</div>
            <Num value={s.points} onCommit={(n) => set({ points: n })} /></label>
          <label className="space-y-1"><div className="font-mono text-[10.5px] text-slate-400">method</div>
            <select className="field" value={s.method} onChange={(e) => set({ method: e.target.value })}>
              <option value="wrp">WRP (fast, exact)</option><option value="points">direct points</option><option value="layers">layers (approx)</option>
            </select></label>
        </div>
        <div className="flex gap-2 pt-1">
          <button className="btn-primary flex-1" disabled={busy.make_hologram} onClick={() => tool("make_hologram").then(() => tool("propagate"))}>
            <Icon name="wave" />Calculate</button>
          <button className="btn flex-1" disabled={busy.focus_sweep} onClick={() => tool("focus_sweep", { steps: 9 })}>Focus sweep</button>
        </div>
        {r.hologram && <div className="font-mono text-[11px] text-slate-400">{r.hologram.info.points_used} visible points · scale ×{r.hologram.info.lab_scale} · {r.hologram.info.compute}</div>}
      </Section>
      <Section title="Eye view · parallax & Window Law">
        <div className="flex items-center gap-3"><span className="label w-14">eye x</span>
          <input type="range" min="-80" max="80" value={eyeX} onChange={(e) => setEyeX(+e.target.value)} className="flex-1" />
          <span className="readout w-14 text-right">{eyeX} mm</span></div>
        <button className="btn w-full" disabled={busy.eye_view} onClick={() => tool("eye_view", { eye_x_mm: eyeX })}><Icon name="eye" />Look from here</button>
      </Section>
      <Section title="Speckle · v11 sparse point groups">
        <div className="flex items-center gap-2"><span className="label">k</span>
          {[2, 3, 4].map((v) => <button key={v} className={`tab ${k === v ? "tab-on" : ""}`} onClick={() => setK(v)}>{v}×{v}</button>)}</div>
        <button className="btn w-full" disabled={busy.speckle_compare} onClick={() => tool("speckle_compare", { k })}>Compare speckle</button>
        {r.speckle?.imgs && (
          <div className="space-y-2">
            <div className="grid grid-cols-3 gap-1.5">
              {[["speckle_one", "1 frame", r.speckle.one_frame], ["speckle_random", `${r.speckle.frames} random`, r.speckle.random_avg], ["speckle_groups", `${r.speckle.k}×${r.speckle.k} groups`, r.speckle.sparse_groups]].map(([key, l, c]) => (
                <figure key={key}><img src={r.speckle.imgs[key]} className="aspect-square w-full rounded-lg border border-line object-cover" />
                  <figcaption className="mt-1 text-center text-[10.5px] text-slate-400">{l}<br /><span className="readout">C = {c}</span></figcaption></figure>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">C = std/mean of brightness. Visible above ~0.04. Eye blur spot {r.speckle.eye_blur_spot_um} µm.</p>
          </div>
        )}
      </Section>
    </>
  );
}

function DeskTab() {
  const s = useStore((x) => x.state);
  const r = useStore((x) => x.results);
  const busy = useStore((x) => x.busy);
  const tool = useStore((x) => x.tool);
  return (
    <>
      <Section title="AETHER Desk · 27″, viewer 70 cm">
        <div className="grid grid-cols-3 gap-2 text-center">
          {[["panel", `${s.desk.panel_w_mm}×${s.desk.panel_h_mm}`], ["columns", `${s.desk.column_width_um} µm`], ["eye box", r.desk ? `${r.desk.eye_box_mm} mm` : "—"]].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-line bg-white/[0.03] px-2 py-2"><div className="label">{k}</div><div className="readout mt-0.5">{v}</div></div>
          ))}
        </div>
        <button className="btn w-full" disabled={busy.desk_check} onClick={() => tool("desk_check")}>Run sharpness check</button>
        {r.desk && (
          <div className="space-y-1.5">
            {r.desk.rows.map((x) => (
              <div key={x.height_cm} className="flex items-center gap-3">
                <span className="readout w-12 text-slate-400">{x.height_cm > 0 ? "+" : ""}{x.height_cm} cm</span>
                <Bar pct={x.sharpness_vs_full_hologram_pct} />
                <span className="readout w-12 text-right">{x.sharpness_vs_full_hologram_pct}%</span>
              </div>
            ))}
            <p className="text-[11px] text-slate-500">Sharpness vs a perfect full hologram. Eye-model simulation, not a measurement.</p>
          </div>
        )}
      </Section>
      <Section title="Window Law · can the eye see it?">
        <button className="btn w-full" disabled={busy.window_check} onClick={() => tool("window_check")}>Check visibility</button>
        {r.window && (
          <div className="space-y-1.5">
            <div className="flex items-baseline justify-between"><span className="text-[12px] text-slate-300">Visible through panel</span><span className="readout text-[15px]">{r.window.visible_pct}%</span></div>
            {r.window.parts.slice(0, 12).map((x) => (
              <div key={x.part} className="flex items-center gap-3"><span className="w-24 truncate text-[11.5px] text-slate-400">{x.part}</span><Bar pct={x.visible_pct} /><span className="readout w-11 text-right">{x.visible_pct}%</span></div>
            ))}
            {r.window.outside_sharp_zone && <p className="text-[11px] text-warn">Part of the design leaves the ±100 mm sharp zone.</p>}
          </div>
        )}
      </Section>
      <Section title="Hand occlusion (v13 rule)">
        <button className="btn w-full" disabled={busy.hand_check} onClick={() => tool("hand_check")}>Check tracked hand</button>
        {r.hand && (r.hand.hand_points ? (
          <div className="text-[12px] text-slate-300">Depth conflicts <span className="readout">{r.hand.depth_conflict_pct}%</span> · natural <span className="readout">{r.hand.naturally_hidden_pct}%</span>
            <p className="mt-1 text-[11px] text-slate-500">{r.hand.advice}</p></div>
        ) : <p className="text-[11.5px] text-slate-500">Switch to Hand mode so the camera can track your hand.</p>)}
      </Section>
      <Section title="Design search">
        <button className="btn w-full" disabled={busy.search_column_width} onClick={() => tool("search_column_width", { height_cm: 10, min_sharpness_pct: 80 })}>Widest column for 80% at 10 cm</button>
        {r.search && <div className="flex flex-wrap gap-1.5">{r.search.tried.map((t) => (
          <span key={t.column_width_um} className={`rounded-md border px-2 py-0.5 font-mono text-[11px] ${t.passes ? "border-ok/40 text-ok" : "border-bad/30 text-bad"}`}>{t.column_width_um} µm</span>))}
          <div className="w-full text-[12px] text-slate-300">Best: <span className="readout">{r.search.largest_column_width_um} µm</span></div></div>}
      </Section>
    </>
  );
}

export default function RightPanel() {
  const open = useStore((s) => s.panels.right);
  const setPanel = useStore((s) => s.setPanel);
  const tab = useStore((s) => s.rightTab);
  const setTab = useStore((s) => s.setTab);
  if (!open)
    return <button onClick={() => setPanel("right", true)} className="glass pointer-events-auto absolute right-4 top-20 z-20 p-2.5" title="Properties"><Icon name="panel" /></button>;
  return (
    <aside className="glass pointer-events-auto absolute bottom-24 right-4 top-20 z-20 flex w-[330px] flex-col animate-floatin">
      <div className="flex items-center gap-1 p-2">
        {[["object", "Object"], ["optics", "Optics"], ["desk", "Desk"]].map(([k, l]) => (
          <button key={k} className={`tab ${tab === k ? "tab-on" : ""}`} onClick={() => setTab(k)}>{l}</button>))}
        <button className="btn-icon ml-1" onClick={() => setPanel("right", false)} title="Collapse"><Icon name="panel" /></button>
      </div>
      <div className="scroll-thin flex-1 overflow-y-auto">
        {tab === "object" ? <ObjectTab /> : tab === "optics" ? <OpticsTab /> : <DeskTab />}
      </div>
    </aside>
  );
}
