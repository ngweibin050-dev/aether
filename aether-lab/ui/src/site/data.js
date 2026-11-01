// Numbers shown on the site. All come from the AETHER simulations (physics notes v9–v13, Lab 2.2–2.3), not a built display.
export const CURVE = {
  z: [-120, -110, -100, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120],
  desk: [77.2, 79.8, 82.2, 84.5, 87.6, 89.5, 91.2, 93.3, 94.5, 95.5, 96.5, 97.0, 97.2, 97.0, 96.5, 95.5, 93.9, 91.9, 89.5, 86.6, 83.4, 79.8, 75.9, 70.2, 65.7],
  screen: [34.7, 41.6, 48.8, 56.0, 63.3, 70.4, 77.2, 83.4, 88.9, 93.5, 97.0, 99.2, 100, 99.2, 96.8, 92.6, 86.9, 79.6, 71.0, 61.4, 51.0, 40.2, 29.5, 19.3, 10.0],
};

export const STATS = [
  { v: "±0.25", u: "D", l: "eye focus tolerance used for “in focus”" },
  { v: "−108…+87", u: "mm", l: "sharp zone above the desk (≥80% of full 2D)" },
  { v: "2.2", u: "%", l: "phase-only error vs. complex modulation" },
  { v: "19/19", u: "", l: "physics & geometry tests passing" },
];

export const TECH = ["Muse Spark", "SAM 3.1", "Modal GPU", "CuPy", "React Three Fiber", "MediaPipe Hands", "Wave optics",
  "Gerchberg–Saxton", "Involute gears", "Visual hull", "Taubin smoothing", "Thibos chromatic eye"];

export const VISION = [
  { k: "01", t: "Design in the air", d: "Speak, sketch or point. The model appears above the desk and you shape it with your hands, like a workshop with no screen in between." },
  { k: "02", t: "True depth, not a flat picture", d: "A hologram rebuilds the light wavefront, so your eye focuses on the part itself. No vergence–accommodation conflict, no headset." },
  { k: "03", t: "AI that builds real parts", d: "Muse Spark reads drawings like an engineer: gears with real modules, links with bores, housings with walls, ready to turn and inspect." },
];

export const PIPELINE = [
  { t: "Speak, sketch or upload", d: "A voice request, a hand-drawn sketch, a blueprint photo, a three-view drawing or an STL/OBJ file.", tag: "Input" },
  { t: "Muse Spark reads it", d: "Tool-calling agent identifies parts, axis ends and tooth counts. SAM 3.1 traces outlines when you want the exact shape.", tag: "Meta AI" },
  { t: "Engineering rebuild", d: "Standard involute gears that mesh, forged links, hubs, housing walls and real machine depth, each size labelled with its source.", tag: "Geometry" },
  { t: "Wave-optics eye check", d: "Every design is scored by a simulated eye: 4 mm pupil, MTF at 15 cpd, phase-only pupil-GS encoding, speckle and colour.", tag: "Physics" },
  { t: "Shown on AETHER Desk", d: "The design floats above a horizontal-parallax holographic panel, sharp where the simulation says it can be.", tag: "Display" },
];

export const FEATURES = [
  { t: "Interpret or trace", d: "Read a drawing as clean standard parts, or trace its exact outline with SAM 3.1.", i: "scan" },
  { t: "Three-view to solid", d: "Front, top and side views carve a watertight visual hull in seconds.", i: "cube" },
  { t: "Gears that turn", d: "Meshing pairs rotate at −z₁/z₂; coaxial parts follow. Real modules and contact ratio.", i: "gear" },
  { t: "See inside", d: "Section plane, exploded view and x-ray, in the editor and in the hologram.", i: "layers" },
  { t: "Full hand mode", d: "Pinch, grab, rotate and scale with MediaPipe hand tracking. Blender-style keys too.", i: "hand" },
  { t: "Closed design loop", d: "The agent measures sharpness with focus_sweep and moves the design into the sharp zone.", i: "loop" },
];

export const RESULTS = [
  { v: 0.855, l: "Wave sim vs. eye model", s: "point MTF on the panel, 0.855 / 0.855" },
  { v: 0.849, l: "Phase-only (pupil-GS)", s: "vs. 0.855 complex; kinoform gives 0.041" },
  { v: 0.2, l: "Haze in dark area", s: "percent, after band-limited GS (η = 0.05)", pct: true },
  { v: 3.6, l: "Speckle contrast", s: "percent, horizontally incoherent columns", pct: true },
];

export const PROVEN = [
  "Eye model validated by independent wave-optics simulation (≈1% agreement)",
  "Phase-only encoding without haze: pupil-GS, 2.2% image error",
  "Oblique-view sharp zone −108…+87 mm along each line of sight",
  "Drawing → meshing 3D machine with real depth (depth/width ≈ 0.6)",
];
export const NOT_YET = [
  "A physical AETHER Desk panel has not been built or measured",
  "kHz phase modulator needed for the 25 cm floating image (Desk 2)",
  "Card-sized version is a long-term goal, not a prototype",
  "Muse Spark's part count can vary between runs of the same drawing",
];
