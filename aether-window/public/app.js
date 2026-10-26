// AETHER Window：逐眼（per-eye）离轴渲染 + 手势 + AI 指令
// 坐标系：单位厘米，原点在屏幕中心，x 向右，y 向上，z 从屏幕指向观看者。
// 屏幕就是一扇“窗”：相机放在眼睛的真实位置，视锥的四条边穿过屏幕四个角（Kooima 广义透视投影）。
import * as THREE from 'three';
import { FilesetResolver, FaceLandmarker, HandLandmarker } from '@mediapipe/tasks-vision';
import { SCENES } from './scenes.js';
import { grabFrame, analyzeFrame, buildCaptureScene, buildModelScene, loopClose, toOBJ, generate3D } from './capture.js';

// ---------- 配置与校准 ----------
const DEFAULTS = {
  pxPerCm: 37.8,       // CSS 像素/厘米，用卡片校准（C）
  fPx: 0,              // 摄像头焦距（像素），0 = 按 hfov 估算；用 D 校准
  hfovDeg: 62,         // 常见笔电摄像头水平视场
  irisCm: 1.17,        // 人类虹膜直径近似常数
  camAboveCm: 0.8,     // 摄像头在屏幕上沿之上的距离
  floatMaxCm: 4.0,     // 漂浮上限：总纲定理 3，40 cm 观看距离下 <43 mm 时调节误差 <0.3 D
  roomDepthCm: 24,
};
const cfg = { ...DEFAULTS, ...loadCfg() };
function loadCfg() { try { return JSON.parse(localStorage.getItem('aether-cfg') || '{}'); } catch { return {}; } }
function saveCfg() { try { localStorage.setItem('aether-cfg', JSON.stringify(cfg)); } catch { /* 隐私模式下忽略 */ } }
cfg.lang ||= (navigator.language || '').startsWith('zh') ? 'zh' : 'en';

// ---------- 界面语言（L 切换）：zh 给自己用，en 给评委和录像用 ----------
const TEXT = {
  zh: {
    starting: '正在启动摄像头…', ready: '追踪就绪', noCam: (e) => `摄像头/模型不可用（${e}），已切到鼠标模拟视点`,
    loaded: (t) => `已载入：${t}`, welcome: 'AETHER Window：移动你的头，或者按 H 看帮助。',
    head: '头部追踪', mouse: '鼠标模拟', eyeAt: '眼睛', stereo: ' · 红蓝立体', uncal: ' · 屏幕未校准(按 C)',
    split: ' · 双人：左半屏给左边的人，右半屏给右边的人', calDone: '距离已按 50 厘米校准。',
    aiOn: (m) => `AI：${m}`, aiOff: 'AI：本地关键词（未配置模型）',
    placeholder: '对 AETHER 说：把发动机拆开 / 活塞是干什么的 / 换成太阳系 / 拍照',
    help: `<h2>AETHER Window</h2>
  <p>F 全屏 · C 卡片校准屏幕尺寸 · D 在 50 cm 处校准距离 · M 鼠标模拟视点 · S 红蓝立体 · V 摄像头预览 · W 窗口定律演示</p>
  <p>1 发动机 · 2 太阳系 · 3 DNA · 4 扫描的物体 · P 360° 扫描成 3D 模型（再按 P 结束）· E 导出 .obj · T 双人观看 · L English · R 重置 · 空格 按住说话 · H 关闭帮助</p>
  <p>手势：捏合拇指和食指拖动＝旋转；两只手同时捏合再拉开＝拆解；食指指向零件＝高亮</p>`,
    cardCal: '把一张银行卡/身份卡贴在屏幕上，用 [ 和 ] 调到和卡一样大，按 Enter 确认',
    lawCard: 'AETHER 卡片 85.6 × 54 mm', lawTitle: '定律 H1 · 全息窗口定律',
    lawLead: '只靠光学，真全息就是一扇窗：只有当"眼睛 → 影像点"的连线穿过卡片时，你才看得到那一点。',
    lawNote: '俯视图：蓝线是视线穿过卡片两边形成的"可见锥"。移动头部，物体超出锥的部分就看不见了。按 W 退出。',
    lawNums: (d, ax, ay, m) => `眼睛到卡片 <b>${d} cm</b> · 窗的视角 <b>${ax}° × ${ay}°</b><br>要在这扇窗里看到完整的 1.7 m 真人，人像要在卡片后约 <b>${m} m</b>`,
    lawIn: '物体完全在窗内', lawOut: '物体部分超出窗口 → 被裁掉', lawEye: '眼睛', lawPlane: '卡片 / 屏幕平面',
    shotAim: '把物体放在框里，正面对着镜头，背景越简单越好', shotWork: (i, n) => `正在抠图 ${i}/${n}…`,
    scanning: (n) => `慢慢把物体原地转一圈（从上往下看是逆时针），转完按 P · 已拍 ${n} 张`,
    scanDone: (what, n, tri, src) => `${what}的 3D 模型做好了：用了 ${n} 个角度，${tri} 个三角形${src === 'box' ? '（背景太杂，有些角度没抠干净）' : ''}。捏合转动看各个面，按 E 导出 .obj。`,
    scanFail: '轮廓对不上，做不出立体形状（可能转太快或转不到一圈），先用单张照片代替。再按 P 慢一点扫一次。',
    building: '正在重建 3D 形状…', exported: '已导出模型文件。', noModel: '还没有扫描出的 3D 模型。',
    seen: (what, h) => `认出来了：${what}${h ? ' · 已去掉手' : ''}`,
    sam3d: (sec) => `SAM 3D 正在生成 3D 模型（一般要 1 分钟左右）· ${sec} 秒`,
    sam3dDone: (what) => `${what}的 3D 模型生成好了（SAM 3D）。捏合转动看各个面，按 E 导出 .glb。`,
    sam3dFail: (e) => `SAM 3D 生成失败（${e}），先用抠图卡片代替。`,
    capInfo3d: '这是 Meta SAM 3D 从一张照片生成的 3D 模型，拿着它的手已经自动去掉。',
    shotDone: (src) => ({ model: '抠好了（模型抠图）。捏合可以旋转，说“拆开”看分层。', local: '抠好了（本地抠图）。捏合可以旋转，说“拆开”看分层。',
      box: '背景太杂，没抠干净，先整张做成卡片。换个简单背景再按 P 试试。' })[src],
    noShot: '还没有扫描过物体，先按 P 扫描。', noVideo: '摄像头没开，扫描不了。',
    capName: '扫描的物体', capInfo: '这是摄像头 360° 扫描后重建出来的 3D 模型：形状来自每个角度的轮廓，颜色来自照片，拿着它的手已经自动去掉。', capTitle: '扫描的物体',
    noUnderstand: '我没听懂，可以试试“拆开”“启动”“活塞是干什么的”。',
  },
  en: {
    starting: 'Starting camera…', ready: 'Tracking ready', noCam: (e) => `Camera/model unavailable (${e}); switched to mouse viewpoint`,
    loaded: (t) => `Loaded: ${t}`, welcome: 'AETHER Window: move your head, or press H for help.',
    head: 'Head tracking', mouse: 'Mouse viewpoint', eyeAt: 'eye', stereo: ' · anaglyph', uncal: ' · screen not calibrated (press C)',
    split: ' · Two viewers: left half for the person on the left, right half for the person on the right', calDone: 'Distance calibrated at 50 cm.',
    aiOn: (m) => `AI: ${m}`, aiOff: 'AI: local keywords (no model configured)',
    placeholder: 'Ask AETHER: take the engine apart / what does the piston do?',
    help: `<h2>AETHER Window</h2>
  <p>F fullscreen · C calibrate screen size with a card · D calibrate distance at 50 cm · M mouse viewpoint · S anaglyph · V camera preview · W Window Law demo</p>
  <p>1 engine · 2 solar system · 3 DNA · 4 scanned object · P 360° scan to 3D model (P again to finish) · E export .obj · T two viewers · L 中文 · R reset · hold Space to talk · H close help</p>
  <p>Gestures: pinch thumb and index and drag = rotate; pinch with both hands and pull apart = explode; point with index = highlight</p>`,
    cardCal: 'Hold a bank card or ID card against the screen, resize with [ and ] until it matches, then press Enter',
    lawCard: 'AETHER card 85.6 × 54 mm', lawTitle: 'Law H1 · The Hologram Window Law',
    lawLead: 'With optics alone, a true hologram is a window: you see a point only if the line from your eye through that point passes through the card.',
    lawNote: 'Top view: blue lines are your lines of sight through the card edges (the visible cone). Move your head and whatever leaves the cone disappears. Press W to exit.',
    lawNums: (d, ax, ay, m) => `Eye to card <b>${d} cm</b> · window angle <b>${ax}° × ${ay}°</b><br>To see a whole 1.7 m person in this window, the image must sit about <b>${m} m</b> behind the card`,
    lawIn: 'Object fully inside the window', lawOut: 'Object leaves the window → clipped', lawEye: 'eye', lawPlane: 'card / screen plane',
    shotAim: 'Hold the object inside the frame, front facing the camera; a plain background works best', shotWork: (i, n) => `Cutting out ${i}/${n}…`,
    scanning: (n) => `Slowly turn the object one full circle (counter-clockwise seen from above), then press P · ${n} frames`,
    scanDone: (what, n, tri, src) => `3D model of the ${what} is ready: ${n} angles, ${tri} triangles${src === 'box' ? ' (busy background, some angles are rough)' : ''}. Pinch to turn it; press E to export .obj.`,
    scanFail: 'The outlines did not agree, so no solid shape could be built (turned too fast, or less than a full circle). Showing a single photo instead; press P to scan again more slowly.',
    building: 'Reconstructing the 3D shape…', exported: 'Model file exported.', noModel: 'No scanned 3D model yet.',
    seen: (what, h) => `Recognised: ${what}${h ? ' · hand removed' : ''}`,
    sam3d: (sec) => `SAM 3D is generating the 3D model (usually about a minute) · ${sec} s`,
    sam3dDone: (what) => `3D model of the ${what} is ready (SAM 3D). Pinch to turn it; press E to export .glb.`,
    sam3dFail: (e) => `SAM 3D failed (${e}); showing the cut-out card instead.`,
    capInfo3d: 'A 3D model generated by Meta SAM 3D from a single photo; the hand holding it was removed automatically.',
    shotDone: (src) => ({ model: 'Done (model segmentation). Pinch to rotate, say "take it apart" to see the layers.', local: 'Done (local cut-out). Pinch to rotate, say "take it apart" to see the layers.',
      box: 'Background too busy to cut cleanly, so the whole photo became a card. Try a plainer background and press P again.' })[src],
    noShot: 'Nothing scanned yet. Press P to scan an object first.', noVideo: 'Camera is off, so nothing can be scanned.',
    capName: 'Scanned object', capInfo: 'A 3D model rebuilt from a 360° camera scan: the shape comes from every angle\'s outline, the colour from the photos, and the hand holding it was removed automatically.', capTitle: 'Scanned object',
    noUnderstand: 'Sorry, I did not get that. Try "take it apart", "start", or "what does the piston do?".',
  },
};
const tr = (k, ...a) => { const v = TEXT[cfg.lang][k]; return typeof v === 'function' ? v(...a) : v; };
const label = (p) => (cfg.lang === 'en' ? p.nameEn : p.name) || p.name;
const infoOf = (p) => (cfg.lang === 'en' ? p.infoEn : p.info) || p.info;
const titleOf = (c) => (cfg.lang === 'en' ? c.titleEn : c.title) || c.title;

const $ = (id) => document.getElementById(id);
const ui = { status: $('status'), eye: $('eye'), hover: $('hover'), reply: $('reply'), q: $('q'), mic: $('mic'),
  cam: $('cam'), help: $('help'), cardCal: $('card-cal'), cardBox: $('card-box'), ai: $('ai'), shot: $('shot'), shotMsg: $('shot-msg'),
  split: $('split') };

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
// 当前这扇“窗”的大小：双人模式下每人一半屏幕
function windowCm() { const s = screenSizeCm(); return view?.split ? { W: s.W / 2, H: s.H } : s; }

// 屏幕后方的“盒子房间”：网格墙让大脑立刻读出深度
function buildRoom() {
  room.clear();
  const { W, H } = windowCm();
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
  pivot.add(current.group);
  fitPivot();
  for (const p of current.parts) {
    p.object.traverse((o) => {
      if (o.isMesh) { o.material = o.material.clone(); o.userData.part = p; o.userData.emissive0 = o.material.emissive.clone(); }
    });
  }
  Object.assign(state, { explode: 0, explodeTarget: 0, selected: null, running: false });
  say(tr('loaded', titleOf(current)), false);
}

function setHighlight(p, on) {
  if (!p) return;
  p.object.traverse((o) => {
    if (o.isMesh) o.material.emissive.copy(on ? new THREE.Color(0x1a6fa0) : o.userData.emissive0);
  });
}

// ---------- 离轴投影 ----------
function applyEye(cam, eye) {
  const { W, H } = windowCm();
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
  if (view?.law) layoutLawCard();
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
const filt = { lx: new OneEuro(), ly: new OneEuro(), lz: new OneEuro(), rx: new OneEuro(), ry: new OneEuro(), rz: new OneEuro() };
const view = { mode: 'mouse', stereo: false, law: false, split: false, left: new THREE.Vector3(-3.2, 0, 50), right: new THREE.Vector3(3.2, 0, 50),
  faceSeen: 0, lastIrisPx: 0 };
let mouse = { x: innerWidth / 2, y: innerHeight / 2 };
addEventListener('pointermove', (e) => { mouse = { x: e.clientX, y: e.clientY }; });

function focalPx(videoW) { return cfg.fPx || (videoW / 2) / Math.tan(THREE.MathUtils.degToRad(cfg.hfovDeg / 2)); }

// 从虹膜估计每只眼的 3D 位置（厘米）。虹膜直径近似常数，所以像素直径给出距离。
function eyesFromFace(lm, vw, vh, t, tgt = view, fl = filt) {
  const px = (i) => ({ x: lm[i].x * vw, y: lm[i].y * vh });
  const d = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const irisA = d(px(469), px(471)), irisB = d(px(474), px(476));
  const irisPx = (irisA + irisB) / 2;
  if (irisPx < 2) return false;
  if (tgt === view) view.lastIrisPx = irisPx;
  const f = focalPx(vw);
  const z = f * cfg.irisCm / irisPx;
  const { H } = screenSizeCm();
  const toWorld = (c) => new THREE.Vector3(
    -(c.x - vw / 2) * z / f,                             // 摄像头画面左右与观看者相反
    -(c.y - vh / 2) * z / f + H / 2 + cfg.camAboveCm,    // 摄像头在屏幕上沿
    z);
  const a = toWorld(px(468)), b = toWorld(px(473));
  const [L, R] = a.x < b.x ? [a, b] : [b, a];
  tgt.left.set(fl.lx.filter(L.x, t), fl.ly.filter(L.y, t), fl.lz.filter(L.z, t));
  tgt.right.set(fl.rx.filter(R.x, t), fl.ry.filter(R.y, t), fl.rz.filter(R.z, t));
  return true;
}

// 双人观看：屏幕分成左右两扇窗，左边的人看左半屏，右边的人看右半屏，每扇窗按各自的眼睛做离轴投影
const mkFilt = () => ({ lx: new OneEuro(), ly: new OneEuro(), lz: new OneEuro(), rx: new OneEuro(), ry: new OneEuro(), rz: new OneEuro() });
const viewers = [0, 1].map(() => ({ left: new THREE.Vector3(-3.2, 0, 50), right: new THREE.Vector3(3.2, 0, 50), seen: 0, filt: mkFilt() }));
function trackTwo(list, vw, vh, t) {
  // 摄像头画面没有翻转：画面里越靠右的人，现实中越靠屏幕左边
  const faces = list.slice(0, 2).sort((a, b) => b[1].x - a[1].x);
  const slots = faces.length === 1 ? [faces[0][1].x > 0.5 ? 0 : 1] : faces.map((_, i) => i);
  faces.forEach((lm, i) => { const v = viewers[slots[i]]; if (eyesFromFace(lm, vw, vh, t, v, v.filt)) v.seen = t; });
  const latest = viewers[0].seen >= viewers[1].seen ? viewers[0] : viewers[1];
  if (faces.length) { view.faceSeen = t; view.left.copy(latest.left); view.right.copy(latest.right); }   // 手势指向用
}
function toggleSplit() {
  view.split = !view.split;
  if (view.split) { if (view.law) toggleLaw(); view.stereo = false; }
  face?.setOptions({ numFaces: view.split ? 2 : 1 });
  ui.split.hidden = !view.split;
  buildRoom();
}

function eyesFromMouse() {
  const { W, H } = screenSizeCm();
  const cx = (mouse.x / innerWidth - 0.5) * W * 1.6, cy = -(mouse.y / innerHeight - 0.5) * H * 1.6;
  view.left.set(cx - 3.2, cy, 50); view.right.set(cx + 3.2, cy, 50);
}

// ---------- 手势 ----------
const hands = { pinch: [false, false], cursor: [null, null], lastPinch: null, twoStart: null, hover: null };
const cursorMeshes = [0, 1].map(() => {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.35, 0.5, 32),
    new THREE.MeshBasicMaterial({ color: 0x5fd0ff, transparent: true, opacity: 0.9, depthTest: false }));
  m.renderOrder = 10; m.visible = false; scene.add(m); return m;
});
const raycaster = new THREE.Raycaster();

function handToScreen(p) {   // 手在画面中的位置 → 屏幕平面坐标（厘米），带 1.6 倍增益方便够到边角
  const { W, H } = screenSizeCm();
  return new THREE.Vector3(-(p.x - 0.5) * W * 1.6, -(p.y - 0.5) * H * 1.6, 0.05);
}

function processHands(result) {
  const list = result?.landmarks || [];
  const pinchPts = [];
  for (let i = 0; i < 2; i++) {
    const lm = list[i];
    const mesh = cursorMeshes[i];
    if (!lm) { hands.pinch[i] = false; mesh.visible = false; hands.cursor[i] = null; continue; }
    const size = Math.hypot(lm[0].x - lm[9].x, lm[0].y - lm[9].y);
    const ratio = Math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y) / size;
    hands.pinch[i] = hands.pinch[i] ? ratio < 0.45 : ratio < 0.3;     // 迟滞，避免抖动
    const mid = { x: (lm[4].x + lm[8].x) / 2, y: (lm[4].y + lm[8].y) / 2 };
    const c = handToScreen(hands.pinch[i] ? mid : lm[8]);
    hands.cursor[i] = c;
    mesh.position.copy(c); mesh.visible = true;
    mesh.material.color.set(hands.pinch[i] ? 0xffb84d : 0x5fd0ff);
    if (hands.pinch[i]) pinchPts.push(c);
  }

  if (pinchPts.length === 2) {            // 双手捏合拉开 = 拆解
    const d = pinchPts[0].distanceTo(pinchPts[1]);
    if (!hands.twoStart) hands.twoStart = { d, explode: state.explodeTarget };
    state.explodeTarget = THREE.MathUtils.clamp(hands.twoStart.explode + (d - hands.twoStart.d) / 15, 0, 1);
    hands.lastPinch = null;
  } else {
    hands.twoStart = null;
    if (pinchPts.length === 1) {          // 单手捏合拖动 = 旋转
      const p = pinchPts[0];
      if (hands.lastPinch) {
        state.rotYT += (p.x - hands.lastPinch.x) * 0.25;
        state.rotXT -= (p.y - hands.lastPinch.y) * 0.25;
      }
      hands.lastPinch = p.clone();
    } else hands.lastPinch = null;
  }

  // 食指指向 = 从眼睛穿过屏幕上的光标做射线，命中的零件高亮
  const pointer = !hands.pinch[0] && hands.cursor[0];
  let hit = null;
  if (pointer && current) {
    const eye = view.left.clone().add(view.right).multiplyScalar(0.5);
    raycaster.set(eye, pointer.clone().sub(eye).normalize());
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
    const u = new SpeechSynthesisUtterance(text); u.lang = /[\u4e00-\u9fff]/.test(text) ? 'zh-CN' : 'en-US'; u.rate = 1.05;
    speechSynthesis.speak(u);
  }
}

function findPart(name) {
  if (!current || !name) return null;
  const n = name.toLowerCase(), names = (p) => [p.name, p.nameEn].filter(Boolean).map((x) => x.toLowerCase());
  return current.parts.find((p) => names(p).includes(n)) || current.parts.find((p) => names(p).some((x) => x.includes(n) || n.includes(x))) || null;
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
        if (p) ui.hover.textContent = label(p);
        break;
      }
      case 'clear_select': if (state.selected) setHighlight(state.selected, false); state.selected = null; ui.hover.textContent = ''; break;
      case 'load_scene': if (a.target === 'capture' && !SCENES.capture) say(tr('noShot')); else loadScene(a.target); break;
      case 'capture': startCapture(); break;
      case 'run': state.running = Number(a.amount) > 0; break;
      case 'reset': Object.assign(state, { explodeTarget: 0, rotXT: 0, rotYT: 0, running: false }); applyActions([{ type: 'clear_select' }]); break;
    }
  }
}

// 断网或没有 API key 时的本地关键词兜底：保证现场演示不会卡死
function localParse(text) {
  if (!/[\u4e00-\u9fff]/.test(text)) return localParseEn(text.toLowerCase());
  const acts = [];
  let reply = '';
  if (/拍照|拍一张|拍下|扫描/.test(text)) return { say: '', actions: [{ type: 'capture', amount: 0, target: '' }] };
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
  return { say: reply || tr('noUnderstand'), actions: acts };
}

function localParseEn(text) {
  const acts = [];
  let reply = '';
  if (/photo|picture|capture|scan/.test(text)) return { say: '', actions: [{ type: 'capture', amount: 0, target: '' }] };
  if (/solar|planet/.test(text)) { acts.push({ type: 'load_scene', target: 'solar' }); reply = 'This is the solar system.'; }
  else if (/dna|gene|helix/.test(text)) { acts.push({ type: 'load_scene', target: 'dna' }); reply = 'This is the DNA double helix.'; }
  else if (/engine|motor/.test(text) && current?.id !== 'engine') { acts.push({ type: 'load_scene', target: 'engine' }); reply = 'This is a four-cylinder engine.'; }
  if (/apart|explode|separate|open/.test(text)) { acts.push({ type: 'explode', amount: 1, target: '' }); reply ||= 'Taking it apart.'; }
  if (/back together|assemble|close|put it back/.test(text)) { acts.push({ type: 'explode', amount: 0, target: '' }); reply ||= 'Putting it back together.'; }
  if (/rotate|turn|spin it/.test(text)) { acts.push({ type: 'rotate', amount: 90, target: 'y' }); reply ||= 'Rotating.'; }
  if (/start|run|animate/.test(text)) { acts.push({ type: 'run', amount: 1, target: '' }); reply = 'Started.'; }
  if (/stop|pause/.test(text)) { acts.push({ type: 'run', amount: 0, target: '' }); reply = 'Stopped.'; }
  if (/reset/.test(text)) { acts.push({ type: 'reset', amount: 0, target: '' }); reply = 'Reset.'; }
  const p = current?.parts.find((q) => text.includes(q.nameEn.toLowerCase().replace(/ \d+$/, '')));
  if (p) { acts.push({ type: 'select', amount: 0, target: p.name }); reply = `${p.nameEn}: ${p.infoEn}`; }
  return { say: reply || tr('noUnderstand'), actions: acts };
}

async function runCommand(text) {
  text = text.trim();
  if (!text) return;
  ui.reply.textContent = `“${text}” …`;
  const snapshot = { scene: current?.id, parts: current?.parts.map(label), ui_language: cfg.lang, explode: +state.explodeTarget.toFixed(2),
    running: state.running, selected: state.selected ? label(state.selected) : null };
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
  if (out.say) say(out.say);
}

$('ask').addEventListener('submit', (e) => { e.preventDefault(); runCommand(ui.q.value); ui.q.value = ''; ui.q.blur(); });
ui.q.addEventListener('keydown', (e) => { if (e.key === 'Escape') ui.q.blur(); });   // 回车或 Esc 后把键盘还给快捷键

// 语音输入：Chrome 的 Web Speech API（需要联网）
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, listening = false;
function startListen() {
  if (!SR || listening) return;
  rec = new SR(); rec.lang = cfg.lang === 'en' ? 'en-US' : 'zh-CN'; rec.interimResults = true;
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
$('snap').addEventListener('click', () => startCapture());

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
      if (view.lastIrisPx) { cfg.fPx = 50 * view.lastIrisPx / cfg.irisCm; saveCfg(); say(tr('calDone'), false); }
      break;
    case 'm': view.mode = view.mode === 'mouse' ? 'face' : 'mouse'; break;
    case 's': view.stereo = !view.stereo; break;
    case 'w': toggleLaw(); break;
    case 'v': ui.cam.classList.toggle('show'); break;
    case 'h': ui.help.hidden = !ui.help.hidden; break;
    case 'r': applyActions([{ type: 'reset' }]); break;
    case '1': loadScene('engine'); break;
    case '2': loadScene('solar'); break;
    case '3': loadScene('dna'); break;
    case '4': applyActions([{ type: 'load_scene', target: 'capture' }]); break;
    case 'p': startCapture(); break;
    case 'e': exportModel(); break;
    case 't': toggleSplit(); break;
    case 'l': cfg.lang = cfg.lang === 'en' ? 'zh' : 'en'; saveCfg(); applyLang(); if (current) say(tr('loaded', titleOf(current)), false); break;
  }
});
addEventListener('keyup', (e) => { if (e.code === 'Space' && document.activeElement !== ui.q) stopListen(); });

function drawCard() {   // ISO/IEC 7810 ID-1：85.60 × 53.98 mm，也正是 AETHER 卡片的尺寸
  ui.cardBox.style.width = `${8.56 * cfg.pxPerCm}px`;
  ui.cardBox.style.height = `${5.398 * cfg.pxPerCm}px`;
}

// ---------- 摄像头与追踪 ----------
let face = null, hand = null;
let statusNow = ['starting'];
function setStatus(...k) { statusNow = k; ui.status.textContent = tr(...k); }
async function initTracking() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, facingMode: 'user' } });
    ui.cam.srcObject = stream;
    await ui.cam.play();
    const fileset = await FilesetResolver.forVisionTasks('/vendor/mediapipe/wasm');
    const faceLm = await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: '/models/face_landmarker.task', delegate: 'GPU' }, runningMode: 'VIDEO', numFaces: 1 });
    const handLm = await HandLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: '/models/hand_landmarker.task', delegate: 'GPU' }, runningMode: 'VIDEO', numHands: 2 });
    face = faceLm; hand = handLm;   // 两个都就绪后再启用，避免追踪循环拿到一半
    view.mode = 'face';
    setStatus('ready');
  } catch (err) {
    setStatus('noCam', err.name || err);
  }
}

let frame = 0, lastVideoTime = -1;
function track(now) {
  const v = ui.cam;
  if (!face || v.readyState < 2 || v.currentTime === lastVideoTime) return;
  lastVideoTime = v.currentTime;
  const fr = face.detectForVideo(v, now);
  if (view.split) trackTwo(fr.faceLandmarks || [], v.videoWidth, v.videoHeight, now);
  else if (fr.faceLandmarks?.[0] && eyesFromFace(fr.faceLandmarks[0], v.videoWidth, v.videoHeight, now)) view.faceSeen = now;
  if (frame++ % 2 === 0) processHands(hand.detectForVideo(v, now));   // 手势隔帧跑，省算力给头部追踪
}

// ---------- 窗口定律演示（H1） ----------
// 卡片放在屏幕平面上（z = 0）。眼睛 → 影像点的连线必须穿过卡片才看得到，
// 这等价于：只在屏幕上卡片那一块矩形里渲染。所以演示里的裁剪不是特效，就是 H1 本身。
const CARD = { w: 8.56, h: 5.398 };
const lawTop = $('law-top'), lawCtx = lawTop.getContext('2d');
function toggleLaw() {
  view.law = !view.law;
  $('law').hidden = !view.law;
  if (view.law) { if (view.split) toggleSplit(); view.stereo = false; layoutLawCard(); }
  fitPivot();
}
function layoutLawCard() {
  const el = $('law-card');
  el.style.width = `${CARD.w * cfg.pxPerCm}px`; el.style.height = `${CARD.h * cfg.pxPerCm}px`;
}
function fitPivot() {   // 演示时把物体缩到卡片大小附近，浮在卡片前 2 cm
  if (!current) return;
  pivot.scale.setScalar(1); pivot.updateMatrixWorld(true);
  const r = new THREE.Box3().setFromObject(current.group).getBoundingSphere(new THREE.Sphere()).radius || 1;
  if (view.law) { pivot.scale.setScalar(Math.min(1, 4.6 / r)); pivot.position.set(0, 0, 3); }   // 故意比卡片略大，转头时能看到被窗口裁掉
  else pivot.position.set(0, 0, Math.max(0, cfg.floatMaxCm - r * 0.75));
}
function drawLaw(eye) {
  const d = Math.max(eye.z, 1);
  const angX = 2 * Math.atan(CARD.w / 2 / d) * 180 / Math.PI, angY = 2 * Math.atan(CARD.h / 2 / d) * 180 / Math.PI;
  const humanAt = 170 / (CARD.h / d) / 100;
  $('law-nums').innerHTML = tr('lawNums', d.toFixed(0), angX.toFixed(1), angY.toFixed(1), humanAt.toFixed(1));
  // 俯视图：x 向右，z 向下（朝观看者）
  const c = lawCtx, Wc = lawTop.width, Hc = lawTop.height;
  const sx = Wc / 60, x0 = Wc / 2, z0 = Hc * 0.42, sz = (Hc - z0 - 14) / Math.max(d, 30);
  const P = (x, z) => [x0 + x * sx, z0 + z * sz];
  c.clearRect(0, 0, Wc, Hc);
  c.strokeStyle = '#2a3442'; c.lineWidth = 1; c.beginPath(); c.moveTo(0, z0); c.lineTo(Wc, z0); c.stroke();   // 屏幕平面
  const [ex, ez] = P(eye.x, d);
  const edges = [-CARD.w / 2, CARD.w / 2];
  const far = (xe) => { const [px, pz] = P(xe, 0); const t = ez / Math.max(ez - pz, 1e-3); return [ex + (px - ex) * t, 0]; };
  const fl = far(edges[0]), fr = far(edges[1]);
  c.fillStyle = 'rgba(95,208,255,0.12)'; c.beginPath(); c.moveTo(ex, ez); c.lineTo(...fl); c.lineTo(...fr); c.closePath(); c.fill();
  c.strokeStyle = '#5fd0ff'; c.lineWidth = 1.2;
  for (const f of [fl, fr]) { c.beginPath(); c.moveTo(ex, ez); c.lineTo(...f); c.stroke(); }
  c.strokeStyle = '#5fd0ff'; c.lineWidth = 4; c.beginPath(); c.moveTo(...P(edges[0], 0)); c.lineTo(...P(edges[1], 0)); c.stroke();   // 卡片
  // 物体：包围盒在俯视图上的投影，按是否落在可见锥里着色
  if (current) {
    const box = new THREE.Box3().setFromObject(pivot);
    const inCone = (x, z) => { const t = (d - 0) / Math.max(d - z, 1e-3); const xs = eye.x + (x - eye.x) * t; return Math.abs(xs) <= CARD.w / 2; };
    const corners = [[box.min.x, box.min.z], [box.max.x, box.min.z], [box.max.x, box.max.z], [box.min.x, box.max.z]];
    const allIn = corners.every(([x, z]) => inCone(x, z));
    const [ax, az] = P(box.min.x, box.max.z), [bx, bz] = P(box.max.x, box.min.z);
    c.strokeStyle = allIn ? '#7fe0a0' : '#ffb84d'; c.lineWidth = 1.5; c.strokeRect(ax, az, bx - ax, bz - az);
    c.fillStyle = allIn ? '#7fe0a0' : '#ffb84d'; c.font = '11px system-ui';
    c.fillText(allIn ? tr('lawIn') : tr('lawOut'), 8, Hc - 8);
  }
  c.fillStyle = '#e8edf3'; c.beginPath(); c.arc(ex, Math.min(ez, Hc - 6), 4, 0, Math.PI * 2); c.fill();
  c.font = '11px system-ui'; c.fillText(tr('lawEye'), ex + 6, Math.min(ez, Hc - 6) - 4); c.fillText(tr('lawPlane'), 6, z0 - 6);
}

// ---------- 主循环 ----------
const clock = new THREE.Clock();
function loop(now) {
  requestAnimationFrame(loop);
  track(now);
  const faceOk = view.mode === 'face' && now - view.faceSeen < 500;
  if (!faceOk) eyesFromMouse();

  // 平滑动画
  state.explode += (state.explodeTarget - state.explode) * 0.12;
  state.rotX += (state.rotXT - state.rotX) * 0.15;
  state.rotY += (state.rotYT - state.rotY) * 0.15;
  pivot.rotation.set(state.rotX, state.rotY, 0);
  if (current) {
    if (!current.skipExplode) for (const p of current.parts) p.object.position.copy(p.base).addScaledVector(p.dir, state.explode);
    current.update(clock.getElapsedTime(), state);
  }

  const mid = view.left.clone().add(view.right).multiplyScalar(0.5);
  ui.eye.textContent = `${faceOk ? tr('head') : tr('mouse')} · ${tr('eyeAt')} (${mid.x.toFixed(1)}, ${mid.y.toFixed(1)}, ${mid.z.toFixed(1)}) cm`
    + `${view.stereo ? tr('stereo') : ''}${view.split ? tr('split') : ''}${cfg.pxPerCm === DEFAULTS.pxPerCm ? tr('uncal') : ''}`;
  if (!state.selected) ui.hover.textContent = hands.hover ? label(hands.hover) : '';

  if (view.split) {
    renderSplit(now, mid);
  } else if (view.law) {
    applyEye(camera, mid);
    renderer.setScissorTest(false); renderer.setClearColor(0x000000); renderer.clear();
    const w = CARD.w * cfg.pxPerCm, h = CARD.h * cfg.pxPerCm;
    renderer.setScissor((innerWidth - w) / 2, (innerHeight - h) / 2, w, h);
    renderer.setScissorTest(true); renderer.render(scene, camera); renderer.setScissorTest(false);
    drawLaw(mid);
  } else if (view.stereo) {
    applyEye(camera, view.left); renderer.setRenderTarget(rtL); renderer.render(scene, camera);
    applyEye(camera, view.right); renderer.setRenderTarget(rtR); renderer.render(scene, camera);
    renderer.setRenderTarget(null); renderer.render(compScene, compCam);
  } else {
    applyEye(camera, mid); renderer.render(scene, camera);
  }
}

// 双人：左右两半各是一扇窗。把世界坐标平移到那半屏的中心，再用半屏大小做离轴投影
function renderSplit(now, mid) {
  const { W } = screenSizeCm();
  const halfPx = innerWidth / 2;
  renderer.setScissorTest(true);
  for (let i = 0; i < 2; i++) {
    const cx = (i === 0 ? -1 : 1) * W / 4;
    const v = viewers[i];
    const ok = view.mode === 'face' && now - v.seen < 500;
    const eye = ok ? v.left.clone().add(v.right).multiplyScalar(0.5) : mid.clone().setX(mid.x + cx);
    eye.x -= cx;
    applyEye(camera, eye);
    renderer.setViewport(i * halfPx, 0, halfPx, innerHeight);
    renderer.setScissor(i * halfPx, 0, halfPx, innerHeight);
    renderer.render(scene, camera);
  }
  renderer.setScissorTest(false);
  renderer.setViewport(0, 0, innerWidth, innerHeight);
}

// ---------- 360° 扫描 → 3D 模型 ----------
// 物体检测模型（COCO 80 类）给的是英文标签，常见的几类翻成中文
const COCO_ZH = { cup: '杯子', bottle: '瓶子', 'wine glass': '酒杯', bowl: '碗', 'cell phone': '手机', book: '书', mouse: '鼠标',
  remote: '遥控器', keyboard: '键盘', scissors: '剪刀', 'teddy bear': '泰迪熊', banana: '香蕉', apple: '苹果', orange: '橙子',
  toothbrush: '牙刷', vase: '花瓶', clock: '时钟', 'sports ball': '球', laptop: '笔记本电脑', 'potted plant': '盆栽', spoon: '勺子',
  fork: '叉子', knife: '刀', donut: '甜甜圈', sandwich: '三明治', cake: '蛋糕', carrot: '胡萝卜', broccoli: '西兰花', 'hair drier': '吹风机',
  handbag: '手提包', backpack: '背包', umbrella: '雨伞', tie: '领带', 'baseball bat': '球棒', 'tennis racket': '网球拍', kite: '风筝',
  frisbee: '飞盘', skateboard: '滑板', car: '汽车', truck: '卡车', airplane: '飞机', bird: '鸟', cat: '猫', dog: '狗' };
// 第一次按 P：倒数 3 秒后开始连拍（每 250 ms 一张，最长 15 秒）；再按 P 结束。少于 4 张就退回单张卡片。
const SCAN = { every: 250, maxMs: 15000, keep: 30 };
let capturing = false, stopScan = false;
async function startCapture() {
  if (capturing) { stopScan = true; return; }
  const v = ui.cam;
  if (!v.srcObject || v.readyState < 2) { say(tr('noVideo')); return; }
  capturing = true; stopScan = false;
  const hadPreview = ui.cam.classList.contains('show');
  ui.cam.classList.add('show', 'big');
  ui.shot.hidden = false;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    for (let n = 3; n > 0 && !stopScan; n--) { ui.shotMsg.textContent = `${tr('shotAim')} · ${n}`; await wait(1000); }
    stopScan = false;
    if (aiStatus?.model3d) { await captureSam3d(v); return; }
    let frames = [];
    const t0 = performance.now();
    while (!stopScan && performance.now() - t0 < SCAN.maxMs) {
      frames.push(grabFrame(v));
      ui.shotMsg.textContent = tr('scanning', frames.length);
      await wait(SCAN.every);
    }
    frames = frames.slice(0, loopClose(frames));
    if (frames.length > SCAN.keep) frames = Array.from({ length: SCAN.keep }, (_, i) => frames[Math.floor(i * frames.length / SCAN.keep)]);

    const masks = [], handMasks = [], votes = {};
    let worst = 'model', anyHand = false;
    for (let i = 0; i < frames.length; i++) {
      ui.shotMsg.textContent = tr('shotWork', i + 1, frames.length);
      const r = await analyzeFrame(frames[i], !!aiStatus?.segment);
      masks.push(r.mask); handMasks.push(r.handMask);
      if (r.label) { const v = (votes[r.label] ||= { s: 0, n: 0 }); v.s += r.score; v.n++; }
      if (r.hands) anyHand = true;
      if (r.source === 'box' || (r.source === 'local' && worst === 'model')) worst = r.source;
    }
    // 每张都投票，分数加起来最高的标签就是这个物体
    // 至少五分之一的角度都认成同一样东西才算数，避免偶尔一帧认错
    const labelEn = Object.entries(votes).filter(([, v]) => v.n >= Math.max(2, frames.length * 0.2)).sort((a, b) => b[1].s - a[1].s)[0]?.[0] || '';
    const nameZh = labelEn ? (COCO_ZH[labelEn] || labelEn) : TEXT.zh.capName, nameEn = labelEn || TEXT.en.capName;
    ui.shotMsg.textContent = `${tr('seen', cfg.lang === 'en' ? nameEn : nameZh, anyHand)} · ${tr('building')}`;
    await wait(30);   // 让提示先画出来
    const names = { name: nameZh, info: TEXT.zh.capInfo, title: nameZh };
    let built = frames.length >= 6 ? buildModelScene(frames, masks, names, handMasks) : null;
    const ok = !!built;
    if (!built) built = buildCaptureScene(frames[0], masks[0], names);
    built.parts[0].nameEn = nameEn; built.parts[0].infoEn = TEXT.en.capInfo; built.titleEn = nameEn;
    SCENES.capture = () => built;
    loadScene('capture');
    say(ok ? tr('scanDone', cfg.lang === 'en' ? nameEn : nameZh, frames.length, built.stats.triangles, worst) : tr('scanFail'));
  } finally {
    ui.shot.hidden = true;
    ui.cam.classList.remove('big');
    if (!hadPreview) ui.cam.classList.remove('show');
    capturing = false; stopScan = false;
  }
}

// 配了 SAM 3D：不用转一圈，拍一张就够。认出物体、去掉手、抠图，再让 SAM 3D 生成带贴图的网格
async function captureSam3d(v) {
  const hi = grabFrame(v, 768), lo = grabFrame(v);
  const r = await analyzeFrame(lo, !!aiStatus?.segment);
  const labelEn = r.label || '';
  const nameZh = labelEn ? (COCO_ZH[labelEn] || labelEn) : TEXT.zh.capName, nameEn = labelEn || TEXT.en.capName;
  const what = cfg.lang === 'en' ? nameEn : nameZh;
  const names = { name: nameZh, info: TEXT.zh.capInfo3d, title: nameZh };
  const t0 = performance.now();
  const tick = setInterval(() => { ui.shotMsg.textContent = `${tr('seen', what, r.hands)} · ${tr('sam3d', Math.round((performance.now() - t0) / 1000))}`; }, 500);
  let built = null, err = null;
  try { built = await generate3D(hi, r.mask, labelEn, names); } catch (e) { err = e; } finally { clearInterval(tick); }
  if (!built) built = buildCaptureScene(lo, r.mask, names);
  built.parts[0].nameEn = nameEn; built.parts[0].infoEn = TEXT.en.capInfo3d; built.titleEn = nameEn;
  SCENES.capture = () => built;
  loadScene('capture');
  say(err ? tr('sam3dFail', String(err?.message || err)) : tr('sam3dDone', what));
}

function exportModel() {
  const m = SCENES.capture?.();
  if (!m?.mesh && !m?.glb) { say(tr('noModel')); return; }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(m.glb ? new Blob([m.glb], { type: 'model/gltf-binary' }) : new Blob([toOBJ(m.mesh)], { type: 'text/plain' }));
  a.download = m.glb ? 'aether-scan.glb' : 'aether-scan.obj';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  say(tr('exported'), false);
}

function applyLang() {
  document.documentElement.lang = cfg.lang === 'en' ? 'en' : 'zh-CN';
  ui.help.innerHTML = tr('help');
  ui.q.placeholder = tr('placeholder');
  $('card-box').querySelector('span').textContent = tr('cardCal');
  $('law-card').querySelector('span').textContent = tr('lawCard');
  $('law-title').textContent = tr('lawTitle');
  $('law-lead').textContent = tr('lawLead');
  $('law-note').textContent = tr('lawNote');
  setStatus(...statusNow);
  showAi();
}

let aiStatus = null;
function showAi() {
  if (!aiStatus) return;
  ui.ai.textContent = aiStatus.chat ? tr('aiOn', `${aiStatus.chat.provider} · ${aiStatus.chat.model}`) : tr('aiOff');
  if (aiStatus.model3d) ui.ai.textContent += ` · 3D: ${aiStatus.model3d.model}`;
}
fetch('/api/status').then((r) => r.json()).then((s) => { aiStatus = s; showAi(); }).catch(() => {});

resize();
applyLang();
loadScene('engine');
say(tr('welcome'), false);
requestAnimationFrame(loop);
initTracking();
window.aether = { state, view, cfg, runCommand, applyActions, localParse };   // 方便调试
