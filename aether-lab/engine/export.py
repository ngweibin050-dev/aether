"""The one-page build report (report_html). Scene STL / GLB export (mesh parts) was removed in Phase A: engineering
export is STEP written by the CAD worker from validated B-rep, and its GLB is a tessellation of that B-rep
(/api/cad/export.step, /api/cad/export.glb)."""
import datetime
import html

import numpy as np

from . import geometry

GUESSED = ("assumed", "engineer", "added", "guess", "typical", "rule")


def _rgb(c):
    c = str(c or "#9aa7b8").lstrip("#")
    return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)] if len(c) == 6 else [0.6, 0.65, 0.72]


def _src(s):
    return "guessed" if any(w in str(s).lower() for w in GUESSED) else "measured"


def report_html(state, build=None, steps=None, title="AETHER build report"):
    """One printable page. build: the last build's report (checks, gear pairs, implausible parts, source image);
    steps: the last run's steps [{label, s}] with the model that did each."""
    build = build or {}
    parts = [p for p in state["parts"] if p["type"] != "group" and p.get("visible", True)]
    lo, hi = geometry.bounds(state["parts"]) if parts else (np.zeros(3), np.zeros(3))   # whole scene: group transforms apply
    rows, n_meas, n_guess = [], 0, 0
    for p in parts:
        e = p.get("eng") or {}
        dims = []
        added = e.get("kind") == "added" or bool(e.get("reason"))      # placed by the engineer's completion: all guessed
        for k, v in (e.get("dims") or {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                g = "guessed" if added else _src(v[1])
                n_meas += g == "measured"
                n_guess += g == "guessed"
                dims.append(f'<span class="{g}">{html.escape(k.replace("_mm", ""))} {html.escape(str(v[0]))}</span>')
        note = html.escape(e.get("reason", ""))
        rows.append(f"<tr><td>{html.escape(p['name'])}</td><td>{html.escape(str(e.get('kind', p['type'])))}</td>"
                    f"<td>{' · '.join(dims[:4])}</td><td class='why'>{note}</td></tr>")
    pairs = "".join(f"<li>{html.escape(str(g.get('a')))} – {html.escape(str(g.get('b')))}: teeth {html.escape(str(g.get('teeth')))}, "
                    f"ratio {html.escape(str(g.get('ratio', '—')))} <span class='why'>({html.escape(str(g.get('source', 'geometry')))})</span></li>"
                    for g in build.get("gear_pairs") or [])
    chk = build.get("check") or {}
    checks = []
    for k, lab_ in (("drawing_lines_on_built_parts_pct", "recall: drawing lines on built parts"),
                    ("staircase_pct", "pixel staircase on part outlines")):
        if k in chk:
            checks.append(f"<li>{lab_}: <b>{chk[k]} %</b></li>")
    if isinstance(chk.get("outline_on_ink_pct"), dict):
        checks.append(f"<li>precision: built outline on the drawing's ink: <b>{chk['outline_on_ink_pct'].get('parts')} %</b> (parts)</li>")
    if build.get("view_match_iou_pct"):
        vm = build["view_match_iou_pct"]
        checks.append("<li>view match on the delivered mesh: <b>" + " / ".join(f"{k} {v}" for k, v in vm.items()) + " %</b></li>")
    if build.get("implausible"):
        checks.append(f"<li>implausible sizes corrected or dropped: {len(build['implausible'])}</li>")
    who = {"read_drawing": ("Muse Spark", "read drawing"), "complete_views": ("Muse Wonder", "complete the unseen views"),
           "Muse Spark": ("Muse Spark", "thinking"), "sam_3_1": ("SAM 3.1", "outline"), "voice": ("Muse Voice Transcribe", "speech to text"),
           "explain · Muse Spark": ("Muse Spark", "explanation"), "illustration · Muse Image": ("Muse Image", "illustration"),
           "cad_pipeline": ("AETHER CAD (OpenCascade)", "three-view sheet -> parametric CAD"), "desk_score": ("Modal T4 GPU", "desk sharpness score"),
           "focus_sweep": ("Modal T4 GPU", "eye focus sweep"), "eye_view": ("Modal T4 GPU", "eye view"),
           "make_hologram": ("Modal T4 GPU", "lab phase hologram"), "classify_upload": ("AETHER engine", "what the image is"),
           "measure_circles": ("AETHER engine", "measure circles on the ink"), "rebuild_3d": ("AETHER engine", "rebuild each part in 3D"),
           "build_assembly": ("AETHER engine", "build the model")}
    st = "".join(f"<tr><td>{html.escape(x.get('who') or who.get(x['label'], ('AETHER engine', ''))[0])}</td>"
                 f"<td>{html.escape(who.get(x['label'], ('', x['label'].replace('_', ' ')))[1] or x['label'].replace('_', ' '))}</td>"
                 f"<td>{x.get('s', '—')} s</td></tr>" for x in steps or [] if x.get("s") is not None)
    img = build.get("image_data_url")
    when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    size = " × ".join(f"{v:.1f}" for v in (hi - lo))
    roots = [p for p in state["parts"] if p["type"] == "group" and not p.get("parent")]
    sc = float((roots[0].get("scale") or [1])[0]) if roots else 1.0
    scale_note = f" on the desk at scale {sc:.3g} (part sizes below: drawing mm, {' × '.join(f'{v / sc:.1f}' for v in (hi - lo))} mm unscaled)" if abs(sc - 1) > 1e-3 else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
@page {{ size: A4; margin: 12mm }}
body {{ font: 9px/1.3 system-ui, sans-serif; color: #111; margin: 0 }}
h1 {{ font-size: 16px; margin: 0 0 2px }} h2 {{ font-size: 11px; margin: 8px 0 3px; text-transform: uppercase; letter-spacing: .06em }}
.top {{ display: flex; gap: 12px }} .top img {{ max-height: 120px; max-width: 200px; border: 1px solid #ccc }}
table {{ border-collapse: collapse; width: 100% }} td {{ border-bottom: 1px solid #eee; padding: 1px 4px; vertical-align: top }}
.measured {{ color: #05603a }} .guessed {{ color: #b54708; font-style: italic }} .why {{ color: #555; font-size: 9px }}
.note {{ border: 1px solid #f0c36d; background: #fffaeb; padding: 4px 6px; margin-top: 6px }}
ul {{ margin: 0; padding-left: 14px }} .cols {{ columns: 2; column-gap: 14px }}
</style></head><body>
<div class="top">{f'<img src="{img}" alt="source drawing">' if img else ''}<div>
<h1>{html.escape(title)}</h1>
<div>{len(parts)} parts · {size} mm (x × y × z){scale_note} · {when}</div>
<div class="{'measured' if build.get('scale_known') else 'guessed'}"><b>Scale:</b> {html.escape(('real size: ' + str(build.get('scale_source'))) if build.get('scale_known') else 'model scale, real size unknown: the drawing states no scale or dimension' + (' (' + str(build.get('scale_source')) + ')' if build.get('scale_source') else ''))}</div>
<div><span class="measured">measured on the drawing: {n_meas} sizes</span> · <span class="guessed">guessed / assumed: {n_guess} sizes</span></div>
<h2>Checks</h2><ul>{''.join(checks) or '<li>none recorded for this model</li>'}</ul>
</div></div>
<h2>Gear pairs</h2><ul>{pairs or '<li>none in this model</li>'}</ul>
<h2>Who did what</h2><table>{st or '<tr><td>no timed steps recorded for this model</td></tr>'}</table>
<h2>Parts (green = measured, orange italic = guessed)</h2><div class="cols"><table>{''.join(rows[:90])}</table></div>
{f'<div class="why">… and {len(rows) - 90} more parts in the GLB file.</div>' if len(rows) > 90 else ''}
<div class="note">Everything here is a model and a simulation: no holographic display has been built. Sizes in green were
measured on the drawing; sizes in orange were assumed or added by the engineer's completion (Muse Spark), each with
its reason. Exported files: GLB (metres, y up, part records in node extras) and STL (millimetres, z up).</div>
</body></html>"""
