# CAD quality benchmark

`python -m tests.cad_quality_bench`: the same objects through the AI-written CAD loop (`cad/codegen.py`). The critic is Muse Spark reviewing real renders against `prompts/cad_critic.md` (0-10; an AI judgement, not a measurement). The gates and IoU are computed by code.

| case | run | rounds | kept | critic overall | fidelity / assembly / surfaces / detail / materials / integrity | gates | IoU side / top / ends | parts | min |
|---|---|---|---|---|---|---|---|---|---|
| car | 20261104-1628 | 5 | 1 | 2 | 3 / 3 / 2 / 2 / 3 / 2 | 110 parts; floating 10, stickers/slivers 0, box-like 51 (46 %), wrong overlaps 0, planned but missing 0 | 0.7038 / 0.8932 / 0.7619 / 0.7614 | 110 | 27.8 |
| car | 20261104-1714 | 5 | 3 | 2 | 4 / 2 / 3 / 2 / 3 / 2 | 118 parts; floating 15, stickers/slivers 0, box-like 65 (55 %), wrong overlaps 4, planned but missing 0, constraints failed 9 of 32 | 0.9142 / 0.9399 / 0.8252 / 0.8274 | 118 | 42.0 |
| roadster | 20261104-1628 | 5 | 5 | 4 | 6 / 6 / 6 / 4 / 5 / 4 | 119 parts; floating 4, stickers/slivers 0, box-like 9 (8 %), wrong overlaps 0, planned but missing 0 | 0.8644 / 0.8793 / 0.7389 / 0.7549 | 119 | 27.0 |
| roadster | 20261104-1714 | 5 | 4 | 3 | 6 / 3 / 4 / 3 / 5 / 4 | 99 parts; floating 5, stickers/slivers 0, box-like 5 (5 %), wrong overlaps 4, planned but missing 0, constraints failed 8 of 29 | 0.8659 / 0.9392 / 0.8627 / 0.8782 | 99 | 33.1 |
| clamp | 20261104-1612 | 5 | - | - | - / - / - / - / - / - | - | - | 0 | 11.5 |
| clamp | 20261104-1628 | 5 | 4 | 5 | 6 / 7 / 4 / 5 / 6 / 9 | 22 parts; floating 0, stickers/slivers 0, box-like 0 (0 %), wrong overlaps 0, planned but missing 0 | - | 22 | 42.7 |
| clamp | 20261104-1714 | 5 | 5 | 3 | 4 / 5 / 3 / 3 / 6 / 5 | 20 parts; floating 0, stickers/slivers 0, box-like 0 (0 %), wrong overlaps 0, planned but missing 0, constraints failed 2 of 16 | - | 20 | 21.0 |
| press | 20261104-1714 | 5 | 3 | 5 | 6 / 6 / 8 / 3 / 4 / 7 | 67 parts; floating 0, stickers/slivers 0, box-like 0 (0 %), wrong overlaps 2, planned but missing 0, constraints failed 0 of 28 | - | 67 | 23.6 |
| engine | 20261104-1628 | 5 | 3 | 5 | 6 / 7 / 7 / 5 / 5 / 8 | 121 parts; floating 0, stickers/slivers 0, box-like 0 (0 %), wrong overlaps 0, planned but missing 0 | - | 121 | 34.7 |
| engine | 20261104-1714 | 5 | 5 | 5 | 6 / 7 / 5 / 5 / 6 / 9 | 90 parts; floating 0, stickers/slivers 0, box-like 0 (0 %), wrong overlaps 0, planned but missing 1, constraints failed 5 of 27; INVALID solids left out: 1 | - | 90 | 19.9 |
