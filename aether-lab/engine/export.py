"""Export the scene as files a CAD tool, slicer or web viewer opens, plus a one-page build report.

- STL (binary): every visible part's triangles in world millimetres, z up (what slicers and CAD expect).
- GLB (glTF 2.0 binary): one node per part with its name and colour; glTF is metres and y up, so (x, y, z) mm ->
  (x, z, -y) / 1000. Each node's `extras` carries the part's engineering record (kind, every size with its source:
  measured on the drawing or guessed), so what was measured and what was assumed travels with the file.
- report_html: one printable page (A4): the parts with measured / guessed sizes, gear pairs and where they came from,
  the checks, and which Meta model did each step in how many seconds."""
import base64
import datetime
import html
import json
import struct

import numpy as np

from . import geometry

GUESSED = ("assumed", "engineer", "added", "guess", "typical", "rule")


def _meshes(state):
    return [(p, np.asarray(V, float), np.asarray(F, np.int64)) for p, V, F in geometry.scene_meshes(state["parts"])
            if p["type"] != "group" and len(F)]


def stl(state):
    """Binary STL bytes of the visible scene (mm, z up)."""
    tris = [V[F] for _, V, F in _meshes(state)]
    T = np.concatenate(tris).astype(np.float32) if tris else np.zeros((0, 3, 3), np.float32)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(T), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, T
    head = b"AETHER Lab export, millimetres, z up".ljust(80, b" ")
    return head + struct.pack("<I", len(T)) + rec.tobytes()


def three_mf(state):
    """3MF bytes (the 3D-printing format slicers prefer over STL: units, one named object per part, colours): every
    visible part in world millimetres, z up."""
    import io
    import zipfile
    from xml.sax.saxutils import escape
    ms = _meshes(state)
    cols, objs, items = [], [], []
    for i, (p, V, F) in enumerate(ms, 1):
        c = str(p.get("color") or "#9aa7b8").lstrip("#")
        cols.append(f'<base name="{escape(p["name"])}" displaycolor="#{(c if len(c) == 6 else "9aa7b8").upper()}FF"/>')
        vs = "".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in V)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c_}"/>' for a, b, c_ in F)
        objs.append(f'<object id="{i + 1}" name="{escape(p["name"])}" type="model" pid="1" pindex="{i - 1}">'
                    f'<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>')
        items.append(f'<item objectid="{i + 1}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<metadata name="Application">AETHER Lab</metadata><resources>'
             f'<basematerials id="1">{"".join(cols)}</basematerials>{"".join(objs)}</resources>'
             f'<build>{"".join(items)}</build></model>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
                   'package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-'
                   '3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" '
                   'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)
    return buf.getvalue()


def analyze(meshes, densities):
    """Mass properties of closed meshes [(part, V mm, F)] and densities g/cm3 by part id: volume, area, mass, centre of
    mass, size. Volumes by the divergence theorem (signed tetrahedra from the origin); an open mesh is flagged."""
    out, tot_m, mom = [], 0.0, np.zeros(3)
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    area_all = 0.0
    for p, V, F in meshes:
        T = V[F]
        vol6 = np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2]))
        vol = float(vol6.sum() / 6)
        area = float(0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1).sum())
        c = (vol6[:, None] * (T[:, 0] + T[:, 1] + T[:, 2]) / 4).sum(0) / (vol6.sum() or 1e-12)
        e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
        _, cnt = np.unique(e, axis=0, return_counts=True)
        rho = densities.get(p["id"], 7.85)
        mass = abs(vol) * rho / 1000.0                   # mm3 x g/cm3 / 1000 = g
        out.append({"part": p["name"], "volume_cm3": round(abs(vol) / 1000, 2), "area_cm2": round(area / 100, 1),
                    "density_g_cm3": rho, "mass_g": round(mass, 1), "closed": bool((cnt == 2).all())})
        tot_m += mass
        mom += mass * c
        area_all += area
        lo, hi = np.minimum(lo, V.min(0)), np.maximum(hi, V.max(0))
    return {"parts": out, "mass_kg": round(tot_m / 1000, 3),
            "centre_of_mass_mm": [round(float(x), 1) for x in mom / max(tot_m, 1e-9)],
            "size_mm": [round(float(x), 1) for x in hi - lo], "area_cm2": round(area_all / 100, 1),
            "open_meshes": [x["part"] for x in out if not x["closed"]]}


def _rgb(c):
    c = str(c or "#9aa7b8").lstrip("#")
    return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)] if len(c) == 6 else [0.6, 0.65, 0.72]


def _vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for i in range(3):
        np.add.at(vn, F[:, i], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def glb(state):
    """glTF 2.0 binary bytes: one node per visible part (name, colour, eng record in extras), metres, y up."""
    buf = bytearray()
    views, accs, meshes, nodes, mats = [], [], [], [], []

    def add(arr, target, comp, typ, minmax=False):
        a = np.ascontiguousarray(arr)
        while len(buf) % 4:
            buf.append(0)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": a.nbytes, "target": target})
        buf.extend(a.tobytes())
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(len(a)), "type": typ}
        if minmax:
            acc["min"], acc["max"] = a.min(0).tolist(), a.max(0).tolist()
        accs.append(acc)
        return len(accs) - 1

    for p, V, F in _meshes(state):
        Vg = (np.c_[V[:, 0], V[:, 2], -V[:, 1]] / 1000.0).astype(np.float32)
        Ng = _vertex_normals(V, F)
        Ng = np.c_[Ng[:, 0], Ng[:, 2], -Ng[:, 1]].astype(np.float32)
        pos = add(Vg, 34962, 5126, "VEC3", True)
        nrm = add(Ng, 34962, 5126, "VEC3")
        idx = add(F.astype(np.uint32).ravel(), 34963, 5125, "SCALAR")
        mats.append({"name": p["name"], "pbrMetallicRoughness": {"baseColorFactor": _rgb(p.get("color")) + [1.0],
                                                                  "metallicFactor": 0.3, "roughnessFactor": 0.5}})
        meshes.append({"name": p["name"], "primitives": [{"attributes": {"POSITION": pos, "NORMAL": nrm}, "indices": idx,
                                                          "material": len(mats) - 1}]})
        e = p.get("eng") or {}
        nodes.append({"name": p["name"], "mesh": len(meshes) - 1,
                      "extras": {"kind": e.get("kind", p["type"]), "dims": e.get("dims", {}), "joints": e.get("joints", []),
                                 **({"added_because": e["reason"]} if e.get("reason") else {})}})
    doc = {"asset": {"version": "2.0", "generator": "AETHER Lab (simulation; sizes measured or guessed as tagged)"},
           "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
           "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    while len(buf) % 4:
        buf.append(0)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(buf), b"BIN\x00") + bytes(buf)
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


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
           "desk_score": ("Modal T4 GPU", "desk sharpness score"),
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
