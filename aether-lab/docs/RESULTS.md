# AETHER Lab — measured results

Inputs and their sources: `docs/INPUTS.md`.

Every number below comes from a saved run (`output/reference/<input>/run<k>/result.json`), produced by `python -m tests.run_reference` with the real Meta key (Muse Spark 1.3, SAM 3.1) and the Modal GPU, through the same function the UI's upload calls (`agent.photo_to_design`, route chosen automatically). All optics are simulations; no holographic display has been built.

## patent_US1699653_fig1 (inputs/US1699653_fig1.png) — one reading per image (before step 3)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-31 18:07:28 | yes | machine | 99 | 119 | 87.9 | 49.8 / 28.9 | — | 10 | 3 | True (82.2) | 8 (0) | 70547 | 201.3 (+111) | — |
| 2 | 2026-10-31 18:10:49 | yes | machine | 107 | 133 | 89.8 | 44.8 / 31.0 | — | 10 | 9 | False (83.4) | 8 (0) | 77119 | 153.5 (+64) | — |
| 3 | 2026-10-31 18:13:23 | yes | machine | 102 | 131 | 90.6 | 50.4 / 29.3 | — | 10 | 12 | True (83.4) | 8 (0) | 71996 | 150.6 (+61) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 102.7 (min 99, max 107, spread 8 %)
- parts built: 127.7 (min 119, max 133, spread 11 %)
- recall, drawing lines on built parts %: 89.4 (min 87.9, max 90.6, spread 3 %)
- precision, parts %: 48.3 (min 44.8, max 50.4, spread 12 %); frames %: 29.7 (min 28.9, max 31, spread 7 %)
- gear pairs: 10.0 (min 10, max 10, spread 0 %)

- total time s: 168.5 (min 150.6, max 201.3, spread 30 %) (target 90 s: 0/3 runs within it)
- Spark calls: 8.0 (min 8, max 8, spread 0 %); tokens: 73220.7 (min 70547, max 77119, spread 9 %)

Time per stage (s, mean over runs): classify_upload 0.3, read_drawing 40.2, measure_circles 15.7, complete_views 63.9, rebuild_3d 6.5, desk_score 23.7, focus_sweep 8.2

## patent_US1699653_fig1 (inputs/US1699653_fig1.png) — two readings per image, temperature 0, strict JSON, agreement (step 3)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 2026-10-31 18:42:16 | yes | machine | 80 | 99 | 69.2 | 53.6 / 28.9 | — | 4 | 6 | True (82.2) | 13 (0) | 89396 | 88.1 (-2) | — |
| 5 | 2026-10-31 18:43:44 | yes | machine | 76 | 97 | 76.4 | 55.3 / 29.9 | — | 5 | 8 | True (83.4) | 13 (0) | 92799 | 88.9 (-1) | — |
| 6 | 2026-10-31 18:45:13 | yes | machine | 74 | 96 | 65.4 | 57.4 / 26.7 | — | 2 | 12 | True (83.4) | 13 (0) | 93879 | 91.8 (+2) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 76.7 (min 74, max 80, spread 8 %)
- parts built: 97.3 (min 96, max 99, spread 3 %)
- recall, drawing lines on built parts %: 70.3 (min 65.4, max 76.4, spread 16 %)
- precision, parts %: 55.4 (min 53.6, max 57.4, spread 7 %); frames %: 28.5 (min 26.7, max 29.9, spread 11 %)
- gear pairs: 3.7 (min 2, max 5, spread 82 %)

- total time s: 89.6 (min 88.1, max 91.8, spread 4 %) (target 90 s: 2/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 92024.7 (min 89396, max 93879, spread 5 %)

Time per stage (s, mean over runs): classify_upload 0.4, read_drawing 44.0, measure_circles 0.0, complete_views 23.4, rebuild_3d 2.2, desk_score 2.2, focus_sweep 6.6

## patent_US1699653_fig1 (inputs/US1699653_fig1.png) — step 3 final: two readings + agreement, outlines fitted to the ink, edge-on round parts, measured gear module, reading deadline

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | 2026-10-31 19:00:26 | yes | machine | 79 | 93 | 82.9 | 56.8 / 34.6 | — | 2 | 5 | False (84.5) | 13 (0) | 89055 | 91.9 (+2) | — |
| 8 | 2026-10-31 19:01:58 | yes | machine | 83 | 99 | 73.0 | 51.7 / 34.3 | — | 2 | 6 | False (79.8) | 13 (0) | 89021 | 96.8 (+7) | — |
| 9 | 2026-10-31 19:03:35 | yes | machine | 79 | 96 | 88.4 | 46.3 / 31.6 | — | 2 | 8 | False (84.5) | 13 (0) | 87161 | 80.6 (-9) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 80.3 (min 79, max 83, spread 5 %)
- parts built: 96.0 (min 93, max 99, spread 6 %)
- recall, drawing lines on built parts %: 81.4 (min 73, max 88.4, spread 19 %)
- precision, parts %: 51.6 (min 46.3, max 56.8, spread 20 %); frames %: 33.5 (min 31.6, max 34.6, spread 9 %)
- gear pairs: 2.0 (min 2, max 2, spread 0 %)

- total time s: 89.8 (min 80.6, max 96.8, spread 18 %) (target 90 s: 1/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 88412.3 (min 87161, max 89055, spread 2 %)

Time per stage (s, mean over runs): classify_upload 0.5, read_drawing 35.8, measure_circles 0.0, complete_views 26.2, rebuild_3d 7.0, desk_score 3.0, focus_sweep 7.3

## patent_US1699653_fig1 (inputs/US1699653_fig1.png) — step 3 closing: as step 3 final + gear / wheel count as one kind in the agreement

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 2026-11-01 00:05:01 | yes | machine | 83 | 99 | 72.7 | 55.4 / 35.8 | — | 2 | 8 | False (84.5) | 13 (0) | 90453 | 115.4 (+25) | — |
| 11 | 2026-11-01 00:06:56 | yes | machine | 83 | 100 | 84.8 | 56.5 / 31.7 | — | 2 | 8 | False (82.2) | 13 (0) | 90543 | 87.7 (-2) | — |
| 12 | 2026-11-01 00:08:24 | yes | machine | 81 | 97 | 81.7 | 52.7 / 28.1 | — | 2 | 8 | False (81.0) | 13 (0) | 97599 | 101.2 (+11) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 82.3 (min 81, max 83, spread 2 %)
- parts built: 98.7 (min 97, max 100, spread 3 %)
- recall, drawing lines on built parts %: 79.7 (min 72.7, max 84.8, spread 15 %)
- precision, parts %: 54.9 (min 52.7, max 56.5, spread 7 %); frames %: 31.9 (min 28.1, max 35.8, spread 24 %)
- gear pairs: 2.0 (min 2, max 2, spread 0 %)

- total time s: 101.4 (min 87.7, max 115.4, spread 27 %) (target 90 s: 1/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 92865.0 (min 90453, max 97599, spread 8 %)

Time per stage (s, mean over runs): classify_upload 0.1, read_drawing 43.2, measure_circles 0.0, complete_views 30.4, rebuild_3d 1.3, desk_score 3.7, focus_sweep 11.3

## patent_US1699653_fig1 (inputs/US1699653_fig1.png) — Muse Wonder reads the drawing and completes the unseen views (Part A rebuild, section gear pairs, plausibility filter)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13 | 2026-11-01 15:36:43 | yes | machine | 104 | 121 | 88.7 | 72.4 / 31.1 | — | 9 | 12 | False (81.4) | 14 (1) | 101156 | 205.1 (+115) | — |
| 14 | 2026-11-01 15:40:08 | yes | machine | 107 | 124 | 88.5 | 58.2 / 32.1 | — | 5 | 11 | False (82.2) | 14 (1) | 106008 | 586.6 (+497) | — |

Mean and spread over 2 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 105.5 (min 104, max 107, spread 3 %)
- parts built: 122.5 (min 121, max 124, spread 2 %)
- recall, drawing lines on built parts %: 88.6 (min 88.5, max 88.7, spread 0 %)
- precision, parts %: 65.3 (min 58.2, max 72.4, spread 22 %); frames %: 31.6 (min 31.1, max 32.1, spread 3 %)
- gear pairs: 7.0 (min 5, max 9, spread 57 %)

- total time s: 395.9 (min 205.1, max 586.6, spread 96 %) (target 90 s: 0/2 runs within it)
- Spark calls: 14.0 (min 14, max 14, spread 0 %); tokens: 103582.0 (min 101156, max 106008, spread 5 %)

Time per stage (s, mean over runs): classify_upload 0.7, read_drawing 284.4, measure_circles 0.2, complete_views 31.0, rebuild_3d 37.5, desk_score 3.2, focus_sweep 13.6

## patent_US1699653_fig1 (inputs/US1699653_fig1.png) — Muse Wonder reads the drawing and completes the unseen views (Part A rebuild, section gear pairs, plausibility filter); reading effort low

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 2026-11-01 15:57:30 | yes | machine | 107 | 125 | 87.7 | 56.2 / 34.2 | — | 11 | 11 | False (83.4) | 13 (0) | 64091 | 114.6 (+25) | — |
| 16 | 2026-11-01 15:59:25 | yes | machine | 107 | 127 | 81.8 | 64.7 / 32.8 | — | 7 | 11 | False (82.2) | 13 (0) | 63921 | 98.9 (+9) | — |

Mean and spread over 2 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 107.0 (min 107, max 107, spread 0 %)
- parts built: 126.0 (min 125, max 127, spread 2 %)
- recall, drawing lines on built parts %: 84.8 (min 81.8, max 87.7, spread 7 %)
- precision, parts %: 60.5 (min 56.2, max 64.7, spread 14 %); frames %: 33.5 (min 32.8, max 34.2, spread 4 %)
- gear pairs: 9.0 (min 7, max 11, spread 44 %)

- total time s: 106.8 (min 98.9, max 114.6, spread 15 %) (target 90 s: 0/2 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 64006.0 (min 63921, max 64091, spread 0 %)

Time per stage (s, mean over runs): classify_upload 0.6, read_drawing 29.3, measure_circles 0.0, complete_views 24.4, rebuild_3d 31.6, desk_score 3.0, focus_sweep 7.8

## patent_US929594_fig1 (inputs/US929594_fig1.png) — one reading per image (before step 3)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-31 18:15:53 | yes | machine | 118 | 131 | 67.9 | 60.3 / 48.9 | — | 0 | 9 | True (90.4) | 8 (0) | 64506 | 127.3 (+37) | — |
| 2 | 2026-10-31 18:18:00 | yes | machine | 127 | 138 | 75.0 | 62.4 / 42.4 | — | 0 | 6 | True (90.4) | 8 (0) | 63193 | 138.4 (+48) | — |
| 3 | 2026-10-31 18:20:19 | yes | machine | 117 | 139 | 71.2 | 61.9 / 33.2 | — | 0 | 8 | True (90.4) | 8 (0) | 63560 | 124.3 (+34) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 120.7 (min 117, max 127, spread 8 %)
- parts built: 136.0 (min 131, max 139, spread 6 %)
- recall, drawing lines on built parts %: 71.4 (min 67.9, max 75, spread 10 %)
- precision, parts %: 61.5 (min 60.3, max 62.4, spread 3 %); frames %: 41.5 (min 33.2, max 48.9, spread 38 %)
- gear pairs: 0

- total time s: 130.0 (min 124.3, max 138.4, spread 11 %) (target 90 s: 0/3 runs within it)
- Spark calls: 8.0 (min 8, max 8, spread 0 %); tokens: 63753.0 (min 63193, max 64506, spread 2 %)

Time per stage (s, mean over runs): classify_upload 0.4, read_drawing 27.9, measure_circles 8.9, complete_views 53.4, rebuild_3d 10.6, desk_score 12.1, focus_sweep 6.9

## patent_US929594_fig1 (inputs/US929594_fig1.png) — two readings per image, temperature 0, strict JSON, agreement (step 3)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 2026-10-31 18:46:45 | yes | machine | 74 | 84 | 79.8 | 71.3 / 66.0 | — | 0 | 6 | True (90.4) | 13 (0) | 81523 | 83.1 (-7) | — |
| 5 | 2026-10-31 18:48:08 | yes | machine | 95 | 106 | 88.6 | 60.7 / 59.1 | — | 0 | 8 | True (90.4) | 13 (2) | 75687 | 205.2 (+115) | — |
| 6 | 2026-10-31 18:51:33 | yes | machine | 88 | 99 | 70.8 | 61.2 / 56.9 | — | 0 | 4 | True (90.4) | 13 (0) | 82355 | 76.6 (-13) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 85.7 (min 74, max 95, spread 25 %)
- parts built: 96.3 (min 84, max 106, spread 23 %)
- recall, drawing lines on built parts %: 79.7 (min 70.8, max 88.6, spread 22 %)
- precision, parts %: 64.4 (min 60.7, max 71.3, spread 16 %); frames %: 60.7 (min 56.9, max 66, spread 15 %)
- gear pairs: 0

- total time s: 121.6 (min 76.6, max 205.2, spread 106 %) (target 90 s: 2/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 79855.0 (min 75687, max 82355, spread 8 %)

Time per stage (s, mean over runs): classify_upload 0.2, read_drawing 72.1, measure_circles 0.0, complete_views 27.8, rebuild_3d 2.1, desk_score 3.9, focus_sweep 5.7

## patent_US929594_fig1 (inputs/US929594_fig1.png) — step 3 final: two readings + agreement, outlines fitted to the ink, edge-on round parts, measured gear module, reading deadline

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | 2026-10-31 19:04:56 | yes | machine | 94 | 105 | 61.8 | 69.8 / 51.2 | — | 0 | 5 | True (90.4) | 13 (0) | 90371 | 86.5 (-4) | — |
| 8 | 2026-10-31 19:06:22 | yes | machine | 103 | 114 | 58.7 | 71.0 / 50.8 | — | 0 | 5 | True (89.5) | 13 (0) | 90050 | 82.7 (-7) | — |
| 9 | 2026-10-31 19:07:45 | yes | machine | 98 | 105 | 84.7 | 70.3 / 59.8 | — | 0 | 4 | True (91.2) | 13 (0) | 88140 | 107.5 (+18) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 98.3 (min 94, max 103, spread 9 %)
- parts built: 108.0 (min 105, max 114, spread 8 %)
- recall, drawing lines on built parts %: 68.4 (min 58.7, max 84.7, spread 38 %)
- precision, parts %: 70.4 (min 69.8, max 71, spread 2 %); frames %: 53.9 (min 50.8, max 59.8, spread 17 %)
- gear pairs: 0

- total time s: 92.2 (min 82.7, max 107.5, spread 27 %) (target 90 s: 2/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 89520.3 (min 88140, max 90371, spread 2 %)

Time per stage (s, mean over runs): classify_upload 0.2, read_drawing 31.6, measure_circles 0.0, complete_views 24.9, rebuild_3d 5.8, desk_score 12.5, focus_sweep 7.6

## patent_US929594_fig1 (inputs/US929594_fig1.png) — step 3 closing: as step 3 final + gear / wheel count as one kind in the agreement

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 2026-10-31 23:59:59 | yes | machine | 102 | 109 | 72.8 | 68.8 / 53.1 | — | 0 | 4 | True (90.4) | 13 (0) | 90152 | 96.4 (+6) | — |
| 11 | 2026-11-01 00:01:36 | yes | machine | 95 | 107 | 73.2 | 68.2 / 73.7 | — | 0 | 6 | True (92.7) | 13 (0) | 86490 | 91.1 (+1) | — |
| 12 | 2026-11-01 00:03:07 | yes | machine | 97 | 112 | 84.3 | 66.2 / 57.1 | — | 0 | 11 | True (90.4) | 13 (0) | 86683 | 109.6 (+20) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 98.0 (min 95, max 102, spread 7 %)
- parts built: 109.3 (min 107, max 112, spread 5 %)
- recall, drawing lines on built parts %: 76.8 (min 72.8, max 84.3, spread 15 %)
- precision, parts %: 67.7 (min 66.2, max 68.8, spread 4 %); frames %: 61.3 (min 53.1, max 73.7, spread 34 %)
- gear pairs: 0

- total time s: 99.0 (min 91.1, max 109.6, spread 19 %) (target 90 s: 0/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 87775.0 (min 86490, max 90152, spread 4 %)

Time per stage (s, mean over runs): classify_upload 0.2, read_drawing 35.3, measure_circles 0.0, complete_views 27.0, rebuild_3d 4.1, desk_score 8.3, focus_sweep 13.3

## patent_US929594_fig1 (inputs/US929594_fig1.png) — Muse Wonder reads the drawing and completes the unseen views (Part A rebuild, section gear pairs, plausibility filter); reading effort low

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13 | 2026-11-01 16:01:51 | yes | machine | 131 | 147 | 84.3 | 64.1 / 67.5 | — | 0 | 12 | True (90.4) | 13 (0) | 66104 | 101.9 (+12) | — |

Mean and spread over 1 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 131
- parts built: 147
- recall, drawing lines on built parts %: 84.3
- precision, parts %: 64.1; frames %: 67.5
- gear pairs: 0

- total time s: 101.9 (target 90 s: 0/1 runs within it)
- Spark calls: 13; tokens: 66104

Time per stage (s, mean over runs): classify_upload 0.9, read_drawing 29.8, measure_circles 0.0, complete_views 35.0, rebuild_3d 13.8, desk_score 3.7, focus_sweep 8.7

## nasa_x3_three_view (inputs/NASA_X-3_three_view.png) — one reading per image (before step 3)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-31 18:22:23 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 30038 | 171.3 (+81) | — |
| 2 | 2026-10-31 18:25:15 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (1) | 4742 | 200.8 (+111) | — |
| 3 | 2026-10-31 18:28:35 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 21299 | 181.1 (+91) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):


- parts built: 33.0 (min 33, max 33, spread 0 %)



- view IoU % (min of the three views): 86.1 (min 86.1, max 86.1, spread 0 %)
- total time s: 184.4 (min 171.3, max 200.8, spread 16 %) (target 90 s: 0/3 runs within it)
- Spark calls: 2.0 (min 2, max 2, spread 0 %); tokens: 18693.0 (min 4742, max 30038, spread 135 %)

Time per stage (s, mean over runs): classify_upload 6.1, read_views 165.7, desk_score 5.3

## nasa_x3_three_view (inputs/NASA_X-3_three_view.png) — two readings per image, temperature 0, strict JSON, agreement (step 3)

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 2026-10-31 18:52:50 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 21987 | 131.4 (+41) | — |
| 5 | 2026-10-31 18:55:01 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 19607 | 117.4 (+27) | — |
| 6 | 2026-10-31 18:56:58 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (1) | 3958 | 184.9 (+95) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):


- parts built: 33.0 (min 33, max 33, spread 0 %)



- view IoU % (min of the three views): 86.1 (min 86.1, max 86.1, spread 0 %)
- total time s: 144.6 (min 117.4, max 184.9, spread 47 %) (target 90 s: 0/3 runs within it)
- Spark calls: 2.0 (min 2, max 2, spread 0 %); tokens: 15184.0 (min 3958, max 21987, spread 119 %)

Time per stage (s, mean over runs): classify_upload 3.4, read_views 129.9, desk_score 4.5

## nasa_x3_three_view (inputs/NASA_X-3_three_view.png) — step 3 final: two readings + agreement, outlines fitted to the ink, edge-on round parts, measured gear module, reading deadline

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | 2026-10-31 23:36:55 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 7565 | 162.5 (+72) | — |
| 8 | 2026-10-31 23:39:37 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 10174 | 135.1 (+45) | — |
| 9 | 2026-10-31 23:41:53 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 8747 | 146.0 (+56) | — |
| 10 | 2026-10-31 23:51:44 | yes | three_view | — | 33 | — | — / — | 92.2/92.6/86.1 | — | — | True (95.9) | 2 (0) | 9313 | 78.3 (-12) | — |

Mean and spread over 4 runs (spread = (max − min) / mean):


- parts built: 33.0 (min 33, max 33, spread 0 %)



- view IoU % (min of the three views): 86.1 (min 86.1, max 86.1, spread 0 %)
- total time s: 130.5 (min 78.3, max 162.5, spread 65 %) (target 90 s: 1/4 runs within it)
- Spark calls: 2.0 (min 2, max 2, spread 0 %); tokens: 8949.8 (min 7565, max 10174, spread 29 %)

Time per stage (s, mean over runs): classify_upload 10.3, read_views 104.5, desk_score 6.0

## nasa_x3_three_view (inputs/NASA_X-3_three_view.png) — step 3 closing: as step 3 final + gear / wheel count as one kind in the agreement

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11 | 2026-11-01 01:28:55 | yes | three_view | — | 44 | — | — / — | 99.8/99.1/98.0 | — | — | True (94.5) | 2 (0) | 8331 | 94.9 (+5) | — |
| 12 | 2026-11-01 01:34:54 | yes | three_view | — | 44 | — | — / — | 99.9/99.2/99.1 | — | — | True (94.5) | 2 (0) | 8954 | 111.7 (+22) | — |
| 13 | 2026-11-01 01:36:46 | yes | three_view | — | 44 | — | — / — | 99.9/99.2/99.1 | — | — | True (94.5) | 2 (0) | 8875 | 69.2 (-21) | — |
| 14 | 2026-11-01 01:45:45 | yes | three_view | — | 44 | — | — / — | 99.9/99.2/99.1 | — | — | True (94.5) | 2 (0) | 8339 | 53.0 (-37) | — |
| 15 | 2026-11-01 01:46:39 | yes | three_view | — | 44 | — | — / — | 99.2/98.6/95.8 | — | — | True (93.9) | 2 (0) | 9814 | 35.6 (-54) | — |
| 16 | 2026-11-01 01:47:14 | yes | three_view | — | 44 | — | — / — | 99.9/99.2/99.1 | — | — | True (94.5) | 2 (0) | 8365 | 34.3 (-56) | — |
| 17 | 2026-11-01 01:53:19 | yes | three_view | — | 44 | — | — / — | 100.0/99.7/98.9 | — | — | True (94.5) | 2 (0) | 7417 | 250.0 (+160) | — |
| 18 | 2026-11-01 01:57:29 | yes | three_view | — | 44 | — | — / — | 100.0/99.7/98.9 | — | — | True (94.5) | 2 (0) | 9265 | 79.3 (-11) | — |
| 19 | 2026-11-01 01:58:49 | yes | three_view | — | 44 | — | — / — | 100.0/99.7/98.9 | — | — | True (94.5) | 2 (0) | 8763 | 31.6 (-58) | — |

Mean and spread over 9 runs (spread = (max − min) / mean):


- parts built: 44.0 (min 44, max 44, spread 0 %)



- view IoU % (min of the three views): 98.5 (min 95.8, max 99.1, spread 3 %)
- total time s: 84.4 (min 31.6, max 250, spread 259 %) (target 90 s: 6/9 runs within it)
- Spark calls: 2.0 (min 2, max 2, spread 0 %); tokens: 8680.3 (min 7417, max 9814, spread 28 %)

Time per stage (s, mean over runs): classify_upload 0.5, read_views 54.7, desk_score 22.8

## heldout_US1770035_fig1 (inputs/heldout/US1770035_fig1.png) — step 3 final: two readings + agreement, outlines fitted to the ink, edge-on round parts, measured gear module, reading deadline

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-31 23:44:30 | yes | machine | 82 | 88 | 78.6 | 80.4 / 45.1 | — | 0 | 3 | True (82.2) | 13 (0) | 104891 | 149.0 (+59) | — |
| 2 | 2026-10-31 23:46:59 | yes | machine | 82 | 96 | 71.9 | 78.9 / 42.3 | — | 0 | 9 | True (81.0) | 13 (0) | 100099 | 115.7 (+26) | — |
| 3 | 2026-10-31 23:48:55 | yes | machine | 86 | 98 | 76.8 | 66.6 / 39.2 | — | 0 | 5 | False (81.0) | 13 (0) | 92993 | 98.3 (+8) | — |

Mean and spread over 3 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 83.3 (min 82, max 86, spread 5 %)
- parts built: 94.0 (min 88, max 98, spread 11 %)
- recall, drawing lines on built parts %: 75.8 (min 71.9, max 78.6, spread 9 %)
- precision, parts %: 75.3 (min 66.6, max 80.4, spread 18 %); frames %: 42.2 (min 39.2, max 45.1, spread 14 %)
- gear pairs: 0

- total time s: 121.0 (min 98.3, max 149, spread 42 %) (target 90 s: 0/3 runs within it)
- Spark calls: 13.0 (min 13, max 13, spread 0 %); tokens: 99327.7 (min 92993, max 104891, spread 12 %)

Time per stage (s, mean over runs): classify_upload 0.3, read_drawing 42.1, measure_circles 0.0, complete_views 39.6, rebuild_3d 11.8, desk_score 5.9, focus_sweep 10.9

## heldout_US1770035_fig1 (inputs/heldout/US1770035_fig1.png) — Muse Wonder reads the drawing and completes the unseen views (Part A rebuild, section gear pairs, plausibility filter); reading effort low

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 2026-11-01 16:03:55 | yes | machine | 104 | 119 | 89.3 | 69.3 / 42.4 | — | 4 | 12 | True (81.0) | 13 (0) | 67926 | 110.5 (+20) | — |

Mean and spread over 1 runs (spread = (max − min) / mean):

- parts read (after agreement, merge and the circle check): 104
- parts built: 119
- recall, drawing lines on built parts %: 89.3
- precision, parts %: 69.3; frames %: 42.4
- gear pairs: 4

- total time s: 110.5 (target 90 s: 0/1 runs within it)
- Spark calls: 13; tokens: 67926

Time per stage (s, mean over runs): classify_upload 0.9, read_drawing 26.6, measure_circles 0.0, complete_views 28.0, rebuild_3d 34.6, desk_score 2.8, focus_sweep 8.6

## heldout_nasa_x36_three_view (inputs/heldout/NASA_X-36_three_view.png) — step 3 closing: as step 3 final + gear / wheel count as one kind in the agreement

| run | date | ok | route | parts read | parts built | recall % | precision % parts / frames | view IoU % (side/top/front) | gear pairs | hidden parts added | desk pass (min %) | Spark calls (failed) | Spark tokens | total s (target 90) | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-01 01:47:54 | yes | three_view | — | 58 | — | — / — | 97.9/96.5/99.6 | — | — | True (94.5) | 2 (0) | 8349 | 39.0 (-51) | — |

Mean and spread over 1 runs (spread = (max − min) / mean):


- parts built: 58



- view IoU % (min of the three views): 96.5
- total time s: 39 (target 90 s: 1/1 runs within it)
- Spark calls: 2; tokens: 8349

Time per stage (s, mean over runs): classify_upload 0.2, read_views 29.9, desk_score 4.4

<!-- Hand-written notes below; tests/run_reference.py keeps them when it rewrites the tables above. -->

## Nov 1 — Part A (no pixel staircase) and the 3-D surface check

**Machines, replayed** (`tests/replay_rebuild.py`: the same saved Muse Spark readings go through the old and the new
rebuild, so only the rebuild changed; mean over the saved runs):

| input | recall % before → after | precision % (parts, official) before → after | staircase on delivered parts |
|---|---|---|---|
| B US1699653 | 77.41 → 76.32 | 54.46 → 62.87 | 0.00 % |
| D US929594 | 73.67 → 72.41 | 69.36 → 77.17 | 0.00 % |
| C US1770035 (held out) | 75.77 → **73.63** | 75.53 → 80.43 | 0.00 % |

**C's recall is 73.6 %, below the 75 % target.** Reason: before Part A every frame and silhouette was drawn on a 1 mm
grid; its blocky edge stuck out past the drawn outline and so lay on extra drawing lines (hatching, neighbouring parts),
which counted as recall. Part A traces frames on the drawing's own pixel grid and vectorises every outline into lines
and arcs (within 1.5 px of the trace), so the silhouette is tighter: fewer lines are covered by accident (recall −1 to
−2 points) and fewer invented edges remain (precision +5 to +8 points). We did not tune C to win the recall back.

**G = NASA X-3, official view match on the delivered mesh** (rasterised, as the UI receives it; one Modal run,
2026-11-01): side 100.0 · top 99.6 · front 99.0; per-part staircase 0.01 %; 40,000 triangles; 68 s including the
automatic Modal redeploy (29–42 s without).

**3-D surface check** (new, `engine/quality.py`, reported as `surface_check` with every three-view build). The per-view
staircase did not see a defect visible in a close-up of G's wing tip (dark sawtooth facets on the thin trailing edge):

- `folds`: folded edges (two triangles facing > 120° apart) and flipped triangles. Measured per build stage on G: surface
  132 / 11, decimated 141 / 26, **seam smoothing 525 / 191**: the seam smoothing pushed a thin rim's two faces through
  each other. Fix: any seam or zig-zag move that turns a triangle over is put back (`quality.keep_unflipped`): 153 / 27
  after seams, 34 flipped triangles on the delivered mesh (Part A mesh: 204). View match unchanged.
- `staircase_px_6px_steps`: the staircase rule on the whole delivered mesh's silhouette edges (inner rims too) in all
  three views, with steps up to 6 px (the decimated mesh's edges are ~7 px). G top view: 334 px before the 1-px build,
  635 px in Part A, 736 px now. **Not fixed**: this is a row of ribs a few px apart along the swept wing edge (voxel
  steps that survive decimation). Two attempts within the 1 h timebox did not remove it: straightening crease zig-zags
  (score fell, render unchanged) and the fold guard (folds only). Test 28 covers both checks.

**Smooth bodies (car sheet, internal only) got worse with the 1-px build, and the tests did not catch it.** Measured on
the delivered mesh (Modal, 2026-11-01): roughness (`quality.roughness`: RMS bend between neighbouring triangles on
smooth surfaces, and the share bent > 10 deg):

| car sheet build | roughness RMS | bent > 10 deg | flipped triangles | view match side / top / front | time |
|---|---|---|---|---|---|
| old coarse (220 voxels) | 5.96 deg | 7.6 % | 16 | 95.7 / 97.0 / 91.1 | 17.5 s |
| 1-px build as in Part A | 12.65 deg | 34.8 % | 762 | 96.4 / 97.9 / 90.7 | 80 s |
| 1-px build now | 8.15 deg | 15.4 % | 355 | 96.4 / 97.9 / 90.7 | 90 s |

Cause: at 1 px per voxel each grid cell is one pixel, so a view's coverage is 0 or 1 and every pixel step of an outline
is extruded along the whole body as a terrace. Fix: each view mask gets one [1 2 1] anti-aliasing pass before the
coverage (`sheet._cover`, aa), and the field is blurred like the coarse build only on and next to parts at least 7 px
thick (`sheet.blur_thick`; a thin wing has no such core and stays sharp). G after it: 100 / 99.5 / 98.9. Smoothing
more (16 passes, 3 px on thick parts) did not lower the car's roughness and cost G's front view 0.1 point: reverted.
New test 29 runs the product's own build on a smooth three-ellipse body: <= 3 deg and >= 99 % (2.24 deg now; 4.9 deg
without the fix). Still open on the car: the tyres' side lines in the front view are filled as body, so thin flat slabs
run along the sides; 1-px steps of the front roof line still leave faint streaks; the wheels are plain cylinders.
X-36 checked the other way: the coarse build gives 96.6 / 94.6 / 95.0 (fine: 99.9 / 99.7 / 99.5) at the same
roughness, so choosing the coarse build for "thick" sheets is not the answer.

**X-36 is no longer held out.** Its first untouched run (2026-11-01 01:47, table above) gave 97.9 / 96.5 / 99.6. After
that its check image was looked at while fixing the three-view build (generic fixes, also tested on G), and it then
read 100 / 99.8 / 99.7; that later number is a tuning result, not a validation.

**New held-out three-view: NASA Bell X-2** (`inputs/heldout/NASA_X-2_three_view.png`, never used for tuning; one run,
2026-11-01, the current build, length 180 mm): **side 92.6 · top 65.8 · front 95.1**, 29.8 s on Modal, 39,998
triangles, per-part staircase 0.02 %, flipped triangles 109. This is the final three-view validation number. Why it is
low: in the front view the thin wings are drawn as a closed outline only a few px tall; the view's fill did not take
them in (only fuselage and tail were filled), and a visual hull keeps only what every view shows, so the outer wings
are carved away, which costs the top view most. The thin nose probe is lost the same way. The fix would be in the view
fill (thin closed outlines), not in the meshing; it is not done.

## Nov 1 — Part B: Explain this machine (Muse Spark) + concept illustration (Muse Image)

Live runs (real key; the model was built from the drawing, Spark and Image calls are new each time). Spark and Image
run in parallel, so the total is the slower of the two.

| input | model built from | Muse Spark explanation | Muse Image | steps | rejected steps | retried |
|---|---|---|---|---|---|---|
| D US929594 | live upload in the UI (78.4 s, 66 parts) | 16.8 s | 12.1 s | 6 | 0 | no |
| D US929594 | same model, second run in the UI | 16.9 s | 10.0 s | 6 | 0 | no |
| D US929594 | saved reading run 7, replayed (115 parts) | 15.6 s | 16.1 s | 6 | 0 | no |
| C US1770035 (held out) | saved reading, replayed | 14.8 s | 24.3 s | 6 | 0 | no |

Every step's part ids exist in the model and every number in its text is a value of the model (checked in code,
`explain.validate`; test 30 shows a wrong id and an invented "300 mm" being rejected). Neither D nor C has a meshing
gear pair in its model (no gear_mesh joint), so Muse Spark gave tooth counts and said no ratio is listed, instead of
inventing one. The model's own odd values are passed on as they are (e.g. a traced shaft 0.4 mm in diameter in D):
the explanation is only as good as the model. The illustration is shown small, labelled "AI illustration — concept, not
the measured model"; it is not a result.

## Nov 1 — rebuild slowdown found and fixed

C's rebuild had gone from ~4 s to 17-38 s (live: "AETHER engine · rebuild each part in 3D" 79-210 s while other work
ran). Cause: since Part A the frames are drawn on the drawing's pixel grid (C: 1195 x 944 cells instead of ~1 mm), and
`outline.fill_holes` flooded from the border one whole-image pass per pixel of the longest background path: 2.8-5.3 s
per frame, four frames per rebuild (profiled: 63 s of 81 s under the profiler). Now reach spreads along whole runs,
rows then columns: 0.30-0.45 s per frame, identical pixels (500 random masks and C's four frames), C's rebuild 6.2 s.
Test 35.

## Nov 1 — C gear pairs and the plausibility filter

**Why C had no meshing pair:** C is a section; every gear in it is cut edge-on (axis in the drawing plane), and the
pairing rule only paired gears seen face-on. Now (`engine/rebuild.py`):
- geometry: two edge-on gears mesh when their axes are parallel, their faces overlap along the axis by half the
  narrower face, and the axis gap is r1 + r2 within 25 % (internal ring: R - r within 10 %, axes >= 0.3 r apart). The
  25 % is what C's real sun / planet pairs read (the box is the tip outline, widened by hatching). Found on C's saved
  readings: run 1: 0 pairs, run 2: 1, run 3: 0; B and D unchanged (B 2-3 face-on pairs per run, D 0).
- otherwise the engineer's completion names the pairs (part numbers + one-line reason); they are built as
  "guessed by Muse Spark" with that reason. On C run 3 a new completion proposed c-q, d-q top, d-q bottom.
- a ratio is given only when both tooth counts were counted (read or FFT); C's were assumed from the size, so every
  pair says "ratio unknown".
- Live C (2026-11-01, upload 93.4 s, 44 parts): 3 pairs, 2 from the geometry, 1 guessed; Explain in the browser
  12.7 s, 6 steps, 0 rejected; its transmission step says which pairs were measured and which guessed, and that the
  ratio is unknown because the teeth were not counted.

**Plausibility filter:** a shaft, piston or spring thinner than 1 % of the machine is a mis-measured width (the "two
drawn sides" were hatching or two close lines: C's pins n, ~20 mm in the drawing, measured 1.4-1.7 mm). Its box
estimate is used when that is plausible, else the part is dropped; each change is listed in `report["implausible"]`.
Replayed on all saved readings (same readings, filter off -> on):

| input | runs | width from the box estimate | dropped | recall % | parts precision % |
|---|---|---|---|---|---|
| B US1699653 | 9 | 0 | 0 | 76.32 -> 76.32 | 62.87 -> 62.87 |
| D US929594 | 9 | 31 | 12 | 72.41 -> 72.30 | 77.17 -> 77.84 |
| C US1770035 | 3 | 5 | 0 | 73.63 -> 73.63 | 80.43 -> 80.43 |

The 0.4 mm shaft in D's live explanation was a 1.3 mm traced width (0.56 % of the 234 mm press) shown after the model
was scaled onto the desk; with the filter it takes its box estimate or is dropped. Test 31 covers both.

## Nov 1 — X-2 front view fixed (held-out result = the first run; after-fix reported separately)

**Held-out result (unchanged, the number to quote):** NASA Bell X-2, first untouched run with the code of that day:
side 92.6 · top 65.8 · front 95.1 %, 29.8 s.

Cause: X-2's front view draws the wing edge-on as a thin closed outline (upper line, centre line, lower line within
10 px) spanning almost the whole view. The ground-line rule (`_drop_ground_line`: a row with ink over >= 80 % of the
width) erased it as if it were the line the aircraft stands on, so the front view kept only fuselage and fins, and the
visual hull carved the outer wings away. Fix (`sheet._in_thin_shape`, both ground-line rules): a horizontal line with
another stroke 3-10 px above or below it in at least half of its columns is one side of a thin closed shape, not a
ground line. Test 25 (ground line erased, flat bottom kept) still passes.

| NASA X-2 three-view | side | top | front | time |
|---|---|---|---|---|
| first run, held out (before the fix) | 92.6 | 65.8 | 95.1 | 29.8 s |
| after the fix (X-2 was used to find it, so this is not a held-out number) | 99.7 | 95.5 | 99.6 | 242 s incl. a Modal redeploy |
| G (X-3) after the fix, unchanged | 100.0 | 99.5 | 98.9 | 32.6 s |

The same fix stopped erasing the tyres' outer lines in the car sheet's end view (internal only): 90.7 -> 99.0 %; its
region names were regenerated by a live Muse Spark naming (18.1 s) because the region numbers changed. Remaining on
X-2: the tips of the horizontal tail (a thin wedge past the fuselage in the side view, only partly filled) are carved
from the top view. No public three-view is held out any more.

## Nov 1 — Muse Voice Transcribe, real speech (owner's test)

| what was said | transcript returned by Muse Voice Transcribe | time | result |
|---|---|---|---|
| "make me a iPhone design" | "make me a iPhone design。" (exact words; a Chinese full stop added) | 34 s end to end, owner's stopwatch: transcription + Muse Spark + 15-part build + focus sweep | 15 parts, 75 x 148.2 x 13.5 mm, 94.7-96.3 % sharp, 0 % off-window |

The transcription alone was not timed in that test; the UI now shows it on the message ("Muse Voice Transcribe ·
speech to text · N s"), and a trailing CJK full stop is removed before the text goes to Muse Spark. The model is a
simplified parametric smartphone shape, not manufacturer data (the reply says so); the demo and README say
"smartphone". Voice can start the explanation: a transcript like "Explain this machine" opens the Explain step player
(phrase rule checked on 6 phrases; not yet tried with the microphone).

## Nov 1 — Muse Wonder reads the dense drawing and does the engineer's completion

`muse-wonder-1.0` (Meta's most capable reasoning model; same endpoint and request format as Muse Spark; probed
2026-11-01: image input, strict json_schema, json_object, temperature, seed, reasoning_effort all accepted) now reads
the drawing (whole sheet + 4 close-ups, each twice) and completes the unseen views. A failed Muse Wonder call is
retried on Muse Spark, and the step label then says "Muse Wonder + Muse Spark (fallback)". Live runs, 2026-11-01:

| input | reading | runs | recall % | parts precision % | read_drawing s | total s |
|---|---|---|---|---|---|---|
| B | Muse Wonder, default effort | 2 | 88.6 | 65.3 (72.4, 58.2) | 284.4 | 205, 587 |
| B | Muse Wonder, effort low (now the default) | 2 | 84.8 | 60.5 (56.2, 64.7) | 29.3 | 115, 99 |
| D | Muse Wonder, effort low | 1 | 84.3 | 64.1 | 29.8 | 102 |
| C | Muse Wonder, effort low | 1 | 89.3 | 69.3 | 26.6 | 111 |
| B / D / C | Muse Spark readings replayed through the same rebuild (mean of saved runs) | 9 / 9 / 3 | 76.3 / 72.3 / 73.6 | 62.9 / 77.8 / 80.4 | ~35-60 | ~96-116 |

Muse Wonder reads more parts (D: 131 kept vs ~80): recall rises 8-16 points on all three drawings; parts precision
does not rise on B and falls 11-14 points on D and C (more parts whose outline is not on a drawn line). At its default
effort the reading takes ~5 x longer for +4 points recall and +5 points precision on B. Costs ~3-5 x Muse Spark per
token (dev.meta.ai pricing). One run each on D and C: not yet a mean. Reading model and effort are switchable without
code changes (META_READ_MODEL, META_READ_EFFORT, META_COMPLETE_MODEL).

**Decision (owner, Nov 1): Muse Spark keeps reading the drawing; Muse Wonder does the engineer's completion (medium
effort).** F1 of recall and parts precision, Muse Spark (replayed) -> Muse Wonder (low effort, live): B 68.9 -> 70.6,
D 75.0 -> 72.8, C 76.9 -> 78.0 (single live runs on D and C). The Muse Wonder reading rows above stay as a measured
comparison; no more Muse Wonder reading runs were made.

## Nov 1 — Demo menu: two full passes with the current code

Each pass, through the server exactly as the Demo menu runs it (warm-up, upload, Explain for the machines); real key,
Modal T4. Reading: Muse Spark; completion: Muse Wonder (medium effort); explanation: Muse Spark; illustration: Muse
Image (in parallel). Sizes on D and C are model scale (300 mm assumed: the patents have no scale).

| demo | pass | read drawing / views | completion | rebuild | build total | Explain (steps, rejected) | total |
|---|---|---|---|---|---|---|---|
| D press | 1 | 30.4 s | 35.0 s | 5.9 s | 93.3 s | 17.2 s (6, 0) | 110.5 s |
| D press | 2 | 29.8 s | 38.5 s | 5.0 s | 95.0 s | 13.9 s (6, 0) | 108.9 s |
| C gearbox | 1 | 34.3 s | 47.2 s | 5.6 s | 109.1 s | 12.0 s (6, 0) | 121.1 s |
| C gearbox | 2 | 41.9 s | 74.8 s | 5.2 s | 141.2 s | 20.2 s (6, 0) | 161.4 s |
| G X-3 | 1 | 40.9 s (Modal) | — | — | 53.1 s | — | 53.1 s |
| G X-3 | 2 | 39.3 s (Modal) | — | — | 50.6 s | — | 50.6 s |

No step failed in either pass. The last successful run of each demo is kept by the server and can be shown from the
Demo menu only as a RECORDED run (banner "RECORDED run · … · not live", and the same label on the explanation).

## How to read these numbers

- **Recall** (`drawing_lines_on_built_parts_pct`): share of the drawing's lines (inside the machine's area) that lie on a built part or frame, front view. A big housing can inflate it, so it is always shown with precision.
- **Precision** (official method): share of the OUTER edge of the built silhouette (front view; all parts merged, frames separately) that lies within 2 px of the drawing's ink; an outline where the drawing has no line was invented. Measured for every run, old or new, on the run's saved check image (its outlines are the silhouette's edge, 3 px wide, on the 1 mm silhouette grid), so before / after compare the same thing. Why this one: each part's own outline (the engine's earlier number) also counts edges lying inside other parts; on B run 7 those were 61 % of the outline pixels and 74 % of them sit on some line of a dense section, so it read 68.9 % where the outer edge reads 56.4 %. Line width (1 px 56.4 %, 3 px 56.8 %) and JPEG (57.1 %) do not explain the gap. Hatching and text count as ink, so precision is an upper bound on dense sheets. Frame outlines are traced on the 1 mm grid, so frame precision is a lower bound, and the 3 mm running clearance cut around every part counts as invented on purpose.
- **Parts read**: parts kept after the reading(s), duplicate merge and the circle check (before hubs and frame plates are added). Its spread across runs is the stability target (≤ 15 %).
- **Total s**: wall time of the whole upload (routing, reading, completion, rebuild, desk score, focus sweep) on Modal T4; the target is 90 s; the number in brackets is how far over or under it is.
- **Ground-line rule** (three-view sheets): the line an object is drawn standing on is not part of the object. A straight horizontal line in the lowest 15 % of a view's ink, at least 40 % of the view's width and at most 5 px thick, is erased before the view is filled, but ONLY if it runs past the object's own outline (measured in the band just above it) on at least one side; a part's own flat bottom edge stays. Where a wheel stands on it, the line's pixels stay. Both cases are test 25. Separate outlines (a nose wheel drawn apart from the fuselage) are kept if they lie inside the main outline's box (+15 %) and do not touch the view's crop edge (a neighbouring view reaching into the crop does).
- **NASA X-3 view match** (86–93 % vs ≥ 95 % on the car sheet): the red areas in its check image are the tips of the horizontal tail and the wings, and the nose wheel. These are surfaces only a few pixels thick in one view: filling each view's outline closes 2 px gaps and erodes back, which removes a thin surface from that view, and a visual hull keeps only what every view shows, so it disappears from the solid. The nose wheel is not connected to the body in the side view, and only the largest connected outline per view is kept. (Before Nov 1; fixed since by the 1-px build without blur and the detached-parts rule: 100 / 99.5 / 98.9 %.)

