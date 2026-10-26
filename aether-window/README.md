# AETHER Window

**Turn any laptop into a head-tracked 3D window you control with your hands, your voice and Meta's AI models.**

AETHER Window is Phase 0 of AETHER (see `proposal/hackathon_ready/AETHER_Hackathon_Proposal.html` in the repository), a project to build true holography from first principles. A normal webcam tracks your eyes; the screen is rendered as a window into a 3D room, so objects float in front of the glass and stay fixed in space when you move your head. No glasses, no extra hardware.

> Honesty note: this is per-eye perspective rendering, not a true hologram. It is the software half of AETHER and the place where we test the interaction model. Phase 1 of the roadmap is a window-scale true hologram (laser + phase modulator + eye tracking).

## Features

| | What it does |
| --- | --- |
| **Head-tracked window** | Off-axis (generalised perspective) projection from the viewer's real eye position, estimated from iris size with MediaPipe Face Landmarker and One-Euro filtering. |
| **Hands** | Pinch and drag to rotate, pinch with both hands and pull apart to explode a model, point with your index finger to highlight a part. |
| **Voice + AI** | Say "take the engine apart" or "what does the piston do?". A language model (Llama via the Meta Model API) turns speech into structured scene actions plus a spoken answer. Works offline with a keyword fallback. |
| **360° scan to 3D model** | Press **P**, slowly turn an object one full circle in front of the camera, press **P** again. An object detector finds and names the object, hand landmarks cut your hand out of every frame, and the outlines from all angles are carved into a real 3D mesh (visual hull + surface nets) coloured from the photos. Press **E** to export it as `.obj`. Segmentation is pluggable: SAM 3.1 through the server, or MediaPipe's point-prompt segmenter locally. |
| **Two viewers** | Press **T**: the screen splits into two windows, each rendered for one person's eyes. |
| **Window Law demo** | Press **W**: a card-sized window appears with live numbers and a top-down light-cone diagram, showing why every true hologram is a window (Law H1). |
| **Languages** | Press **L** to switch between English and Chinese (UI, speech recognition and voice). |

## Quick start (Windows)

1. Install [Node.js](https://nodejs.org) LTS if you don't have it.
2. Double-click `start.bat`. The browser opens http://localhost:8787.
3. Allow the camera. Everything (Three.js, MediaPipe, models) is bundled, so no `npm install` is needed and it runs offline.

On macOS or Linux: `node server.mjs`, then open http://localhost:8787 in Chrome.

### First-time calibration (30 seconds)

1. Press **C**, hold a bank card against the screen and resize the frame with `[` and `]` until it matches. Press Enter. This gives the real screen size in centimetres.
2. Sit 50 cm from the screen and press **D**. This calibrates the camera's focal length.
3. Press **F** for full screen.

## Connecting the AI models

Edit `ai.config.json` (copy `ai.config.example.json` if it is missing), then restart `start.bat`.

```json
{
  "chat":    { "provider": "meta", "apiKey": "YOUR_KEY", "model": "Llama-4-Maverick-17B-128E-Instruct-FP8", "baseUrl": "https://api.llama.com/compat/v1" },
  "segment": { "provider": "http", "url": "https://your-sam-endpoint", "apiKey": "" }
}
```

- `chat.provider`: `meta` (Llama API, OpenAI-compatible), `openai` (any OpenAI-compatible endpoint), `anthropic`, or `none`. Set the model name and base URL from the event's API docs.
- `segment.provider`: `http` sends `{ image_base64, points, text_prompt }` to `url` and expects `{ mask_base64 }`. Adapt `callSegmenter()` in `server.mjs` to SAM 3.1's real request format; the browser side does not change.
- `ai.config.json` is git-ignored, so keys stay on your machine. Environment variables `AETHER_PROVIDER`, `AETHER_API_KEY`, `AETHER_MODEL` and `AETHER_BASE_URL` override the file.
- The top-left HUD shows which model is active.

## Keys

| Key | Action |
| --- | --- |
| F | Full screen |
| C / D | Screen size calibration / 50 cm distance calibration |
| M | Mouse viewpoint (for recording, or if the camera fails) |
| S | Red-cyan anaglyph stereo |
| V | Camera preview |
| W | Window Law (H1) demo |
| T | Two viewers (split screen) |
| P | 360° scan to 3D model (press again to finish) |
| E | Export the scanned model as .obj |
| L | English / 中文 |
| 1 2 3 4 | Engine / solar system / DNA / captured object |
| R | Reset |
| Space (hold) | Talk |
| H | Help |

## How it works

- `public/app.js`: off-axis projection, iris ranging, gestures, two-viewer split, Window Law demo, AI command layer and local fallback, UI language.
- `public/capture.js`: frame grab, object detection (EfficientDet-Lite0) to find and name the object, hand removal (Hand Landmarker), segmentation (server first, then MediaPipe Interactive Segmenter, then a colour fallback), loop closure, visual-hull carving on a 64³ grid, surface-nets meshing, per-vertex colour from the best-facing photos, and OBJ export.
- `public/scenes.js`: the three demo scenes. Add a scene by writing a `buildXxx()` and registering it in `SCENES`.
- `server.mjs`: static files, `/api/command` (language model to `{ say, actions[] }` with a fixed action schema), `/api/segment`, `/api/status`.

The language model can only return these actions: `explode`, `rotate`, `select`, `clear_select`, `load_scene`, `run`, `reset`, `capture`. Unknown actions are dropped, so the model cannot break the scene.

## Known limits

- Single-webcam hand tracking depends on lighting. Use mouse mode (M) as a fallback in live demos.
- Head-tracked depth is correct only for the tracked viewer(s); bystanders see a skewed image.
- Float depth in front of the screen is capped at 4 cm to stay in the eye's comfort zone; depth behind the screen can be larger.
- Iris-based distance accuracy on real users has not been measured yet.
- The 360° scan assumes the object is turned at a roughly even speed through one full circle. Visual hulls cannot see concave areas (the inside of a cup is filled in). A single-image-to-mesh model such as SAM 3D could plug into the same server later.
- Speech recognition uses Chrome's Web Speech API and needs internet; type in the box when offline.
