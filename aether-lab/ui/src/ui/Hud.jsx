import { selectedPart, useStore } from "../store";

export default function Hud() {
  const p = useStore(selectedPart);
  const r = useStore((s) => s.results);
  const mode = useStore((s) => s.mode);
  const gizmo = useStore((s) => s.gizmo);
  const axis = useStore((s) => s.axis);
  const toast = useStore((s) => s.toast);
  const sweep = r.sweep;
  const inZone = r.window ? !r.window.outside_sharp_zone : null;
  const items = [
    ["selected", p ? p.name : "—"],
    ["tool", mode === "hand" ? "hands" : `${gizmo}${axis ? " · " + axis.toUpperCase() : ""}`],
    ["focus", sweep ? `${sweep.depths[sweep.i]} mm` : r.recon ? `${r.recon.z} mm` : "—"],
    ["window law", r.window ? `${r.window.visible_pct}%` : "—"],
    ["sharp zone", inZone === null ? "±100 mm" : inZone ? "inside" : "exceeded"],
  ];
  return (
    <>
      <div className="pointer-events-none absolute left-1/2 top-[72px] z-20 flex -translate-x-1/2 items-center gap-5 rounded-2xl border border-line bg-black/35 px-5 py-2 backdrop-blur-xl">
        {items.map(([k, v]) => (
          <div key={k} className="leading-tight"><div className="label">{k}</div>
            <div className={`readout ${k === "sharp zone" && inZone === false ? "text-warn" : k === "sharp zone" && inZone ? "text-ok" : ""}`}>{v}</div></div>
        ))}
      </div>
      {toast && (
        <div className={`pointer-events-none absolute left-1/2 top-[128px] z-40 -translate-x-1/2 rounded-xl border px-4 py-2 text-[12.5px] backdrop-blur-xl animate-floatin ${toast.kind === "error" ? "border-bad/40 bg-bad/15 text-rose-100" : "border-cyan-glow/30 bg-cyan-glow/10 text-cyan-50"}`}>{toast.text}</div>
      )}
    </>
  );
}
