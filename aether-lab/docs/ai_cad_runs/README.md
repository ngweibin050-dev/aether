# AI-written CAD: the CC0 roadster, cycle by cycle

Each cycle is `cad/codegen.py` (Muse Wonder writes the CadQuery program, the sandbox runs it, code checks it). Cycle 1 starts from the drawing alone; cycles 2-5 revise the kept program of the cycle before (cycle 3 from cycle 2's round 1). Per cycle: every round's plan, error, IoU per view and parts (`cycleN.json`) and the kept program (`cycleN_program.py`).

| cycle | kept round | IoU side / top / end A / end B | mean |
|---|---|---|---|
| cycle1 | 5 | 0.8211 / 0.9709 / 0.9125 / 0.9085 | 0.9032 |
| cycle2 | 3 | 0.7728 / 0.9737 / 0.9089 / 0.9084 | 0.891 |
| cycle3 | 4 | 0.8339 / 0.9591 / 0.9333 / 0.908 | 0.9086 |
| cycle4 | 4 | 0.8645 / 0.9618 / 0.8854 / 0.8726 | 0.8961 |
| cycle5 | 4 | 0.8439 / 0.9749 / 0.8682 / 0.8985 | 0.8964 |

Cycle 4 is the demo model (docs/replay/CAR). Cycle 5 scored about the same but looked lumpier on renders: IoU alone is not enough to keep a round.
