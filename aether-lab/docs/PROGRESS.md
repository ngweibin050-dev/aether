# Progress (status 2026-11-01, evening MYT)

Every number below is from `docs/RESULTS.md` (saved live runs: real Meta key, Modal GPU). Precision uses the official
method (outer edge of the built silhouette within 2 px of the drawing's ink; see RESULTS.md, "How to read").

## Step 0 — baseline (done 2026-10-31)
Code read, 23 tests passing, Meta smoke test passing (SAM 3.1, voice with silence only, design loop 54.3 % -> 81.0 %).

## Step 1 — reference runs (done)
`tests/run_reference.py` runs the UI's own upload function with the real key and saves JSON + images per run.
Copyright-free inputs (`docs/INPUTS.md`): US patents 1,699,653 (B, gearing) and 929,594 (D, press), Fig. 1 each;
NASA's X-3 three-view (G); held-out US 1,770,035 Fig. 1 (C), never tuned on. Earlier stock / brand images are internal only.

## Step 2 — submission repo (prepared, not pushed)
`C:\Aether\make_submission.ps1` mirrors `aether-lab` into `C:\AetherLab-submission` (no `.env`, outputs, graphify,
node_modules, legacy `web/`, unused panels, third-party images) and runs a secret scan (0 key-like hits on Oct 31).
`BUILT_DURING_EVENT.md` and `LICENSE` (MIT) are drafted. Final sync on Nov 3; the owner creates the repo and pushes.

## Step 3 — reliable AI reading (closed, targets partly met)

| Target | B gearing | D press | Held-out C | Met? |
|---|---|---|---|---|
| part-count spread <= 15 % | 2 % | 7 % | 5 % | yes |
| recall >= 75 % (mean of 3) | 79.7 % | 76.8 % | 75.8 % | yes (single runs down to 72.7 %) |
| parts precision >= 70 % (official) | 54.9 % | 67.7 % | 75.3 % | **no on B and D** |
| time <= 90 s (median / worst) | 101.2 / 115.4 s | 96.4 / 109.6 s | 115.7 / 149.0 s | **no** |

Before step 3 (one reading per image): B recall 89.4 %, precision 48.3 %, 168.5 s mean; D 71.4 %, 61.5 %, 130.0 s.
Held-out C ran with the code before the last change (gear / wheel agreement); B and D numbers are the last change.
Three-view G: view match side / top / front 92.2 / 92.6 / 86.1 % (unchanged by step 3); 78.3 s when the computer
was otherwise idle, 135–163 s while other work ran on it.

What step 3 changed (details in `docs/CHANGELOG.md`): strict JSON + temperature 0 + seed, one retry and a timeout per
Muse Spark call; every image read twice, parts kept when both readings agree (gear and wheel count as one kind) or the
drawing confirms them (a measured circle, drawn lines on 3–4 sides); a 60 s reading deadline; completion and region
naming with low reasoning effort (143 s -> 27–33 s, 68–120 s -> 15–23 s); GPU warm-up during reading; outlines fitted to
the ink; round parts seen edge-on built with their axis in the drawing plane; measured gear module unless ISO 54 is
within 3 %; recall and precision side by side in the UI; live seconds per step.

Known causes of the remaining gaps:
- precision on B: the outer silhouette edge of a dense section drawing (curved motor housing as a "wheel" rectangle,
  rough shaft boxes); per-kind diagnostics in RESULTS.md runs;
- time: Muse Spark call times vary between runs (the same reading: 21–54 s per call); readings ~26–54 s, completion
  ~25–54 s, explanation turn ~8–12 s. Steps show their live seconds, so the screen is never blank.

## Part A — no pixel staircase (done, committed)
Machines (replayed readings): parts precision B 54.5 -> 62.9 %, D 69.4 -> 77.2 %, C 75.5 -> 80.4 %; recall fell 1–2
points (C 73.6 %, below 75: the old blocky silhouette over-covered ink; reason in RESULTS.md). Staircase 0.00 %.

## Three-view build (done for the demo input G; open items listed)
- G = NASA X-3, official view match on the delivered mesh: 100.0 / 99.5 / 98.9 %, 40,000 triangles, ~27–34 s on Modal.
- 3-D surface checks on every build (`surface_check`): folds and whole-mesh steps; fold guard after seam smoothing
  (G 525 -> 153 folded edges). Smooth bodies: anti-aliased view masks + `blur_thick` (car sheet roughness 12.7 ->
  8.2 deg; the old coarse build 6.0 deg). Tests 28 and 29.
- Open: rib row on G's swept wing edge (measured, not fixed); car sheet (internal only, not in the demo): tyre side
  lines become flat slabs, faint roof streaks, plain cylinder wheels; NASA X-2 held-out sheet 92.6 / 65.8 / 95.1 %
  (thin wings in the front view not filled) -> fix after Part B; X-2 is then no longer held out.

## Part B — Explain this machine + Muse Image (done; live on D and C)
`explain.py`: Muse Spark gets the built model (every part id, kind, size tagged measured / guessed, reasons for added
parts, gear pairs with tooth counts and the ratio computed in code) plus the drawing, and returns 5–10 steps (title,
2–4 sentences, part ids, camera front / top / iso / section, explode). Code rejects unknown part ids and any number
not in the model, retries once, drops steps still invalid. Muse Image (`muse-image-1.0`, `/v1/images/generations`)
draws one illustration in parallel, labelled "AI illustration — concept, not the measured model", dropped after 30 s.
UI: "Explain this machine" (also Inspect menu) -> step player (Back / Next / Play): parts highlighted, the rest x-ray,
camera moves, explode / section. Test 30. Live: D 16–17 s Spark + 10–16 s image (parallel), 6 steps, 0 rejected
(3 runs); C 14.8 s + 24.3 s, 6 steps, 0 rejected.

## Next (in this order)
1. X-2 thin-wing fill in the front view.
2. 1 h test audit for the demo inputs D, C, G: each test checks outline match, surface quality and time; each
   threshold must fail without its fix.
3. Queue: voice (owner's recorded test; "Explain this machine" by voice), Meta model + seconds on every pipeline
   step, README "Meta models used" table, SAM 3.1 outline experiment (timebox 3 h).
4. Mission steps 4–7 (completion reasons in the UI, checks, GLB/STL export, desk proof, demo menu); final repo sync
   Nov 3.
