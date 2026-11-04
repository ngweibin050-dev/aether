import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useStore } from "../store";
import Icon from "./Icon";

// The open project and everything about projects: new, open another, rename, and the versions the assistant saved
// after each change (restore any of them; the current scene is saved as a version first, so nothing is lost).
export default function ProjectMenu() {
  const project = useStore((s) => s.project);
  const st = useStore();
  const [open, setOpen] = useState(false);
  const [list, setList] = useState([]);
  const [versions, setVersions] = useState([]);
  const [tab, setTab] = useState("projects");
  const [name, setName] = useState("");
  const projectName = useStore((s) => s.project?.name);
  useEffect(() => {
    if (!open) return;
    fetch("/api/projects").then((r) => r.json()).then((j) => setList(j.projects || [])).catch(() => {});
    fetch("/api/project").then((r) => r.json()).then((j) => setVersions(j.versions || [])).catch(() => {});
    const close = (e) => !e.target.closest?.("[data-projectmenu]") && setOpen(false);
    addEventListener("pointerdown", close);
    return () => removeEventListener("pointerdown", close);
  }, [open, projectName]);
  return (
    <div className="relative" data-projectmenu>
      <button onClick={() => setOpen(!open)} title="Project: switch, create, rename, versions"
        className={`flex max-w-[220px] items-center gap-1.5 rounded-md px-2.5 py-1 text-[12px] transition ${open ? "bg-white/10 text-white" : "text-white/85 hover:text-white"}`}>
        <Icon name="layers" className="h-3.5 w-3.5 shrink-0 text-cyan-glow" />
        <span className="truncate font-semibold">{project?.name || "Project"}</span>
        <Icon name="chevron" className="h-3 w-3 shrink-0 rotate-90 text-silver" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.12 }}
            className="glass-solid absolute left-0 top-9 w-80 p-2 text-[12px]">
            <form className="flex gap-1" onSubmit={async (e) => { e.preventDefault(); if (!name.trim()) return; await st.newProject(name.trim()); setName(""); setOpen(false); }}>
              <input className="field min-w-0 flex-1 !py-1" placeholder="New project name, e.g. CAD car" value={name} onChange={(e) => setName(e.target.value)} />
              <button className="btn !py-1" disabled={!name.trim()}>Create</button>
            </form>
            <div className="mt-2 flex gap-1">
              {[["projects", `Projects ${list.length}`], ["versions", `Versions ${versions.length}`]].map(([k, t]) => (
                <button key={k} onClick={() => setTab(k)} className={`btn !px-2 !py-0.5 text-[11px] ${tab === k ? "!border-cyan-glow/50 text-cyan-glow" : ""}`}>{t}</button>))}
              <button className="btn ml-auto !px-2 !py-0.5 text-[11px]" title="Rename this project"
                onClick={async () => { const n = prompt("Project name", project?.name || ""); if (n?.trim()) await st.renameProject(n.trim()); }}>Rename</button>
            </div>
            <div className="scroll-thin mt-2 max-h-72 space-y-0.5 overflow-y-auto">
              {tab === "projects" && list.map((p) => (
                <button key={p.slug} onClick={async () => { setOpen(false); await st.openProject(p.slug); }}
                  className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left ${p.slug === project?.slug ? "bg-cyan-glow/15 text-white" : "hover:bg-white/5"}`}>
                  <span className="min-w-0 flex-1"><span className="block truncate">{p.name}</span>
                    <span className="font-mono text-[9.5px] text-slate-500">{p.models} model(s) · {p.versions} version(s) · saved {p.saved}</span></span>
                  {p.slug === project?.slug && <span className="font-mono text-[9.5px] text-cyan-glow">open</span>}
                </button>))}
              {tab === "versions" && (versions.length ? versions.map((v) => (
                <div key={v.n} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-white/5">
                  <span className="min-w-0 flex-1"><span className="block truncate">v{v.n} · {v.label}</span>
                    <span className="font-mono text-[9.5px] text-slate-500">{v.t} · {v.models} model(s)</span></span>
                  <button className="btn !px-2 !py-0.5 text-[11px]" title="Restore this version (the current scene is saved as a version first)"
                    onClick={async () => { setOpen(false); await st.restoreVersion(v.n); }}>Restore</button>
                </div>)) : <div className="px-2 py-2 text-slate-400">No versions yet: one is saved after every change the assistant makes.</div>)}
            </div>
            <div className="mt-2 border-t border-white/10 pt-1.5 font-mono text-[9.5px] text-slate-500">
              Saved automatically · output/projects/{project?.slug}</div>
          </motion.div>)}
      </AnimatePresence>
    </div>
  );
}
