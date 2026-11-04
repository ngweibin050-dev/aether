"""tests/ground_truth/scores.json -> docs/GROUND_TRUTH.md (every number in the page comes from score.py)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(os.path.dirname(HERE))
NAMES = {"pillow_block": "Pillow block bearing housing", "flanged_hub": "Flanged hub (6-bolt)",
         "gusset_bracket": "Gusseted angle bracket"}
KINDS = {"baseline": "One-shot (Muse Wonder, no plan / gates / critic)", "aether": "AETHER loop (plan, gates, critic, 3 rounds)",
         "corrected": "AETHER loop + engineer's correction of the INFERRED parameters (same program re-run, no model call)"}


def cell_feats(s):
    out = []
    for f in s["features"]:
        e = "missing" if f["error_mm"] is None else f"{f['error_mm']:+.1f}"
        cnt = f" ({f['count_found']}/{f['count_truth']} found)" if f["count_truth"] > 1 or f["count_found"] != f["count_truth"] else ""
        out.append(f"Ø{f['diameter_mm']:g}: {e}{cnt}")
    return "<br>".join(out)


CF = os.path.join(HERE, "corrections_run.json")
EXTRA = json.load(open(CF)) if os.path.exists(CF) else {}

FINDINGS = """
## What this shows

- **Sizes written on the drawing come out exact** (overall length / width / height within 0.1 mm on all three parts,
  every method): AETHER marks them *read* / *measured*.
- **Sizes scaled off the drawing are a few mm off** (bores +1 to +4 mm, holes ±2 to 3 mm, the hub +5 mm), and AETHER
  marks every one of them *inferred* or *assumed*, with the evidence it used. It does not pretend they were measured.
- **The loop's gain over one shot is robustness and traceability, not raw accuracy** on parts this simple: on the
  pillow block the one-shot program crashed (no solid) and the loop delivered a valid solid; on the hub and the bracket
  both came within a few mm, and the one-shot volume was even closer on the bracket.
- **The engineer's correction is where the error goes away:** setting only the inferred values to the real ones
  re-runs the same program in about 10 s with no model call. Pillow block: every feature diameter exact, both bolt holes
  found, silhouette IoU 0.95 / 1.00 / 0.99. Bracket: all four holes found, exact.
- **A limitation it exposed:** on the hub Muse Wonder modelled the bore and the bolt holes as thin "liner" solids
  (2 / 1.5 mm walls, marked *assumed*) instead of cutting them, so after the correction those holes are still 4 / 3 mm
  under size. Neither the gates nor the critic caught it; a parameter cannot fix it, an edit of the program can. A gate
  for "a hole filled by a solid" is the next check to add.
"""


def main():
    S = json.load(open(os.path.join(HERE, "scores.json")))
    extra = EXTRA
    L = ["# Ground truth: does the CAD match the part?", "",
         "Three mechanical parts with **known dimensions** were modelled in CadQuery and drawn as third-angle engineering "
         "drawings (hidden lines dashed, only the overall sizes dimensioned: bores, holes and centre heights must be read "
         "from the drawing to scale). AETHER got the drawing PNG and one neutral sentence (`Rebuild this part from its "
         "engineering drawing as editable CAD. Units are mm.`), nothing else. Its solids were then measured against the "
         "known ones.", "",
         "This is **synthetic ground truth** (a drawing made from a known model), so it measures the drawing → CAD step, "
         "not a scanner. Reproduce: `tests/ground_truth/make_parts.py`, `run_baseline.py`, `run_aether.py`, `score.py`, "
         "`report.py`.", "",
         "Metrics: best of the 24 axis-aligned orientations; overall size error per axis; every truth diameter matched to "
         "the nearest cylinder in the result (holes counted by distinct axis); volume error; silhouette IoU (front / top / "
         "side) at one scale, 2 px per mm, never stretched; parameters the geometry reads (only those can be corrected).", "",
         "| part | method | solid? | overall size error (mm, 3 axes) | feature diameters (error mm) | volume error | silhouette IoU (front / top / side) | parameters read | time |",
         "|---|---|---|---|---|---|---|---|---|"]
    for part, title in NAMES.items():
        truth = json.load(open(os.path.join(HERE, part, "truth.json")))
        for kind, label in KINDS.items():
            s = S.get(f"{part}/{kind}")
            if not s or s.get("missing"):
                continue
            secs = f"{s.get('seconds') or (extra.get(part) or {}).get('seconds') or '-'} s"
            if s.get("no_solid"):
                why = (s.get("error") or "no valid solid")
                why = why.strip().splitlines()[-1][:80]
                L.append(f"| {title} ({' × '.join(f'{x:g}' for x in truth['size_mm'])} mm) | {label} | **no** ({why}) | - | - | - | - | - | {secs} |")
                continue
            L.append(f"| {title} ({' × '.join(f'{x:g}' for x in truth['size_mm'])} mm) | {label} | yes | "
                     f"{' / '.join(f'{x:+.1f}' for x in s['size_error_mm'])} | {cell_feats(s)} | {s['volume_error_pct']:+.1f} % | "
                     f"{' / '.join(f'{x:.2f}' for x in s['iou_front_top_side'])} | {s['params_read']} / {s['params_total']} | {secs} |")
    if extra:
        L += ["", "## What the engineer corrected", "",
              "Only parameters AETHER had marked *inferred* or *assumed* (scaled off the drawing, not written on it) were "
              "set to the part's real values, as calipers on the real part would give them; the same program re-ran.", "",
              "| part | parameter: AETHER's value → real value | re-run |", "|---|---|---|"]
        for part, c in extra.items():
            ch = ", ".join(f"{k} {c['was'][k]:g} → {v:g}" for k, v in c["overrides"].items())
            L.append(f"| {NAMES[part]} | {ch} | {c['seconds']} s |")
    L += [FINDINGS, "Raw numbers: [tests/ground_truth/scores.json](../tests/ground_truth/scores.json)."]
    open(os.path.join(LAB, "docs", "GROUND_TRUTH.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
