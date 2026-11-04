# Reference inputs and their sources

Every image in this repository that is used for the measured results, the tests and the demo is in the public domain or CC0. The one exception, a third-party car sheet that is used but not redistributed, is described below the table.
Files are in `tests/inputs/`. The full original sheet is kept next to each cropped figure.

| File | What it is | Source | Licence |
|---|---|---|---|
| `US1699653_fig1.png` | **Fig. 1** (sectional side elevation of the whole drive: motor housing, planetary reduction gearing, output shaft, bearings) cropped from sheet 1 | US Patent 1,699,653 "Motor reduction gearing", W. B. Bronander, filed 1926-07-19, granted 1929-01-22 — https://patents.google.com/patent/US1699653A/en (drawing: https://patentimages.storage.googleapis.com/a1/ec/78/0f513f69f710e7/US1699653-drawings-page-1.png) | US patent drawing, public domain |
| `US1699653_sheet1.png` | the full drawing sheet (Fig. 1–4) | same | public domain |
| `US929594_fig1.png` | **Fig. 1** (side elevation, partly in section, of the whole press: frame, ram, crank shaft 55, connecting rod, die, feed levers), cropped above the legs and the signatures | US Patent 929,594 "Metal drawing press", H. C. Hunter, filed 1902-09-10, granted 1909-07-27 — https://patents.google.com/patent/US929594A/en (drawing: https://patentimages.storage.googleapis.com/a6/7b/1e/3a5babfd6c18cf/US929594-drawings-page-1.png) | US patent drawing, public domain |
| `US929594_sheet1.png` | the full sheet 1 (Fig. 1 elevation and Fig. 2 plan) | same | public domain |
| `NASA_X-3_three_view.png` | Douglas X-3 "Stiletto" three-view line drawing (top, front, side), NASA Dryden graphic EG-0086-01 | https://commons.wikimedia.org/wiki/File:Douglas_X-3_line_drawing.png (NASA original without the Commons uploader's footnotes; NASA source: http://www.dfrc.nasa.gov/gallery/Graphics/X-3/index.html) | PD-USGov-NASA |

| `heldout/US1770035_fig1.png` | **Held-out test drawing**: Fig. 1 (sectional elevation of the whole speed reduction gear: housing, planet carrier, input shaft a, output shaft b) cropped from sheet 1. Never used while tuning; its numbers are reported only at the end of a step | US Patent 1,770,035 "Speed reduction gearing", W. Heap et al., filed 1928-09-07, granted 1930-07-08 — https://patents.google.com/patent/US1770035A/en (drawing: https://patentimages.storage.googleapis.com/c8/1c/c9/a814c4ea7024ac/US1770035-drawings-page-1.png) | US patent drawing, public domain |
| `heldout/US1770035_sheet1.png` | the full sheet 1 | same | public domain |
| `heldout/NASA_X-36_three_view.png` | **No longer held out** (Nov 1: its check image was used while fixing the three-view build; its file stays in `heldout/` so old run folders still match). Formerly the held-out three-view: McDonnell Douglas X-36 three-view line drawing (top, front, side), NASA Dryden graphic, rendered by Wikimedia Commons from the SVG at 1920 px and flattened onto white. Not used while tuning until its first run (Oct 31 – Nov 1) | https://commons.wikimedia.org/wiki/File:McDonnell_Douglas_X-36_3-view_drawing.svg (author NASA, 2002-05-02; NASA source: https://www.dfrc.nasa.gov/Gallery/Graphics/X-36/index.html) | PD-USGov-NASA |
| `heldout/NASA_X-2_three_view.png` | **No longer held out** (Nov 1: its front view showed the ground-line bug and was used to fix it; first untouched run 92.6 / 65.8 / 95.1 %). Was the held-out three-view: Bell X-2 three-view line drawing (top, front, side), NASA Dryden graphic (1998-02), rendered by Wikimedia Commons from the SVG at 1920 px and flattened onto white. Never used while tuning | https://commons.wikimedia.org/wiki/File:Bell_X-2_3-view.svg (author Dryden Flight Research Center; NASA source: https://www.dfrc.nasa.gov/Gallery/Graphics/X-2/index.html) | PD-USGov-NASA |
| `heldout/CC0_Cobra_four_view.png` | **Car four-view sheet** (top, side, rear, front), the public input for the CAD pipeline and the CAR demo. Converted from the SVG: Wikimedia's PNG render at 1920 px, red lines turned black, the drawing frame removed, strokes thickened to about 5 px (a 5×5 minimum filter), cropped. Its first CAD run failed at view detection (8 views found). Two general fixes followed in `cad/observations.py`: a straight row inside a view is not a ground line, and a drawing wholly inside another view's box belongs to that view. Its numbers are from the first full run after those fixes; nothing else was tuned on it | "Shelby cobra blueprint i 01.svg" by Igor Križanovskij (Open Clip Art) — https://commons.wikimedia.org/wiki/File:Shelby_cobra_blueprint_i_01.svg | CC0 1.0 (public domain dedication) |

**Not redistributed: the car sheet behind the main CAD evidence.** The car sheet in `docs/EVIDENCE.md` §1–2, §6–7 and
`docs/archive/STORY.md` is a third-party line drawing of a commercial car. It was used for measurement only and is not in this
repository (`.gitignore`). The CC0 sheet above is the reproducible public input.

**Third-party software on Modal only**: `fast-simplification==0.1.13` (MIT licence,
https://github.com/pyvista/fast-simplification) decimates the three-view hull mesh inside the Modal GPU image
(`modal_app.py`). It is not installed or needed on the local computer; local tests skip that step.

**NASA media guidelines** (https://www.nasa.gov/nasa-brand-center/images-and-media/): NASA images are generally not
subject to copyright in the US and may be used freely, but their use must not state or imply that NASA endorses
AETHER, and the NASA insignia / logotype must not be used. AETHER shows the drawing only as an input and says where it
came from.

**Patent figures**: US patents are public domain; the drawings were cropped to one figure each (the one main view
that shows the whole mechanism), because AETHER rebuilds one view of a machine. The router (`vision.upload_kind`)
sends both cropped figures to "Machine drawing" and the X-3 sheet to "Three-view sheet" (measured: edge density
0.213 / 0.501 / 0.09; X-3 views found 3, size disagreement 1.6 %).
