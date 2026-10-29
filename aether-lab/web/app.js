import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (id) => document.getElementById(id);
let state = null;
let sweep = { imgs: [], depths: [], sharp: [] };

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

// ================= 3D scene =================
const box = $("three");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0);
box.appendChild(renderer.domElement);
const scene3 = new THREE.Scene();
scene3.fog = new THREE.FogExp2(0x05070d, 0.006);
const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 2000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
scene3.add(new THREE.HemisphereLight(0x9fdcff, 0x1a1030, 0.7));
const key = new THREE.DirectionalLight(0xffffff, 1.6);
key.position.set(30, 40, 80);
scene3.add(key);
const rim = new THREE.PointLight(0x5fe1ff, 40, 0, 2);
scene3.add(rim);

// the hologram (display) at z = 0
const holoTex = new THREE.Texture();
const plane = new THREE.Mesh(new THREE.PlaneGeometry(8.192, 8.192),
  new THREE.MeshBasicMaterial({ color: 0x163b52, side: THREE.DoubleSide, transparent: true, opacity: 0.95 }));
scene3.add(plane);
const frameMat = new THREE.LineBasicMaterial({ color: 0x5fe1ff });
const frame = new THREE.LineSegments(new THREE.EdgesGeometry(plane.geometry), frameMat);
scene3.add(frame);
const glow = new THREE.Mesh(new THREE.PlaneGeometry(11, 11), new THREE.MeshBasicMaterial({
  color: 0x5fe1ff, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false }));
glow.position.z = -0.05;
scene3.add(glow);
const grid = new THREE.GridHelper(40, 40, 0x1f3550, 0x111c2e);
grid.rotation.x = Math.PI / 2; grid.position.z = -0.2;
grid.material.transparent = true; grid.material.opacity = 0.5;
scene3.add(grid);

// floating dust for depth
const dust = new THREE.Points(new THREE.BufferGeometry().setAttribute("position",
  new THREE.Float32BufferAttribute(Array.from({ length: 900 }, () => (Math.random() - 0.5) * 140), 3)),
  new THREE.PointsMaterial({ color: 0x5fe1ff, size: 0.18, transparent: true, opacity: 0.35 }));
dust.position.z = 40;
scene3.add(dust);

let objs = [];
let view = "close";

function gearShape(teeth, r) {
  // same outline as engine/scene.py (mm)
  const s = new THREE.Shape(), n = 360, depth = 0.25 * r / 1.5;
  for (let i = 0; i <= n; i++) {
    const t = (i / n) * Math.PI * 2;
    const tooth = Math.min(1, Math.max(-1, Math.cos(teeth * t) * 3)) * 0.5 + 0.5;
    const rr = r - depth + depth * tooth;
    i ? s.lineTo(rr * Math.cos(t), rr * Math.sin(t)) : s.moveTo(rr * Math.cos(t), rr * Math.sin(t));
  }
  const hole = new THREE.Path();
  hole.absarc(0, 0, r * 0.3, 0, Math.PI * 2, true);
  s.holes.push(hole);
  return s;
}

function drawScene() {
  objs.forEach((m) => scene3.remove(m));
  objs = [];
  for (const o of state.objects) {
    const g = new THREE.ExtrudeGeometry(gearShape(o.teeth, o.radius_mm),
      { depth: 0.35, bevelEnabled: true, bevelSize: 0.04, bevelThickness: 0.04, bevelSegments: 2 });
    g.translate(0, 0, -0.175);
    const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
      color: 0xffcf7a, metalness: 0.75, roughness: 0.28, emissive: 0x2a1600 }));
    const [rx, ry, rz] = o.rotate_deg.map((d) => (d * Math.PI) / 180);
    m.rotation.set(rx, ry, rz, "ZYX");
    m.position.set(...o.position_mm);
    scene3.add(m); objs.push(m);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 30),
      new THREE.LineBasicMaterial({ color: 0xffe2a8, transparent: true, opacity: 0.35 }));
    edges.rotation.copy(m.rotation); edges.position.copy(m.position);
    scene3.add(edges); objs.push(edges);

    // light pyramid: the hologram sends light that converges on the object
    const tip = new THREE.Vector3(...o.position_mm);
    const c = [[-4.1, -4.1], [4.1, -4.1], [4.1, 4.1], [-4.1, 4.1]].map(([x, y]) => new THREE.Vector3(x, y, 0));
    const tri = [];
    for (let i = 0; i < 4; i++) tri.push(c[i], c[(i + 1) % 4], tip);
    const cone = new THREE.Mesh(new THREE.BufferGeometry().setFromPoints(tri), new THREE.MeshBasicMaterial({
      color: 0x5fe1ff, transparent: true, opacity: 0.07, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    scene3.add(cone); objs.push(cone);
    const rays = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(c.flatMap((p) => [p, tip])),
      new THREE.LineBasicMaterial({ color: 0x5fe1ff, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending }));
    scene3.add(rays); objs.push(rays);
    rim.position.set(tip.x + 4, tip.y + 3, tip.z + 6);
  }
  const o = state.objects[0];
  if (o) {
    setSlider("z", o.position_mm[2], `${o.position_mm[2]} mm`);
    setSlider("tilt", o.rotate_deg[1], `${o.rotate_deg[1]}°`);
    setSlider("teeth", o.teeth, o.teeth);
    const holoMm = (state.display.samples * state.display.pitch_um / 1000).toFixed(1);
    $("sceneinfo").innerHTML = `Gear <b>${(o.radius_mm * 2).toFixed(1)} mm</b> · ${o.teeth} teeth<br>
      Floating <b>${o.position_mm[2]} mm</b> in front<br>Hologram <b>${holoMm} mm</b> · ${state.display.pitch_um} µm pixels · ${state.display.wavelength_nm} nm`;
  }
  frameCamera();
}

function setSlider(id, v, label) {
  $(id).value = v;
  $({ z: "zv", tilt: "tv", teeth: "nv" }[id]).textContent = label;
}

function frameCamera() {
  const o = state && state.objects[0];
  const p = o ? new THREE.Vector3(...o.position_mm) : new THREE.Vector3(0, 0, 50);
  if (view === "close") {
    const r = Math.max(2, (o ? o.radius_mm : 1.5) * 5.5);
    controls.target.copy(p);
    camera.position.set(p.x + r * 0.95, p.y + r * 0.45, p.z + r * 1.25);
  } else {
    controls.target.set(0, 0, p.z / 2);
    camera.position.set(p.z * 0.95, p.z * 0.4, p.z * 0.8);
  }
}
document.querySelectorAll("[data-view]").forEach((b) => (b.onclick = () => {
  view = b.dataset.view;
  document.querySelectorAll("[data-view]").forEach((x) => x.classList.toggle("on", x === b));
  frameCamera();
}));

function setHologramTexture(src) {
  const img = new Image();
  img.onload = () => {
    holoTex.image = img; holoTex.needsUpdate = true; holoTex.colorSpace = THREE.SRGBColorSpace;
    plane.material.map = holoTex; plane.material.color.set(0x8fe9ff); plane.material.needsUpdate = true;
  };
  img.src = src;
}

function resize() {
  const w = box.clientWidth, h = box.clientHeight;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(box);
const clock = new THREE.Clock();
(function loop() {
  const t = clock.getElapsedTime();
  dust.rotation.z = t * 0.01;
  glow.material.opacity = 0.06 + 0.03 * Math.sin(t * 1.6);
  controls.update(); renderer.render(scene3, camera); requestAnimationFrame(loop);
})();

// ================= results =================
function showImg(id, src) { const el = $(id); el.src = src; el.classList.add("show"); }

function showImages(im) {
  if (!im) return;
  if (im.hologram) { showImg("holo", im.hologram); setHologramTexture(im.hologram); }
  if (im.reconstruction) { showImg("recon", im.reconstruction); $("depthtag").hidden = true; }
  if (im.sweep) {
    sweep.imgs = im.sweep;
    $("sweep").max = sweep.imgs.length - 1; $("sweep").disabled = false;
    $("sweep").value = Math.floor(sweep.imgs.length / 2);
    showSweep();
  }
  if (im.one_frame) {
    drawer("Speckle · grainy laser light", `<div class="figs">
      <figure><img src="${im.one_frame}"><figcaption>One frame</figcaption></figure>
      <figure><img src="${im.averaged}"><figcaption>Averaged frames</figcaption></figure></div>`);
  }
  if (im.predicted_wall) {
    drawer("Printable film hologram", `<div class="figs">
      <figure><img src="${im.film_tile}" style="image-rendering:pixelated"><figcaption>One film tile · black blocks light</figcaption></figure>
      <figure><img src="${im.predicted_wall}"><figcaption>Predicted picture on the wall (with its mirror twin)</figcaption></figure></div>`);
  }
}

function showSweep() {
  const i = +$("sweep").value;
  if (!sweep.imgs[i]) return;
  showImg("recon", sweep.imgs[i]);
  if (sweep.depths.length) {
    $("depthtag").hidden = false;
    $("depthtag").textContent = `focus ${sweep.depths[i]} mm · ${sweep.sharp[i]}% sharp`;
    const max = Math.max(...sweep.sharp, 1);
    $("spark").innerHTML = sweep.sharp.map((v, k) =>
      `<i class="${k === i ? "on" : ""}" style="height:${Math.max(6, (v / max) * 100)}%" title="${sweep.depths[k]} mm: ${v}%"></i>`).join("");
  }
}
$("sweep").oninput = showSweep;

function drawer(title, html) {
  $("extra").hidden = false; $("extratitle").textContent = title; $("extrabody").innerHTML = html;
}
$("closeextra").onclick = () => ($("extra").hidden = true);

function color(p) { return p >= 80 ? "var(--ok)" : p >= 65 ? "var(--warn)" : "var(--bad)"; }

function deskTable(r) {
  $("desk").innerHTML = r.rows.map((x) => {
    const p = x.sharpness_vs_full_hologram_pct;
    return `<div class="drow"><span class="h">${x.height_cm > 0 ? "+" : ""}${x.height_cm} cm</span>
      <div class="track"><div class="fill" data-w="${p}" style="background:${color(p)}"></div></div>
      <span class="v" style="color:${color(p)}">${p}%</span></div>`;
  }).join("") + `<div class="legend"><span><i style="background:var(--ok)"></i>sharp enough for design</span>
      <span><i style="background:var(--warn)"></i>soft</span><span><i style="background:var(--bad)"></i>blurry</span></div>
    <p class="desknote">Sharpness vs a perfect full hologram · ${r.column_width_um} µm columns · eye box ${r.eye_box_mm} mm. ${r.note}</p>`;
  requestAnimationFrame(() => document.querySelectorAll(".fill").forEach((f) => (f.style.width = f.dataset.w + "%")));
}

function applyResult(name, res) {
  showImages(res._images);
  if (name === "focus_sweep") { sweep.depths = res.depths_mm; sweep.sharp = res.share_of_object_sharp_pct; showSweep(); }
  if (name === "desk_check") deskTable(res);
  if (name === "search_column_width" && res.largest_column_width_um) {
    drawer("Widest column search", `<div class="stat-row">
      <div class="stat"><div class="k">Widest column that works</div><div class="val">${res.largest_column_width_um} <small>µm</small></div></div>
      <div class="stat"><div class="k">Goal</div><div class="val">≥ ${res.min_sharpness_pct}% <small>at ${res.height_cm} cm</small></div></div></div>
      <div class="tried">${res.tried.map((t) => `<span class="${t.passes ? "pass" : "fail"}">${t.column_width_um} µm ${t.passes ? "✓" : "✕"}</span>`).join("")}</div>
      <p class="note">Each try is a full eye-model simulation chosen by the search.</p>`);
  }
  if (name === "measure_speckle" && res.contrast_one_frame !== undefined) {
    $("extrabody").insertAdjacentHTML("afterbegin", `<div class="stat-row">
      <div class="stat"><div class="k">1 frame</div><div class="val">${res.contrast_one_frame}</div></div>
      <div class="stat"><div class="k">${res.frames} frames averaged</div><div class="val">${res.contrast_averaged}</div></div>
      <div class="stat"><div class="k">Visible above</div><div class="val">~0.04</div></div></div>`);
  }
  if (name === "export_film" && res.path) {
    $("extrabody").insertAdjacentHTML("afterbegin", `<div class="stat-row">
      <div class="stat"><div class="k">Print at</div><div class="val">${res.dpi} <small>dpi, 100%</small></div></div>
      <div class="stat"><div class="k">Pixel</div><div class="val">${res.pixel_um.toFixed(1)} <small>µm</small></div></div>
      <div class="stat"><div class="k">Picture on wall (2 m)</div><div class="val">${res.pattern_width_on_wall_cm} <small>cm</small></div></div></div>
      <p class="note"><a class="dl" href="/output/${res.path.split(/[\\/]/).pop()}" download>Download print file</a> · laser: ${res.laser}. Never look into the beam.</p>`);
  }
}

async function tool(name, args = {}) {
  const j = await api("/api/tool", { name, args });
  state = j.state; drawScene();
  if (j.result.error) throw new Error(j.result.error);
  applyResult(name, j.result);
  return j.result;
}

async function busy(btn, fn) {
  btn.disabled = true; btn.classList.add("busy");
  try { await fn(); } catch (e) { log("err", e.message); } finally { btn.disabled = false; btn.classList.remove("busy"); }
}

// ================= manual controls =================
["z", "tilt", "teeth"].forEach((id) => {
  $(id).oninput = () => {
    $("zv").textContent = `${$("z").value} mm`; $("tv").textContent = `${$("tilt").value}°`; $("nv").textContent = $("teeth").value;
  };
  $(id).onchange = () => tool("move_object", { index: 0, position_mm: [0, 0, +$("z").value],
    rotate_deg: [0, +$("tilt").value, 0], teeth: +$("teeth").value }).catch((e) => log("err", e.message));
});
$("calc").onclick = () => busy($("calc"), async () => {
  await tool("make_hologram");
  await tool("propagate", { z_mm: +state.objects[0].position_mm[2] });
});
$("dosweep").onclick = () => busy($("dosweep"), () => tool("focus_sweep", { steps: 9 }));
$("dodesk").onclick = () => busy($("dodesk"), () => tool("desk_check"));

// ================= assistant =================
const NAMES = {
  set_scene: ["SC", "Build scene"], move_object: ["MV", "Move object"], set_display: ["DP", "Set display"],
  make_hologram: ["HG", "Calculate hologram"], propagate: ["PR", "Propagate light"], focus_sweep: ["FS", "Focus sweep"],
  desk_check: ["DK", "Desk check"], search_column_width: ["SR", "Search column width"],
  measure_speckle: ["SP", "Measure speckle"], export_film: ["FM", "Export film"],
};
function summary(t) {
  const r = t.result;
  if (r.error) return "error";
  if (t.tool === "desk_check") return r.rows.map((x) => `${x.height_cm}cm ${x.sharpness_vs_full_hologram_pct}%`).join(" · ");
  if (t.tool === "search_column_width") return r.largest_column_width_um ? `best ${r.largest_column_width_um} µm` : r.result;
  if (t.tool === "focus_sweep") return `${r.depths_mm.length} depths · error ${r.median_depth_error_mm} mm`;
  if (t.tool === "make_hologram") return `${r.points} points → ${r.hologram_px}² px`;
  if (t.tool === "propagate") return `z = ${r.z_mm} mm`;
  if (t.tool === "measure_speckle") return `${r.contrast_one_frame} → ${r.contrast_averaged}`;
  if (t.tool === "move_object") return `depth ${r.depth_range_mm.join("–")} mm`;
  if (t.tool === "export_film") return `${r.dpi} dpi`;
  return "";
}

function log(kind, text) {
  document.querySelector(".hello")?.remove();
  const d = document.createElement("div");
  d.className = `msg ${kind}`; d.textContent = text;
  $("log").appendChild(d); $("log").scrollTop = 1e9;
  return d;
}
function logSteps(trace) {
  if (!trace.length) return;
  const d = document.createElement("div");
  d.className = "steps";
  d.innerHTML = trace.map((t) => {
    const [ic, nm] = NAMES[t.tool] || ["··", t.tool];
    return `<div class="step"><span class="ic">${ic}</span><b>${nm}</b><code>${summary(t)}</code></div>`;
  }).join("");
  $("log").appendChild(d);
}

async function ask(text) {
  log("user", text);
  const dots = document.createElement("div");
  dots.className = "thinking"; dots.innerHTML = "<i></i><i></i><i></i>";
  $("log").appendChild(dots); $("log").scrollTop = 1e9;
  const send = document.querySelector(".send"); send.disabled = true;
  try {
    const j = await api("/api/chat", { text });
    dots.remove();
    logSteps(j.trace);
    state = j.state; drawScene();
    showImages(j.images);
    for (const t of j.trace) applyResult(t.tool, t.result);
    log("ai", j.reply);
  } catch (e) { dots.remove(); log("err", e.message); }
  send.disabled = false;
}

$("ask").onsubmit = (e) => {
  e.preventDefault();
  const text = $("q").value.trim(); if (!text) return;
  $("q").value = ""; ask(text);
};
document.querySelectorAll(".examples button").forEach((b) => (b.onclick = () => ask(b.dataset.q)));

// ================= voice (Muse Voice Transcribe) =================
let rec = null, chunks = [];
async function startRec() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    rec = new MediaRecorder(stream); chunks = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      $("mic").classList.remove("rec");
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      $("q").placeholder = "Transcribing…";
      try {
        const r = await fetch("/api/transcribe", { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error);
        if (j.text.trim()) ask(j.text.trim());
      } catch (e) { log("err", "Voice: " + e.message); }
      $("q").placeholder = "Ask, or hold the mic to talk…";
    };
    rec.start(); $("mic").classList.add("rec"); $("q").placeholder = "Listening… release to send";
  } catch (e) { log("err", "Microphone: " + e.message); }
}
function stopRec() { if (rec && rec.state === "recording") rec.stop(); }
$("mic").addEventListener("pointerdown", startRec);
["pointerup", "pointerleave"].forEach((ev) => $("mic").addEventListener(ev, stopRec));

// ================= start =================
const s = await api("/api/state");
state = s.state;
$("compute").innerHTML = `<i class="dot ${s.compute === "modal" ? "cloud" : "ok"}"></i>physics: ${s.compute === "modal" ? "Modal cloud" : "this PC"}`;
resize(); drawScene();
