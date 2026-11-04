"""Loads AETHER's exported files with trimesh only (no AETHER code) and compares them with the manifest AETHER wrote.
Run by tests/check_exports.py in the isolated env: python -I tests/check_exports_load.py output/exports_check

Per file: does it load, triangles (vs AETHER's count), size in mm (vs AETHER's; GLB is metres and y up by the glTF
standard, so it is converted back), watertight share of its meshes."""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

d = Path(sys.argv[1])
manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
rows = []
for name, m in manifest.items():
    for fmt, fname in m["files"].items():
        row = {"model": name, "format": fmt}
        try:
            sc = trimesh.load(d / fname, force="scene")
            geoms = [g for g in sc.dump() if isinstance(g, trimesh.Trimesh)] if hasattr(sc, "dump") else [sc]
            tris = int(sum(len(g.faces) for g in geoms))
            V = np.vstack([g.vertices for g in geoms])
            size = V.max(0) - V.min(0)
            if fmt == "glb":                                   # glTF: metres, y up -> mm, z up
                size = np.array([size[0], size[2], size[1]]) * 1000.0
            ref = np.asarray(m["size_mm"], float)
            row.update(loads=True, triangles=tris, triangles_expected=m["triangles"],
                       size_mm=[round(float(x), 2) for x in size],
                       size_error_mm=round(float(np.abs(size - ref).max()), 3),
                       watertight_meshes=f"{sum(g.is_watertight for g in geoms)}/{len(geoms)}")
            row["pass"] = tris == m["triangles"] and row["size_error_mm"] < 0.05 * max(1.0, float(ref.max()) / 1000) + 0.01
        except Exception as e:                                  # noqa: BLE001 - a file that does not load is the result
            row.update(loads=False, error=f"{type(e).__name__}: {str(e)[:200]}", **{"pass": False})
        rows.append(row)
(d / "results.json").write_text(json.dumps({"trimesh": trimesh.__version__, "files": rows}, indent=1), encoding="utf-8")
print(f"trimesh {trimesh.__version__}")
print("| model | format | loads | triangles (AETHER) | size mm | max size error mm | watertight meshes | pass |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    if r["loads"]:
        print(f"| {r['model']} | {r['format']} | yes | {r['triangles']} ({r['triangles_expected']}) | "
              f"{' x '.join(f'{x:.0f}' for x in r['size_mm'])} | {r['size_error_mm']} | {r['watertight_meshes']} | "
              f"{'PASS' if r['pass'] else 'FAIL'} |")
    else:
        print(f"| {r['model']} | {r['format']} | NO: {r['error']} | | | | | FAIL |")
print(f"{sum(r['pass'] for r in rows)}/{len(rows)} pass")
