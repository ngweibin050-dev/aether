// AETHER Window：逐眼（per-eye）离轴渲染 + 手势 + AI 指令
// 坐标系：单位厘米，原点在屏幕中心，x 向右，y 向上，z 从屏幕指向观看者。
// 屏幕就是一扇“窗”：相机放在眼睛的真实位置，视锥的四条边穿过屏幕四个角（Kooima 广义透视投影）。
import * as THREE from 'three';
import { FilesetResolver, FaceLandmarker, HandLandmarker } from '@mediapipe/tasks-vision';
import { SCENES } from './scenes.js';

// ---------- 配置与校准 ----------
const DEFAULTS = {
  pxPerCm: 37.8,       // CSS 像素/厘米，用卡片校准（C）
  fPx: 0,              // 摄像头焦距（像素），0 = 按 hfov 估算；用 D 校准
  hfovDeg: 62,         // 常见笔电摄像头水平视场
  irisCm: 1.17,        // 人类虹膜直径近似常数
  ipdCm: 6.3,          // 两眼瞳距，D 校准时按本人更新；测距主要靠它（比虹膜稳定得多）
  camAboveCm: 0.8,     // 摄像头在屏幕上沿之上的距离
  floatMaxCm: 4.0,     // 漂浮上限：总纲定理 3，40 cm 观看距离下 <43 mm 时调节误差 <0.3 D
  roomDepthCm: 24,
};
const cfg = { ...DEFAULTS, ...loadCfg() };
function loadCfg() { try { return JSON.parse(localStorage.getItem('aether-cfg') || '{}'); } catch { return {}; } }
function saveCfg() { try { localStorage.setItem('aether-cfg', JSON.stringify(cfg)); } catch { /* 隐私模式下忽略 */ } }

const $ = (id) => document.getElementById(id);
const ui = { status: $('status'), eye: $('eye'), hover: $('hover'), reply: $('reply'), q: $('q'), mic: $('mic'),
  cam: $('cam'), help: $('help'), cardCal: $('card-cal'), cardBox: $('card-box') };

// ---------- 渲染器与场景 ----------
const canvas = $('view');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05070a);
const camera = new THREE.PerspectiveCamera();
camera.matrixAutoUpdate = true;

scene.add(new THREE.HemisphereLight(0xcfe3ff, 0x202530, 1.1));
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(20, 30, 40);
scene.add(key);

const room = new THREE.Group();
scene.add(room);

const pivot = new THREE.Group();   // 用户旋转作用在这里
scene.add(pivot);
let current = null;

const state = { explode: 0, explodeTarget: 0, rotX: 0, rotY: 0, rotXT: 0, rotYT: 0, running: false, selected: null };

function screenSizeCm() { return { W: innerWidth / cfg.pxPerCm, H: innerHeight / cfg.pxPerCm }; }

// 屏幕后方的“盒子房间”：网格墙让大脑立刻读出深度
function buildRoom() {
  room.clear();
  const { W, H } = screenSizeCm();
  const D = cfg.roomDepthCm, step = 2;
  const pts = [];
  const add = (a, b) => pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  for (let z = 0; z >= -D; z -= step) {          // 沿深度的方框
    add(V(-W / 2, -H / 2, z), V(W / 2, -H / 2, z)); add(V(-W / 2, H / 2, z), V(W / 2, H / 2, z));
    add(V(-W / 2, -H / 2, z), V(-W / 2, H / 2, z)); add(V(W / 2, -H / 2, z), V(W / 2, H / 2, z));
  }
  for (let x = -W / 2; x <= W / 2 + 1e-6; x += step) {   // 地板和天花板的纵线
    add(V(x, -H / 2, 0), V(x, -H / 2, -D)); add(V(x, H / 2, 0), V(x, H / 2, -D));
  }
  for (let y = -H / 2; y <= H / 2 + 1e-6; y += step) {   // 两侧墙的纵线
    add(V(-W / 2, y, 0), V(-W / 2, y, -D)); add(V(W / 2, y, 0), V(W / 2, y, -D));
  }
  for (let x = -W / 2; x <= W / 2 + 1e-6; x += step) add(V(x, -H / 2, -D), V(x, H / 2, -D));
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  room.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x1f6f8b, transparent: true, opacity: 0.55 })));
  // 地面上的影子：帮助判断物体悬浮高度
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(4, 48),
    new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.45 }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.set(0, -H / 2 + 0.01, 0);
  room.add(shadow);
}

function loadScene(id) {
  const build = SCENES[id];
  if (!build) return;
  pivot.clear();
  current = build();
  // 物体中心放在屏幕前，最前端不超过 floatMaxCm
  const box = new THREE.Box3().setFromObject(current.group);
  const radius = box.getBoundingSphere(new THREE.Sphere()).radius;
  pivot.position.set(0, 0, Math.max(0, cfg.floatMaxCm - radius * 0.75));
  pivot.add(current.group);
  for (const p of current.parts) {
    p.object.traverse((o) => {
      if (o.isMesh) { o.material = o.material.clone(); o.userData.part = p; o.userData.emissive0 = o.material.emissive.clone(); }
    });
  }
  Object.assign(state, { explode: 0, explodeTarget: 0, selected: null, running: false });
  say(`已载入：${current.title}`, false);
}

function setHighlight(p, on) {
  if (!p) return;
  p.object.traverse((o) => {
    if (o.isMesh) o.material.emissive.copy(on ? new THREE.Color(0x1a6fa0) : o.userData.emissive0);
  });
}

// ---------- 离轴投影 ----------
function applyEye(cam, eye) {
  const { W, H } = screenSizeCm();
  const n = 0.5, f = 600, ez = Math.max(eye.z, 8);
  const l = (-W / 2 - eye.x) * n / ez, r = (W / 2 - eye.x) * n / ez;
  const b = (-H / 2 - eye.y) * n / ez, t = (H / 2 - eye.y) * n / ez;
  cam.position.set(eye.x, eye.y, ez);
  cam.quaternion.identity();
  cam.updateMatrixWorld(true);
  cam.projectionMatrix.makePerspective(l, r, t, b, n, f);   // 不要调用 updateProjectionMatrix，会覆盖
  cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
}

// 红蓝立体：左右眼分别渲染到纹理，再合成
const rtL = new THREE.WebGLRenderTarget(1, 1), rtR = new THREE.WebGLRenderTarget(1, 1);
const compScene = new THREE.Scene();
const compCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
compScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
  uniforms: { tL: { value: rtL.texture }, tR: { value: rtR.texture } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }',
  fragmentShader: `uniform sampler2D tL, tR; varying vec2 vUv;
    void main(){ vec3 l = texture2D(tL, vUv).rgb, r = texture2D(tR, vUv).rgb;
      gl_FragColor = vec4(dot(l, vec3(0.299, 0.587, 0.114)), r.g, r.b, 1.0);
      #include <colorspace_fragment>
    }`,
})));

function resize() {
  renderer.setSize(innerWidth, innerHeight, false);
  const s = renderer.getPixelRatio();
  rtL.setSize(innerWidth * s, innerHeight * s); rtR.setSize(innerWidth * s, innerHeight * s);
  buildRoom();
}
addEventListener('resize', resize);

// ---------- 视点：头部追踪 / 鼠标 ----------
class OneEuro {   // 低速时强平滑，快速移动时低延迟
  constructor(minCutoff = 1.2, beta = 0.02) { this.minCutoff = minCutoff; this.beta = beta; this.x = null; this.dx = 0; this.t = 0; }
  filter(x, t) {
    if (this.x === null) { this.x = x; this.t = t; return x; }
    const dt = Math.max((t - this.t) / 1000, 1e-3); this.t = t;
    const a = (c) => 1 / (1 + 1 / (2 * Math.PI * c * dt));
    const dx = (x - this.x) / dt; this.dx += a(1) * (dx - this.dx);
    this.x += a(this.minCutoff + this.beta * Math.abs(this.dx)) * (x - this.x);
    return this.x;
  }
}
// x/y 要跟手快；z（距离）噪声大，平滑更强，否则物体会“呼吸”
const filt = { cx: new OneEuro(1.0, 0.05), cy: new OneEuro(1.0, 0.05), cz: new OneEuro(0.4, 0.01) };
const view = { mode: 'mouse', stereo: false, left: new THREE.Vector3(-3.2, 0, 50), right: new THREE.Vector3(3.2, 0, 50),
  faceSeen: 0, lastIrisPx: 0, lastIpdPx: 0 };
let mouse = { x: innerWidth / 2, y: innerHeight / 2 };
addEventListener('pointermove', (e) => { mouse = { x: e.clientX, y: e.clientY }; });

function focalPx(videoW) { return cfg.fPx || (videoW / 2) / Math.tan(THREE.MathUtils.degToRad(cfg.hfovDeg / 2)); }

// 估计双眼的 3D 位置（厘米）。
// 距离主要用瞳距：两眼中心相距约 65 像素，1 像素误差只有 1.5%；虹膜直径只有约 12 像素，1 像素误差就是 8%（物体会前后晃）。
// 转头会让瞳距在画面里变短，用头部姿态矩阵的偏航角修正。
function eyesFromFace(lm, vw, vh, t, mat) {
  const px = (i) => ({ x: lm[i].x * vw, y: lm[i].y * vh });
  const d = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const irisPx = (d(px(469), px(471)) + d(px(474), px(476))) / 2;
  const cA = px(468), cB = px(473);
  const ipdPx = d(cA, cB);
  if (ipdPx < 10) return false;
  view.lastIrisPx = irisPx; view.lastIpdPx = ipdPx;
  let yawCos = 1;
  if (mat) {   // 列主序 4x4，第三列是脸的朝向
    const fx = mat[8], fz = mat[10];
    yawCos = THREE.MathUtils.clamp(Math.abs(fz) / Math.hypot(fx, fz), 0.6, 1);
  }
  const f = focalPx(vw);
  const zIpd = f * cfg.ipdCm * yawCos / ipdPx;
  const zIris = irisPx > 2 ? f * cfg.irisCm / irisPx : zIpd;
  const z = 0.85 * zIpd + 0.15 * zIris;
  const { H } = screenSizeCm();
  const c = { x: (cA.x + cB.x) / 2, y: (cA.y + cB.y) / 2 };
  const cx = filt.cx.filter(-(c.x - vw / 2) * z / f, t);                         // 摄像头画面左右与观看者相反
  const cy = filt.cy.filter(-(c.y - vh / 2) * z / f + H / 2 + cfg.camAboveCm, t);  // 摄像头在屏幕上沿
  const cz = filt.cz.filter(z, t);
  const half = cfg.ipdCm / 2;
  view.left.set(cx - half, cy, cz); view.right.set(cx + half, cy, cz);
  return true;
}

function eyesFromMouse() {
  const { W, H } = screenSizeCm();
  const cx = (mouse.x / innerWidth - 0.5) * W * 1.6, cy = -(mouse.y / innerHeight - 0.5) * H * 1.6;
  view.left.set(cx - 3.2, cy, 50); view.right.set(cx + 3.2, cy, 50);
}

// ---------- 手势 ----------
// 手感要点：每只手固定槽位（按左右手），光标做 One Euro 平滑，捏合用 3D 距离 + 迟滞 + 连续帧确认，松手后旋转带惯性。
const mkHand = () => ({ pinch: false, pinchFrames: 0, openFrames: 0, cursor: null, fx: new OneEuro(1.5, 0.3), fy: new OneEuro(1.5, 0.3), seen: 0 });
const hands = { slot: [mkHand(), mkHand()], lastPinch: null, twoStart: null, hover: null, vel: { x: 0, y: 0 } };
const cursorMeshes = [0, 1].map(() => {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.35, 0.5, 32),
    new THREE.MeshBasicMaterial({ color: 0x5fd0ff, transparent: true, opacity: 0.9, depthTest: false }));
  m.renderOrder = 10; m.visible = false; scene.add(m); return m;
});
const raycaster = new THREE.Raycaster();
const ROT_GAIN = 5.0;   // 手横跨整个画面 ≈ 转 5 弧度（约 290°）

function handToScreen(x, y) {   // 手在画面中的位置（0~1）→ 屏幕平面坐标（厘米），带 1.6 倍增益方便够到边角
  const { W, H } = screenSizeCm();
  return new THREE.Vector3(-(x - 0.5) * W * 1.6, -(y - 0.5) * H * 1.6, 0.05);
}

function assignSlots(result) {   // MediaPipe 每帧返回的手顺序会变，按左右手固定槽位，避免两只手“串台”
  const list = result?.landmarks || [];
  const out = [null, null];
  list.forEach((lm, i) => {
    const label = result.handednesses?.[i]?.[0]?.categoryName;
    let k = label === 'Left' ? 1 : 0;
    if (out[k]) k = 1 - k;
    out[k] = lm;
  });
  return out;
}

function processHands(result, t) {
  const slots = assignSlots(result);
  const pinchPts = [];
  for (let i = 0; i < 2; i++) {
    const lm = slots[i], h = hands.slot[i], mesh = cursorMeshes[i];
    if (!lm) {
      if (t - h.seen > 150) { h.pinch = false; h.cursor = null; mesh.visible = false; h.fx = new OneEuro(1.5, 0.3); h.fy = new OneEuro(1.5, 0.3); }
      if (h.pinch && h.cursor) pinchPts.push(h.cursor);   // 短暂丢失时保持状态，不打断拖动
      continue;
    }
    h.seen = t;
    const d3 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, (a.z - b.z) * 0.5);
    const size = d3(lm[0], lm[9]);
    const ratio = d3(lm[4], lm[8]) / size;
    if (ratio < 0.28) { h.pinchFrames++; h.openFrames = 0; } else if (ratio > 0.42) { h.openFrames++; h.pinchFrames = 0; }
    if (!h.pinch && h.pinchFrames >= 2) h.pinch = true;      // 连续 2 帧才算捏合
    if (h.pinch && h.openFrames >= 3) h.pinch = false;       // 连续 3 帧才算松开
    const src = h.pinch ? { x: (lm[4].x + lm[8].x) / 2, y: (lm[4].y + lm[8].y) / 2 } : lm[8];
    const sx = h.fx.filter(src.x, t), sy = h.fy.filter(src.y, t);
    h.cursor = handToScreen(sx, sy); h.cursor.userData = { nx: sx, ny: sy };
    mesh.position.copy(h.cursor); mesh.visible = true;
    mesh.material.color.set(h.pinch ? 0xffb84d : 0x5fd0ff);
    mesh.scale.setScalar(h.pinch ? 0.8 : 1);
    if (h.pinch) pinchPts.push(h.cursor);
  }

  if (pinchPts.length === 2) {            // 双手捏合拉开 = 拆解
    const d = pinchPts[0].distanceTo(pinchPts[1]);
    if (!hands.twoStart) hands.twoStart = { d, explode: state.explodeTarget };
    state.explodeTarget = THREE.MathUtils.clamp(hands.twoStart.explode + (d - hands.twoStart.d) / 15, 0, 1);
    hands.lastPinch = null; hands.vel = { x: 0, y: 0 };
  } else {
    hands.twoStart = null;
    if (pinchPts.length === 1) {          // 单手捏合拖动 = 旋转（直接跟手）
      const p = pinchPts[0].userData;
      if (hands.lastPinch) {
        const dx = (hands.lastPinch.nx - p.nx) * ROT_GAIN, dy = (p.ny - hands.lastPinch.ny) * ROT_GAIN;
        state.rotYT += dx; state.rotXT = THREE.MathUtils.clamp(state.rotXT + dy, -1.4, 1.4);
        const dt = Math.max((t - hands.lastPinch.t) / 1000, 1 / 120);
        hands.vel = { x: 0.6 * hands.vel.x + 0.4 * dx / dt, y: 0.6 * hands.vel.y + 0.4 * dy / dt };
      }
      hands.lastPinch = { nx: p.nx, ny: p.ny, t };
    } else hands.lastPinch = null;        // 松手后由主循环按 vel 继续转（惯性）
  }

  // 食指指向 = 从眼睛穿过屏幕上的光标做射线，命中的零件高亮
  const ptr = hands.slot.find((h) => h.cursor && !h.pinch);
  let hit = null;
  if (ptr && current && pinchPts.length === 0) {
    const eye = view.left.clone().add(view.right).multiplyScalar(0.5);
    raycaster.set(eye, ptr.cursor.clone().sub(eye).normalize());
    const meshes = [];
    pivot.traverse((o) => { if (o.isMesh && o.userData.part) meshes.push(o); });
    hit = raycaster.intersectObjects(meshes, false)[0]?.object.userData.part || null;
  }
  if (hit !== hands.hover) {
    if (hands.hover && hands.hover !== state.selected) setHighlight(hands.hover, false);
    hands.hover = hit;
    if (hit) setHighlight(hit, true);
  }
}

// ---------- AI 指令 ----------
function say(text, speak = true) {
  ui.reply.textContent = text;
  if (speak && 'speechSynthesis' in window) {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text); u.lang = 'zh-CN'; u.rate = 1.05;
    speechSynthesis.speak(u);
  }
}

function findPart(name) {
  if (!current || !name) return null;
  return current.parts.find((p) => p.name === name) || current.parts.find((p) => p.name.includes(name) || name.includes(p.name)) || null;
}

function applyActions(actions = []) {
  for (const a of actions) {
    switch (a.type) {
      case 'explode': state.explodeTarget = THREE.MathUtils.clamp(Number(a.amount) || 0, 0, 1); break;
      case 'rotate': if (a.target === 'x') state.rotXT += THREE.MathUtils.degToRad(a.amount); else state.rotYT += THREE.MathUtils.degToRad(a.amount); break;
      case 'select': {
        const p = findPart(a.target);
        if (state.selected) setHighlight(state.selected, false);
        state.selected = p; setHighlight(p, true);
        if (p) ui.hover.textContent = p.name;
        break;
      }
      case 'clear_select': if (state.selected) setHighlight(state.selected, false); state.selected = null; ui.hover.textContent = ''; break;
      case 'load_scene': loadScene(a.target); break;
      case 'run': state.running = Number(a.amount) > 0; break;
      case 'reset': Object.assign(state, { explodeTarget: 0, rotXT: 0, rotYT: 0, running: false }); hands.vel = { x: 0, y: 0 }; applyActions([{ type: 'clear_select' }]); break;
    }
  }
}

// 断网或没有 API key 时的本地关键词兜底：保证现场演示不会卡死
function localParse(text) {
  const acts = [];
  let reply = '';
  if (/太阳|行星/.test(text)) { acts.push({ type: 'load_scene', target: 'solar' }); reply = '这是太阳系。'; }
  else if (/DNA|dna|基因|双螺旋/.test(text)) { acts.push({ type: 'load_scene', target: 'dna' }); reply = '这是 DNA 双螺旋。'; }
  else if (/发动机|引擎/.test(text) && current?.id !== 'engine') { acts.push({ type: 'load_scene', target: 'engine' }); reply = '这是四缸发动机。'; }
  if (/拆|爆炸|分开|展开/.test(text)) { acts.push({ type: 'explode', amount: 1, target: '' }); reply ||= '拆开了。'; }
  if (/装回|合上|组装|还原/.test(text)) { acts.push({ type: 'explode', amount: 0, target: '' }); reply ||= '装回去了。'; }
  if (/转/.test(text)) { acts.push({ type: 'rotate', amount: 90, target: 'y' }); reply ||= '转一下。'; }
  if (/启动|运行|动起来|转起来/.test(text)) { acts.push({ type: 'run', amount: 1, target: '' }); reply = '启动了。'; }
  if (/停/.test(text)) { acts.push({ type: 'run', amount: 0, target: '' }); reply = '停下了。'; }
  if (/重置|复位/.test(text)) { acts.push({ type: 'reset', amount: 0, target: '' }); reply = '已重置。'; }
  const p = current?.parts.find((q) => text.includes(q.name.replace(/\d+$/, '')));
  if (p) { acts.push({ type: 'select', amount: 0, target: p.name }); reply = `${p.name}：${p.info}`; }
  return { say: reply || '我没听懂，可以试试“拆开”“启动”“活塞是干什么的”。', actions: acts };
}

async function runCommand(text) {
  text = text.trim();
  if (!text) return;
  ui.reply.textContent = `“${text}” …`;
  const snapshot = { scene: current?.id, parts: current?.parts.map((p) => p.name), explode: +state.explodeTarget.toFixed(2),
    running: state.running, selected: state.selected?.name || null };
  let out;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    const r = await fetch('/api/command', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, state: snapshot }), signal: ctl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error(String(r.status));
    out = await r.json();
  } catch {
    out = localParse(text);
  }
  applyActions(out.actions);
  say(out.say);
}

$('ask').addEventListener('submit', (e) => { e.preventDefault(); runCommand(ui.q.value); ui.q.value = ''; ui.q.blur(); });
ui.q.addEventListener('keydown', (e) => { if (e.key === 'Escape') ui.q.blur(); });   // 回车或 Esc 后把键盘还给快捷键

// 语音输入：Chrome 的 Web Speech API（需要联网）
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, listening = false;
function startListen() {
  if (!SR || listening) return;
  rec = new SR(); rec.lang = 'zh-CN'; rec.interimResults = true;
  rec.onresult = (e) => {
    const r = e.results[e.results.length - 1];
    ui.q.value = r[0].transcript;
    if (r.isFinal) { runCommand(r[0].transcript); ui.q.value = ''; }
  };
  rec.onend = () => { listening = false; ui.mic.classList.remove('on'); };
  rec.start(); listening = true; ui.mic.classList.add('on');
}
function stopListen() { if (rec && listening) rec.stop(); }
ui.mic.addEventListener('pointerdown', startListen);
ui.mic.addEventListener('pointerup', stopListen);

// ---------- 键盘 ----------
addEventListener('keydown', (e) => {
  if (document.activeElement === ui.q) return;
  if (!ui.cardCal.hidden) {
    if (e.key === '[') cfg.pxPerCm *= 0.99;
    if (e.key === ']') cfg.pxPerCm *= 1.01;
    if (e.key === 'Enter' || e.key.toLowerCase() === 'c') { ui.cardCal.hidden = true; saveCfg(); resize(); loadScene(current.id); }
    drawCard(); return;
  }
  if (e.code === 'Space') { e.preventDefault(); startListen(); return; }
  switch (e.key.toLowerCase()) {
    case 'f': document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(); break;
    case 'c': ui.cardCal.hidden = false; drawCard(); break;
    case 'd':
      if (view.lastIrisPx) {
        cfg.fPx = 50 * view.lastIrisPx / cfg.irisCm;
        if (view.lastIpdPx) cfg.ipdCm = THREE.MathUtils.clamp(view.lastIpdPx * 50 / cfg.fPx, 5.2, 7.4);   // 记住本人的瞳距
        saveCfg(); say('距离已按 50 厘米校准。', false);
      }
      break;
    case 'm': view.mode = view.mode === 'mouse' ? 'face' : 'mouse'; break;
    case 's': view.stereo = !view.stereo; break;
    case 'v': ui.cam.classList.toggle('show'); break;
    case 'h': ui.help.hidden = !ui.help.hidden; break;
    case 'r': applyActions([{ type: 'reset' }]); break;
    case '1': loadScene('engine'); break;
    case '2': loadScene('solar'); break;
    case '3': loadScene('dna'); break;
  }
});
addEventListener('keyup', (e) => { if (e.code === 'Space' && document.activeElement !== ui.q) stopListen(); });

function drawCard() {   // ISO/IEC 7810 ID-1：85.60 × 53.98 mm，也正是 AETHER 卡片的尺寸
  ui.cardBox.style.width = `${8.56 * cfg.pxPerCm}px`;
  ui.cardBox.style.height = `${5.398 * cfg.pxPerCm}px`;
}

// ---------- 摄像头与追踪 ----------
let face = null, hand = null;
async function initTracking() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 960 }, height: { ideal: 540 }, frameRate: { ideal: 60 }, facingMode: 'user' } });
    ui.cam.srcObject = stream;
    await ui.cam.play();
    const fileset = await FilesetResolver.forVisionTasks('/vendor/mediapipe/wasm');
    const faceLm = await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: '/models/face_landmarker.task', delegate: 'GPU' }, runningMode: 'VIDEO', numFaces: 1, outputFacialTransformationMatrixes: true });
    const handLm = await HandLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: '/models/hand_landmarker.task', delegate: 'GPU' }, runningMode: 'VIDEO', numHands: 2,
      minHandDetectionConfidence: 0.6, minHandPresenceConfidence: 0.6, minTrackingConfidence: 0.5 });
    face = faceLm; hand = handLm;   // 两个都就绪后再启用，避免追踪循环拿到一半
    view.mode = 'face';
    ui.status.textContent = '追踪就绪';
  } catch (err) {
    ui.status.textContent = `摄像头/模型不可用（${err.name || err}），已切到鼠标模拟视点`;
  }
}

let lastVideoTime = -1;
function track(now) {
  const v = ui.cam;
  if (!face || v.readyState < 2 || v.currentTime === lastVideoTime) return;
  lastVideoTime = v.currentTime;
  const fr = face.detectForVideo(v, now);
  const mat = fr.facialTransformationMatrixes?.[0]?.data;
  if (fr.faceLandmarks?.[0] && eyesFromFace(fr.faceLandmarks[0], v.videoWidth, v.videoHeight, now, mat)) view.faceSeen = now;
  processHands(hand.detectForVideo(v, now), now);   // 手势每帧都跑：隔帧会让光标一顿一顿
}

// ---------- 主循环 ----------
const clock = new THREE.Clock();
function loop(now) {
  requestAnimationFrame(loop);
  track(now);
  const faceOk = view.mode === 'face' && now - view.faceSeen < 500;
  if (!faceOk) eyesFromMouse();

  // 平滑动画
  const dt = Math.min(clock.getDelta(), 0.05);
  if (!hands.lastPinch && !hands.twoStart && (Math.abs(hands.vel.x) > 0.02 || Math.abs(hands.vel.y) > 0.02)) {   // 松手后的惯性
    state.rotYT += hands.vel.x * dt; state.rotXT = THREE.MathUtils.clamp(state.rotXT + hands.vel.y * dt, -1.4, 1.4);
    const decay = Math.exp(-dt * 3.5); hands.vel.x *= decay; hands.vel.y *= decay;
  }
  const k = (rate) => 1 - Math.exp(-dt * rate);   // 与帧率无关的平滑
  state.explode += (state.explodeTarget - state.explode) * k(8);
  state.rotX += (state.rotXT - state.rotX) * k(18);
  state.rotY += (state.rotYT - state.rotY) * k(18);
  pivot.rotation.set(state.rotX, state.rotY, 0);
  if (current) {
    if (!current.skipExplode) for (const p of current.parts) p.object.position.copy(p.base).addScaledVector(p.dir, state.explode);
    current.update(clock.elapsedTime, state);
  }

  const mid = view.left.clone().add(view.right).multiplyScalar(0.5);
  ui.eye.textContent = `${faceOk ? '头部追踪' : '鼠标模拟'} · 眼睛 (${mid.x.toFixed(1)}, ${mid.y.toFixed(1)}, ${mid.z.toFixed(1)}) cm`
    + `${view.stereo ? ' · 红蓝立体' : ''}${cfg.pxPerCm === DEFAULTS.pxPerCm ? ' · 屏幕未校准(按 C)' : ''}`;
  if (!state.selected) ui.hover.textContent = hands.hover?.name || '';

  if (view.stereo) {
    applyEye(camera, view.left); renderer.setRenderTarget(rtL); renderer.render(scene, camera);
    applyEye(camera, view.right); renderer.setRenderTarget(rtR); renderer.render(scene, camera);
    renderer.setRenderTarget(null); renderer.render(compScene, compCam);
  } else {
    applyEye(camera, mid); renderer.render(scene, camera);
  }
}

resize();
loadScene('engine');
say('AETHER Window：移动你的头，或者按 H 看帮助。', false);
requestAnimationFrame(loop);
initTracking();
window.aether = { state, view, cfg, hands, runCommand, applyActions, localParse, processHands };   // 方便调试
