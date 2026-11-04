# Ground truth: does the CAD match the part?

Three mechanical parts with **known dimensions** were modelled in CadQuery and drawn as third-angle engineering drawings (hidden lines dashed, only the overall sizes dimensioned: bores, holes and centre heights must be read from the drawing to scale). AETHER got the drawing PNG and one neutral sentence (`Rebuild this part from its engineering drawing as editable CAD. Units are mm.`), nothing else. Its solids were then measured against the known ones.

This is **synthetic ground truth** (a drawing made from a known model), so it measures the drawing → CAD step, not a scanner. Reproduce: `tests/ground_truth/make_parts.py`, `run_baseline.py`, `run_aether.py`, `score.py`, `report.py`.

Metrics: best of the 24 axis-aligned orientations; overall size error per axis; every truth diameter matched to the nearest cylinder in the result (holes counted by distinct axis); volume error; silhouette IoU (front / top / side) at one scale, 2 px per mm, never stretched; parameters the geometry reads (only those can be corrected).

| part | method | solid? | overall size error (mm, 3 axes) | feature diameters (error mm) | volume error | silhouette IoU (front / top / side) | parameters read | time |
|---|---|---|---|---|---|---|---|---|
| Pillow block bearing housing (140 × 40 × 70 mm) | One-shot (Muse Wonder, no plan / gates / critic) | **no** (OCP.OCP.Standard.Standard_DomainError) | - | - | - | - | - | 134.2 s |
| Pillow block bearing housing (140 × 40 × 70 mm) | AETHER loop (plan, gates, critic, 3 rounds) | yes | +0.0 / +0.0 / +0.1 | Ø56: +4.0<br>Ø30: +4.0<br>Ø12: +2.0 (0/2 found) | -20.2 % | 0.85 / 0.95 / 0.79 | 13 / 13 | 460.8 s |
| Pillow block bearing housing (140 × 40 × 70 mm) | AETHER loop + engineer's correction of the INFERRED parameters (same program re-run, no model call) | yes | +0.0 / +0.0 / +0.1 | Ø56: +0.0<br>Ø30: +0.0<br>Ø12: +0.0 (2/2 found) | -5.0 % | 0.95 / 1.00 / 0.99 | 13 / 13 | 10.2 s |
| Flanged hub (6-bolt) (120 × 120 × 62 mm) | One-shot (Muse Wonder, no plan / gates / critic) | yes | -0.0 / +0.0 / +0.0 | Ø120: +0.0<br>Ø60: +6.0<br>Ø25: +3.0<br>Ø10: +1.0 (6/6 found) | +17.6 % | 0.91 / 0.96 / 0.91 | 10 / 10 | 45.4 s |
| Flanged hub (6-bolt) (120 × 120 × 62 mm) | AETHER loop (plan, gates, critic, 3 rounds) | yes | -0.0 / +0.0 / +0.0 | Ø120: +0.0<br>Ø60: +5.0<br>Ø25: +1.0<br>Ø10: -2.0 (0/6 found) | +19.3 % | 0.92 / 0.97 / 0.92 | 13 / 13 | 304.0 s |
| Flanged hub (6-bolt) (120 × 120 × 62 mm) | AETHER loop + engineer's correction of the INFERRED parameters (same program re-run, no model call) | yes | -0.0 / +0.0 / +0.0 | Ø120: +0.0<br>Ø60: +0.0<br>Ø25: -4.0 (0/1 found)<br>Ø10: -3.0 (0/6 found) | +4.7 % | 1.00 / 0.97 / 1.00 | 13 / 13 | 10.7 s |
| Gusseted angle bracket (100 × 60 × 70 mm) | One-shot (Muse Wonder, no plan / gates / critic) | yes | +0.0 / +0.0 / +0.0 | Ø9: +3.0 (0/4 found) | -2.8 % | 0.98 / 0.98 / 0.88 | 9 / 9 | 65.6 s |
| Gusseted angle bracket (100 × 60 × 70 mm) | AETHER loop (plan, gates, critic, 3 rounds) | yes | +0.0 / +0.0 / +0.0 | Ø9: +3.0 (0/4 found) | +20.7 % | 0.96 / 0.95 / 0.92 | 13 / 13 | 444.7 s |
| Gusseted angle bracket (100 × 60 × 70 mm) | AETHER loop + engineer's correction of the INFERRED parameters (same program re-run, no model call) | yes | +0.0 / +0.0 / +0.0 | Ø9: +0.0 (4/4 found) | +2.7 % | 0.97 / 0.96 / 0.97 | 13 / 13 | 9.3 s |

## What the engineer corrected

Only parameters AETHER had marked *inferred* or *assumed* (scaled off the drawing, not written on it) were set to the part's real values, as calipers on the real part would give them; the same program re-ran.

| part | parameter: AETHER's value → real value | re-run |
|---|---|---|
| Pillow block bearing housing | base_thickness 12 → 14, bolt_hole_diameter 14 → 12, bolt_hole_end_offset 28 → 15, bore_diameter 34 → 30, bore_centre_height 40 → 42, cap_outer_radius 30 → 28, housing_depth 28 → 40, pedestal_width 88 → 70 | 10.2 s |
| Flanged hub (6-bolt) | flange_thickness 15 → 12, hub_diameter 65 → 60, hub_protrusion 47 → 50, central_bore_diameter 30 → 25, bolt_hole_diameter 11 → 10, bolt_pcd 94 → 90 | 10.7 s |
| Gusseted angle bracket | plate_thickness 10 → 8, hole_diameter 12 → 9, hole_spacing 50 → 60, hole_offset_x 25 → 20 | 9.3 s |

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

Raw numbers: [tests/ground_truth/scores.json](../tests/ground_truth/scores.json).
