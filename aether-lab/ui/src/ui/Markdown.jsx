// A small Markdown renderer for chat replies (no HTML is ever injected: everything becomes React elements).
// Blocks: # headings, - / * / • bullet lists, 1. numbered lists, ``` code fences, paragraphs.
// Inline: **bold**, *italic*, `code`, [text](https://link).

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^)\s]+)\)|\*[^*\s][^*]*\*)/g;

function inline(text, key = "i") {
  const out = [];
  let last = 0, m, n = 0;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    const k = `${key}-${n++}`;
    if (t.startsWith("**")) out.push(<strong key={k} className="font-semibold text-white">{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={k} className="rounded bg-white/10 px-1 font-mono text-[11px] text-cyan-100">{t.slice(1, -1)}</code>);
    else if (t.startsWith("[")) out.push(<a key={k} href={m[2]} target="_blank" rel="noreferrer" className="text-sky-300 underline-offset-2 hover:underline">{t.slice(1, t.indexOf("]"))}</a>);
    else out.push(<em key={k}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text }) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (/^```/.test(ln)) {                                   // code fence
      const body = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) body.push(lines[i++]);
      i++;
      blocks.push(<pre key={blocks.length} className="scroll-thin overflow-x-auto rounded-lg bg-black/40 p-2 font-mono text-[11px] text-slate-200">{body.join("\n")}</pre>);
      continue;
    }
    const h = ln.match(/^(#{1,3})\s+(.*)/);
    if (h) {
      blocks.push(<div key={blocks.length} className={`font-display font-semibold text-white ${h[1].length === 1 ? "text-[14px]" : "text-[13px]"}`}>{inline(h[2], "h" + i)}</div>);
      i++;
      continue;
    }
    if (/^\s*([-*•])\s+/.test(ln) || /^\s*\d+[.)]\s+/.test(ln)) {   // a list: consecutive items
      const ordered = /^\s*\d+[.)]\s+/.test(ln);
      const items = [];
      while (i < lines.length && (ordered ? /^\s*\d+[.)]\s+/ : /^\s*([-*•])\s+/).test(lines[i])) {
        items.push(lines[i].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*([-*•])\s+/, ""));
        i++;
      }
      const L = ordered ? "ol" : "ul";
      blocks.push(<L key={blocks.length} className={`ml-4 space-y-0.5 ${ordered ? "list-decimal" : "list-disc"} marker:text-slate-500`}>
        {items.map((t, k) => <li key={k}>{inline(t, `l${i}-${k}`)}</li>)}</L>);
      continue;
    }
    if (!ln.trim()) { i++; continue; }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,3}\s|\s*([-*•])\s+|\s*\d+[.)]\s+)/.test(lines[i])) para.push(lines[i++]);
    blocks.push(<p key={blocks.length}>{para.flatMap((p, k) => (k ? [<br key={"b" + k} />, ...inline(p, `p${i}-${k}`)] : inline(p, `p${i}-${k}`)))}</p>);
  }
  return <div className="space-y-1.5">{blocks}</div>;
}
