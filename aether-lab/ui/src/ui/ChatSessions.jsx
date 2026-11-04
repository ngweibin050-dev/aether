import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";
import Icon from "./Icon";

// The project's chats (projects.py chat sessions): several conversations about the same scene. The scene and its
// undo history are shared by all of them; switching only changes the conversation.

export default function ChatSessions() {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState({ chats: [] });
  const [edit, setEdit] = useState(null);
  const busy = useStore((s) => s.busy.chat);
  const project = useStore((s) => s.project?.slug);
  const st = useStore.getState();
  const box = useRef();
  const load = () => fetch("/api/chats").then((r) => r.json()).then(setList).catch(() => {});
  useEffect(() => { load(); }, [project]);
  useEffect(() => {
    if (!open) return;
    load();
    const off = (e) => { if (!box.current?.contains(e.target)) setOpen(false); };
    addEventListener("pointerdown", off);
    return () => removeEventListener("pointerdown", off);
  }, [open]);
  const post = async (path, body) => {
    const r = await fetch(path, { method: "POST", body: JSON.stringify(body || {}) });
    const j = await r.json();
    if (!r.ok) { st.notify(j.error || "failed", "error"); return null; }
    return j;
  };
  const go = async (path, body) => {
    const j = await post(path, body);
    if (j) { st.setChat(j.chat); setList(j); setOpen(false); }
  };
  const cur = list.chats.find((c) => c.current);
  return (
    <div ref={box} className="relative mr-1">
      <button type="button" title="Chats in this project (switch, new, rename)" onClick={() => setOpen((o) => !o)}
        className="flex h-7 max-w-[180px] items-center gap-1.5 rounded-lg border border-white/10 bg-black/30 px-2 text-[11px] text-slate-300 transition hover:text-white">
        <Icon name="sparkle" className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{cur?.title || "Chat"}</span>
        <span className="text-slate-500">▾</span>
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-50 w-72 rounded-xl border border-white/10 bg-[#0b1018]/95 p-1.5 shadow-2xl backdrop-blur">
          <button type="button" disabled={busy} onClick={() => go("/api/chats/new")}
            className="mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-cyan-200 hover:bg-white/[0.06] disabled:opacity-40">
            <Icon name="plus" className="h-3.5 w-3.5" /> New chat</button>
          <div className="scroll-thin max-h-72 overflow-y-auto">
            {list.chats.map((c) => (
              <div key={c.id} className={`group flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] ${c.current ? "bg-white/[0.07] text-white" : "text-slate-300 hover:bg-white/[0.04]"}`}>
                {edit === c.id ? (
                  <input autoFocus defaultValue={c.title} className="min-w-0 flex-1 rounded bg-black/40 px-1 text-[12px] text-white outline-none"
                    onKeyDown={async (e) => {
                      if (e.key === "Enter") { await post("/api/chats/rename", { id: c.id, title: e.target.value }); setEdit(null); load(); }
                      if (e.key === "Escape") setEdit(null);
                    }} onBlur={() => setEdit(null)} />
                ) : (
                  <button type="button" disabled={busy || c.current} onClick={() => go("/api/chats/open", { id: c.id })}
                    className="min-w-0 flex-1 truncate text-left disabled:cursor-default" title={c.title}>{c.title}</button>
                )}
                <span className="shrink-0 font-mono text-[9.5px] text-slate-500">{c.messages}</span>
                <button type="button" title="Rename" onClick={() => setEdit(c.id)}
                  className="shrink-0 text-[11px] text-slate-500 opacity-0 hover:text-white group-hover:opacity-100">✎</button>
                {!c.current && <button type="button" title="Delete this chat"
                  onClick={async () => { if (confirm(`Delete the chat "${c.title}"?`)) { await post("/api/chats/delete", { id: c.id }); load(); } }}
                  className="shrink-0 text-[12px] text-slate-500 opacity-0 hover:text-rose-300 group-hover:opacity-100">×</button>}
              </div>))}
          </div>
          <div className="px-2 pt-1 text-[10px] leading-snug text-slate-500">All chats share this project's scene and undo history.</div>
        </div>
      )}
    </div>
  );
}
