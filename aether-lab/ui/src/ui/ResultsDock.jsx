import { useStore } from "../store";
import Icon from "./Icon";

function Card({ title, sub, busy, children, w = "w-[200px]" }) {
  return (
    <div className={`glass relative overflow-hidden p-2.5 ${w}`}>
      <div className="mb-2 flex items-baseline justify-between px-0.5">
        <span className="font-display text-[12.5px] font-semibold">{title}</span>
        {sub && <span className="font-mono text-[10.5px] text-cyan-glow">{sub}</span>}
      </div>
      {children}
      {busy && <div className="busy-sheen pointer-events-none absolute inset-0" />}
    </div>
  );
}

const Empty = ({ text }) => <div className="flex aspect-square items-center justify-center rounded-xl border border-dashed border-line text-center text-[11px] text-slate-500 px-3">{text}</div>;

export default function ResultsDock() {
  const r = useStore((s) => s.results);
  const busy = useStore((s) => s.busy);
  const open = useStore((s) => s.panels.results);
  const setPanel = useStore((s) => s.setPanel);
  const sweep = r.sweep;
  const set = (i) => useStore.setState((s) => ({ results: { ...s.results, sweep: { ...s.results.sweep, i } } }));
  if (!open)
    return <button className="glass pointer-events-auto absolute right-[350px] top-[140px] z-20 px-3 py-1.5 text-[12px]" onClick={() => setPanel("results", true)}>Light preview</button>;
  const reconImg = sweep ? sweep.imgs[sweep.i] : r.recon?.img;
  return (
    <div className="scroll-thin pointer-events-auto absolute bottom-24 right-[350px] top-[140px] z-20 flex flex-col items-end gap-3 overflow-y-auto pr-1 animate-floatin">
      <button className="flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-white" onClick={() => setPanel("results", false)}><span className="label">Light preview</span><Icon name="close" className="h-3.5 w-3.5" /></button>
      <Card title="Hologram" sub={r.hologram ? `${r.hologram.info.hologram_px}² px` : ""} busy={busy.make_hologram} w="w-[200px]">
        {r.hologram ? <img src={r.hologram.img} className="aspect-square w-full rounded-xl object-cover" /> : <Empty text="Press Enter to calculate" />}
      </Card>
      <Card title="What the eye focuses on" sub={sweep ? `${sweep.depths[sweep.i]} mm` : r.recon ? `${r.recon.z} mm` : ""} busy={busy.propagate || busy.focus_sweep} w="w-[200px]">
        {reconImg ? <img src={reconImg} className="aspect-square w-full rounded-xl object-cover" /> : <Empty text="Reconstruction" />}
        {sweep && (
          <div className="mt-2 space-y-1.5">
            <input type="range" min="0" max={sweep.imgs.length - 1} value={sweep.i} onChange={(e) => set(+e.target.value)} className="w-full" />
            <div className="flex h-6 items-end gap-[3px]">
              {sweep.sharp.map((v, k) => <i key={k} onClick={() => set(k)} className={`flex-1 cursor-pointer rounded-t-sm transition ${k === sweep.i ? "bg-cyan-glow shadow-glow" : "bg-cyan-glow/25"}`}
                style={{ height: `${Math.max(8, v / Math.max(...sweep.sharp, 1) * 100)}%` }} />)}
            </div>
            <div className="flex justify-between font-mono text-[10px] text-slate-500"><span>near panel</span><span>{sweep.sharp[sweep.i]}% sharp</span><span>toward eye</span></div>
          </div>
        )}
      </Card>
      <Card title="Eye view" sub={r.eye ? `x ${r.eye.info.eye_mm[0]} mm` : ""} busy={busy.eye_view} w="w-[200px]">
        {r.eye ? <img src={r.eye.img} className="aspect-square w-full rounded-xl object-cover" /> : <Empty text="Optics ▸ Look from here" />}
      </Card>
    </div>
  );
}
