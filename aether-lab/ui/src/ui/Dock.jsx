import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { HEAVY, useStore } from "../store";
import { run } from "../commands";
import { sceneBox } from "../scene/Viewport";
import Icon from "./Icon";
import { Slider } from "./Charts";

const AXI = { x: "x", y: "y", z: "z" };

function DockButton({ icon, label, onClick, on, busy, title, wide }) {
  return (
    <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.94 }} title={title} onClick={onClick}
      className={`relative flex h-11 items-center gap-2 whitespace-nowrap rounded-xl px-3 text-[12px] font-medium transition ${wide ? "pr-3.5" : ""}
        ${on ? "bg-cyan-glow/15 text-cyan-50 shadow-inner" : "text-white/80 hover:bg-white/[0.07] hover:text-white hover:shadow-inner"}`}>
      <Icon name={icon} className={`h-[18px] w-[18px] ${on ? "text-cyan-glow" : ""}`} />{label && <span>{label}</span>}
      {busy && <span className="absolute inset-x-2 bottom-1 h-[2px] overflow-hidden rounded-full bg-white/10"><i className="absolute top-0 block h-full w-1/3 animate-sweep bg-cyan-glow shadow-glow" /></span>}
    </motion.button>
  );
}

function SectionPop() {
  const v = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  const [range, setRange] = useState([-100, 100]);
  useEffect(() => {
    const b = sceneBox();
    if (!b.isEmpty() && v.section) setRange([Math.floor(b.min[AXI[v.section]] - 2), Math.ceil(b.max[AXI[v.section]] + 2)]);
  }, [v.section]);
  return (
    <div className="w-72 space-y-3 p-3">
      <div className="flex items-center justify-between"><span className="label">Section cut</span>
        <span className="font-mono text-[10.5px] text-magenta-glow">{v.section ? `${v.section.toUpperCase()} = ${v.section_mm.toFixed(1)} mm` : "off"}</span></div>
      <div className="grid grid-cols-4 gap-1">
        {["x", "y", "z"].map((a) => <button key={a} onClick={() => run("in.sec" + a)}
          className={`btn py-1 font-mono ${v.section === a ? "!border-magenta-glow/60 !bg-magenta-glow/15 text-white" : ""}`}>{a.toUpperCase()}</button>)}
        <button className="btn py-1" onClick={() => setView({ section: null }, { now: true })}>Off</button>
      </div>
      {v.section && <>
        <Slider value={v.section_mm} min={range[0]} max={range[1]} accent="#ff4fd8" onChange={(x) => setView({ section_mm: +x.toFixed(1) })} />
        <button className="btn w-full" onClick={() => run("in.flip")}><Icon name="flip" />Keep the other side</button>
      </>}
      <p className="text-[10.5px] leading-snug text-silver">Cut faces glow magenta. The hologram is computed from the cut design. The desk viewer looks down from 70 cm, so a Z cut opens the inside to the eye.</p>
    </div>
  );
}

function ExplodePop() {
  const v = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  return (
    <div className="w-72 space-y-3 p-3">
      <div className="flex items-center justify-between"><span className="label">Exploded view</span><span className="readout text-cyan-glow">{Math.round(v.explode * 100)}%</span></div>
      <Slider value={v.explode} min={0} max={1} onChange={(x) => setView({ explode: +x.toFixed(2) })} />
      <div className="grid grid-cols-3 gap-1">
        {[[0, "Assembled"], [0.5, "Half"], [1, "Full"]].map(([x, l]) => <button key={l} className="btn py-1" onClick={() => setView({ explode: x }, { now: true })}>{l}</button>)}
      </div>
      <p className="text-[10.5px] leading-snug text-silver">Shells, rotor and shaft slide apart along the main axis; coils and magnets move outward. Press <span className="kbd">E</span> to toggle.</p>
    </div>
  );
}

export default function Dock() {
  const busy = useStore((s) => s.busy);
  const v = useStore((s) => s.view);
  const dock = useStore((s) => s.dock);
  const setDock = useStore((s) => s.setDock);
  const sel = useStore((s) => s.selection.length);
  const anyBusy = HEAVY.some((h) => busy[h]);
  return (
    <div className="pointer-events-auto absolute bottom-[30px] left-1/2 z-30 -translate-x-1/2">
      <AnimatePresence>
        {dock && (
          <motion.div key={dock} initial={{ opacity: 0, y: 8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }}
            style={{ x: "-50%" }} className="glass-solid absolute bottom-[58px] left-1/2">
            {dock === "section" ? <SectionPop /> : <ExplodePop />}
          </motion.div>
        )}
      </AnimatePresence>
      <div className="glass relative flex items-center gap-0.5 overflow-hidden rounded-[22px] p-1">
        <DockButton icon="holo" label="Calculate hologram" title="Calculate hologram + focus sweep (F12)" busy={busy.make_hologram} onClick={() => run("holo.calc")} wide />
        <DockButton icon="wave" label="Wave propagation" title="Focus sweep through the depth (Ctrl+F12)" busy={busy.focus_sweep} onClick={() => run("holo.prop")} />
        <DockButton icon="eye" title="Eye view through a 4 mm pupil" busy={busy.eye_view} onClick={() => run("holo.eye")} />
        <span className="mx-1 h-6 w-px bg-white/10" />
        <DockButton icon="section" label="Section" title="Section cut (Alt+X / Alt+Y)" on={!!v.section || dock === "section"} onClick={() => setDock("section")} />
        <DockButton icon="explode" label="Explode" title="Exploded view (E)" on={v.explode > 0 || dock === "explode"} onClick={() => setDock("explode")} />
        <DockButton icon="xray" title="X-ray (Alt+Z)" on={v.xray} onClick={() => run("in.xray")} />
        <DockButton icon="isolate" title="Isolate selected (/)" on={v.isolate.length > 0} onClick={() => (sel || v.isolate.length) && run("in.isolate")} />
        <span className="mx-1 h-6 w-px bg-white/10" />
        <DockButton icon="film" label="Export film" title="Export a 2400 dpi print film + predicted wall image" busy={busy.export_film} onClick={() => run("file.film")} />
        {anyBusy && <div className="pointer-events-none absolute inset-0 busy-sheen opacity-70" />}
      </div>
    </div>
  );
}
