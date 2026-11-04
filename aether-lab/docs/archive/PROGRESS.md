# Progress (status 2026-11-01, evening MYT)

Deadline: Nov 5 2026, 10:00 MYT (Nov 4, 9 PM EST). Target: everything done by Nov 3 evening. Every number here is
from `docs/RESULTS.md` (live runs: real Meta key, Modal T4 GPU) or the test suite (36 tests, all passing).

## Done

| Item | Where | Evidence |
|---|---|---|
| Reliable drawing reading (two readings + agreement, strict JSON, deadline) | `agent.py`, `engine/interpret.py` | RESULTS step 3 tables; test 24 |
| No pixel staircase on built parts (Part A) | `engine/outline.py`, `engine/rebuild.py` | staircase 0.00 %; tests 27, 36 |
| Three-view sheets: 1-px build on Modal, fold guard, surface checks, smooth bodies | `engine/sheet.py`, `engine/quality.py` | G 100 / 99.5 / 98.9 %; tests 26, 28, 29 |
| Thin wing is not a ground line (X-2) | `engine/sheet.py` | X-2 held-out first run 92.6 / 65.8 / 95.1 % -> 99.7 / 95.5 / 99.6 % after; test 25 |
| Explain this machine (Muse Spark) + labelled Muse Image illustration | `explain.py`, `ui/src/ui/ExplainPlayer.jsx` | 6 steps, 0 rejected on D and C; tests 30 |
| Model scale stated (patents have no scale) | `explain.py`, `engine/export.py` | validator + report; tests 30, 33 |
| Section gear pairs, plausibility filter | `engine/rebuild.py` | test 31; RESULTS "C gear pairs" |
| Muse Wonder (medium) for the engineer's completion; Muse Spark keeps reading | `agent.py` | RESULTS Wonder comparison (F1 B 68.9 -> 70.6, D 75.0 -> 72.8, C 76.9 -> 78.0); test 34 |
| Rebuild slowdown fixed (C 17-38 s -> 6 s) | `engine/outline.py` | test 35 |
| Models stand on the base plane; Place on base (Shift+B) | `engine/lab.py` | test 32 |
| Every step shows the Meta model + seconds; voice -> Explain; CJK full stop stripped | `ui/src/ui/Orchestrator.jsx`, `server.py` | screenshots Nov 1 |
| Voice, real speech (owner's test) | — | RESULTS: exact transcript, 34 s end to end |
| GLB + STL export, one-page build report | `engine/export.py`, File menu | test 33; GLB parsed by three.js GLTFLoader (58 meshes) |
| Demo menu D / C / G, warm-up on open, recorded fallback (labelled) | `server.py`, `ui/src/store.js` | two full passes: D 110.5 / 108.9 s, C 121.1 / 161.4 s, G 53.1 / 50.6 s |
| Holography roadmap | `docs/HOLOGRAPHY_ROADMAP.md` (copy of `proposal/long_term/AETHER_Holography_Proposal.md`) | every number cites a note or an engine test |
| README for the submission, Chinese summary | `README.md`, `README_中文.md` | — |
| Static replay site for GitHub Pages | `docs/index.html`, `docs/replay.html`, `docs/replay/`, `tools/build_replay.py` | tested on a plain static server; no key or endpoint in the files |
| Submission mirror + secret scan | `C:\Aether\make_submission.ps1` -> `C:\AetherLab-submission` | 0 key-like hits (Nov 1) |
| Replay test on the demo drawings D and C (outline, surface, time) | `tests/test_physics.py` test 36 | skipped where the saved runs are absent |

## Not done

- SAM 3.1 outline experiment (optional item; not started).
- Test audit for G on the real sheet: G needs the Modal GPU, so its offline guards are the synthetic tests 26 and 29;
  test 36 covers D and C only.
- Known open results: B parts precision 62.9 % (target 70); C recall 73.6 % (target 75); full runs 100-160 s
  (target 90); X-2 tail tips; rib row on G's swept wing edge; car sheet (internal) tyre slabs and roof streaks.
- Voice -> Explain was checked with text phrases, not yet with the microphone.

## For the owner, by hand

1. Record the 3-minute video (Demo menu: warm up, then D or C live; the recorded fallback is labelled if the API is
   slow). Say "smartphone", never a brand name.
2. A short user test with one person, if wanted for the video or the write-up.
3. Create the public GitHub repository, push `C:\AetherLab-submission`, enable Pages (main, `/docs`), then replace
   `https://<user>.github.io/<repo>/` in `README.md` with the real address and run `make_submission.ps1` again.
4. Decide about `proposal/long_term/Aether_Proposal.docx`: it shows as deleted in `C:\Aether` (not deleted by Claude);
   restore it with `git checkout -- proposal/long_term/Aether_Proposal.docx` if that was not intended.
5. Submit on the platform (entry + video + public repo link) before Nov 5, 10:00 MYT.
