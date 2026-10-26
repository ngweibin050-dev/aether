// 拍照 → 抠出物体 → 变成一张有厚度的 3D 卡片，放进窗口里。
// 抠图顺序：服务器（/api/segment，SAM 3.1 接在那里）→ 本地 MediaPipe 点选抠图（magic_touch，和 SAM 一样“点一下物体”）
// → 颜色抠图（只靠和背景的颜色差，背景杂或颜色接近时会出洞）→ 整张圆角卡片。
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FilesetResolver, InteractiveSegmenter, ObjectDetector, HandLandmarker } from '@mediapipe/tasks-vision';

const SIZE = 256;   // 抠图分辨率，够做卡片又够快

// 取摄像头画面中间的正方形，左右翻转成“照镜子”的样子（和用户在预览里看到的一致）
export function grabFrame(video, size = SIZE) {
  const vw = video.videoWidth, vh = video.videoHeight;
  const s = Math.min(vw, vh) * 0.7;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  g.translate(size, 0); g.scale(-1, 1);
  g.drawImage(video, (vw - s) / 2, (vh - s) / 2, s, s, 0, 0, size, size);
  return c;
}

// 返回 { mask: 每个像素 0~1 的 Float32Array, source: 'model' | 'local' | 'box' }
export async function segment(img, useModel = true, point = [0.5, 0.5]) {
  if (useModel) try {
    const image = img.toDataURL('image/png').split(',')[1];
    const r = await fetch('/api/segment', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ image, point, prompt: '' }),
      signal: AbortSignal.timeout(15000),
    });
    if (r.ok) {
      const { mask } = await r.json();
      return { mask: await decodeMask(mask), source: 'model' };
    }
  } catch { /* 走本地兜底 */ }
  try {
    const m = await magicSegment(img, point);
    if (m) return { mask: m, source: 'local' };
  } catch (err) { console.warn('magic_touch 不可用，改用颜色抠图', err); }
  return localSegment(img);
}

let magic = null;
async function magicSegment(img, point) {
  magic ||= FilesetResolver.forVisionTasks('/vendor/mediapipe/wasm').then((fs) => InteractiveSegmenter.createFromOptions(fs, {
    baseOptions: { modelAssetPath: '/models/magic_touch.tflite', delegate: 'GPU' },
    outputCategoryMask: false, outputConfidenceMasks: true,
  }));
  const seg = await magic;
  const res = seg.segment(img, { keypoint: { x: point[0], y: point[1] } });
  const cm = res.confidenceMasks?.[0];
  if (!cm) return null;
  const w = cm.width, h = cm.height, conf = cm.getAsFloat32Array();
  const N = SIZE, fg = new Uint8Array(N * N);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    fg[y * N + x] = conf[Math.floor(y * h / N) * w + Math.floor(x * w / N)] > 0.5 ? 1 : 0;
  }
  res.close?.();
  const comp = largestNearCenter(fg, N, point);
  if (!comp) return null;
  const mask = fillHoles(comp, N, 0.004);
  let area = 0;
  for (let i = 0; i < mask.length; i++) area += mask[i];
  if (area / (N * N) < 0.02 || area / (N * N) > 0.95) return null;
  return feather(mask, N);
}

// ---------- 自动识别物体 + 去掉手 ----------
// 1. 物体检测（EfficientDet，COCO 80 类）找出画面里不是“人”的那个物体，认出它是什么，用它的中心当抠图的点；
// 2. 点选抠图抠出物体；
// 3. 手部关键点画出手指和手掌的形状，从轮廓里挖掉，所以拿着物体的手不会进 3D 模型。
let detector = null, handImg = null;
const fileset = () => (fileset.p ||= FilesetResolver.forVisionTasks('/vendor/mediapipe/wasm'));
async function getDetector() {
  detector ||= fileset().then((fs) => ObjectDetector.createFromOptions(fs, {
    baseOptions: { modelAssetPath: '/models/efficientdet_lite0.tflite', delegate: 'GPU' },
    scoreThreshold: 0.25, maxResults: 5, categoryDenylist: ['person'],
  }));
  return detector;
}
async function getHands() {
  handImg ||= fileset().then((fs) => HandLandmarker.createFromOptions(fs, {
    baseOptions: { modelAssetPath: '/models/hand_landmarker.task', delegate: 'GPU' }, numHands: 2,
  }));
  return handImg;
}

export async function analyzeFrame(img, useModel) {
  let point = [0.5, 0.5], label = '', score = 0;
  try {
    const det = (await getDetector()).detect(img).detections || [];
    // 离画面中心越近、分数越高越可能是用户举着的那个东西
    let best = null, bestScore = -1;
    for (const d of det) {
      const b = d.boundingBox, c = d.categories?.[0];
      if (!b || !c) continue;
      const x = (b.originX + b.width / 2) / SIZE, y = (b.originY + b.height / 2) / SIZE;
      const sc = c.score * Math.exp(-((x - 0.5) ** 2 + (y - 0.5) ** 2) * 6);
      if (sc > bestScore) { bestScore = sc; best = { x, y, label: c.categoryName, score: c.score }; }
    }
    if (best) { point = [best.x, best.y]; label = best.label; score = best.score; }
  } catch (err) { console.warn('物体检测不可用', err); }

  let hands = [];
  try { hands = (await getHands()).detect(img).landmarks || []; } catch (err) { console.warn('手部检测不可用', err); }
  const handMask = hands.length ? drawHands(hands) : null;
  // 抠图的点如果落在手上，就沿着离手掌的方向往外挪，直到离开手
  if (handMask) for (let i = 0; i < 20 && handMask[Math.floor(point[1] * SIZE) * SIZE + Math.floor(point[0] * SIZE)]; i++) {
    const w = hands[0][0], dx = point[0] - w.x, dy = point[1] - w.y, len = Math.hypot(dx, dy) || 1;
    point = [Math.min(0.98, Math.max(0.02, point[0] + dx / len * 0.02)), Math.min(0.98, Math.max(0.02, point[1] + dy / len * 0.02))];
  }

  const out = await segment(img, useModel, point);
  if (handMask) {
    for (let i = 0; i < out.mask.length; i++) if (handMask[i]) out.mask[i] = 0;
    const N = SIZE, bin = new Uint8Array(N * N);
    for (let i = 0; i < bin.length; i++) bin[i] = out.mask[i] > 0.5 ? 1 : 0;
    const comp = largestNearCenter(bin, N, point);   // 挖掉手以后，只留物体本身那一块
    if (comp) out.mask = feather(comp, N);
  }
  return { ...out, label, score, hands: hands.length, handMask };
}

// 手的形状：沿 20 根骨头画粗线，再把手掌五个点围起来填满。线宽按手的大小定
const BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];
function drawHands(hands) {
  const N = SIZE, c = document.createElement('canvas');
  c.width = c.height = N;
  const g = c.getContext('2d');
  g.fillStyle = g.strokeStyle = '#fff'; g.lineCap = 'round'; g.lineJoin = 'round';
  for (const lm of hands) {
    const P = (i) => [lm[i].x * N, lm[i].y * N];
    const size = Math.hypot(P(0)[0] - P(9)[0], P(0)[1] - P(9)[1]);
    g.lineWidth = Math.max(4, size * 0.32);
    for (const [a, b] of BONES) { g.beginPath(); g.moveTo(...P(a)); g.lineTo(...P(b)); g.stroke(); }
    g.beginPath(); [0, 1, 5, 9, 13, 17].forEach((i, k) => (k ? g.lineTo(...P(i)) : g.moveTo(...P(i)))); g.closePath(); g.fill();
  }
  const d = g.getImageData(0, 0, N, N).data, m = new Uint8Array(N * N);
  for (let i = 0; i < m.length; i++) m[i] = d[i * 4] > 0 ? 1 : 0;
  return m;
}

async function decodeMask(b64) {
  const im = new Image();
  im.src = `data:image/png;base64,${b64}`;
  await im.decode();
  const c = document.createElement('canvas');
  c.width = c.height = SIZE;
  const g = c.getContext('2d');
  g.drawImage(im, 0, 0, SIZE, SIZE);
  const d = g.getImageData(0, 0, SIZE, SIZE).data;
  const m = new Float32Array(SIZE * SIZE);
  for (let i = 0; i < m.length; i++) m[i] = d[i * 4] > 127 ? 1 : 0;
  return m;
}

export function localSegment(img) {
  const N = SIZE, d = img.getContext('2d').getImageData(0, 0, N, N).data;
  const px = (i) => [d[i * 4], d[i * 4 + 1], d[i * 4 + 2]];
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

  // 1. 边缘一圈的颜色当背景样本，k-means 聚成 5 类
  const border = [];
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (x < 8 || y < 8 || x >= N - 8 || y >= N - 8) if ((x + y) % 3 === 0) border.push(px(y * N + x));
  }
  let centers = [0, 1, 2, 3, 4].map((k) => border[Math.floor(k * border.length / 5)].slice());
  for (let it = 0; it < 10; it++) {
    const sum = centers.map(() => [0, 0, 0, 0]);
    for (const p of border) {
      let best = 0;
      for (let k = 1; k < centers.length; k++) if (dist(p, centers[k]) < dist(p, centers[best])) best = k;
      sum[best][0] += p[0]; sum[best][1] += p[1]; sum[best][2] += p[2]; sum[best][3]++;
    }
    centers = sum.map((s, k) => (s[3] ? [s[0] / s[3], s[1] / s[3], s[2] / s[3]] : centers[k]));
  }
  const bgDist = (p) => Math.min(...centers.map((c) => dist(p, c)));

  // 2. 阈值取边缘像素自身离背景模型距离的 95 分位再放大，背景越杂阈值越高
  const bd = border.map(bgDist).sort((a, b) => a - b);
  const T = Math.max(28, bd[Math.floor(bd.length * 0.95)] * 1.6);
  let fg = new Uint8Array(N * N);
  for (let i = 0; i < N * N; i++) fg[i] = bgDist(px(i)) > T ? 1 : 0;

  // 3. 形态学闭运算，补上小缝
  fg = erode(dilate(fg, N, 3), N, 3);

  // 4. 只留离中心最近的那一块连通区域
  const comp = largestNearCenter(fg, N);
  if (!comp) return boxMask();
  // 5. 填洞：从边缘出发淹不到的地方都算物体
  const mask = fillHoles(comp, N);
  let area = 0;
  for (let i = 0; i < mask.length; i++) area += mask[i];
  const frac = area / (N * N);
  if (frac < 0.03 || frac > 0.85) return boxMask();   // 抠得太小或太大都不可信，改用整张圆角卡片
  return { mask: feather(mask, N), source: 'local' };
}

function dilate(a, N, r) {
  const o = new Uint8Array(a.length);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (!a[y * N + x]) continue;
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
      const X = x + dx, Y = y + dy;
      if (X >= 0 && Y >= 0 && X < N && Y < N) o[Y * N + X] = 1;
    }
  }
  return o;
}
function erode(a, N, r) {
  const inv = a.map((v) => 1 - v);
  return dilate(inv, N, r).map((v) => 1 - v);
}

function largestNearCenter(fg, N, point = [0.5, 0.5]) {
  const label = new Int32Array(N * N).fill(-1);
  let best = null, bestScore = -Infinity;
  const stack = [];
  for (let s = 0; s < N * N; s++) {
    if (!fg[s] || label[s] >= 0) continue;
    const pix = [];
    stack.push(s); label[s] = s;
    let sx = 0, sy = 0;
    while (stack.length) {
      const i = stack.pop(); pix.push(i);
      const x = i % N, y = (i / N) | 0; sx += x; sy += y;
      for (const j of [i - 1, i + 1, i - N, i + N]) {
        if (j < 0 || j >= N * N || label[j] >= 0 || !fg[j]) continue;
        if ((j === i - 1 && x === 0) || (j === i + 1 && x === N - 1)) continue;
        label[j] = s; stack.push(j);
      }
    }
    const cx = sx / pix.length / N - point[0], cy = sy / pix.length / N - point[1];
    const score = pix.length * Math.exp(-(cx * cx + cy * cy) * 8);   // 面积大、离中心近的优先
    if (score > bestScore) { bestScore = score; best = pix; }
  }
  if (!best || best.length < 50) return null;
  const out = new Uint8Array(N * N);
  for (const i of best) out[i] = 1;
  return out;
}

function fillHoles(a, N, maxHole = 1) {
  const seen = new Uint8Array(N * N), stack = [];
  for (let i = 0; i < N; i++) for (const j of [i, (N - 1) * N + i, i * N, i * N + N - 1]) {
    if (!a[j] && !seen[j]) { seen[j] = 1; stack.push(j); }
  }
  while (stack.length) {
    const i = stack.pop(), x = i % N;
    for (const j of [i - 1, i + 1, i - N, i + N]) {
      if (j < 0 || j >= N * N || seen[j] || a[j]) continue;
      if ((j === i - 1 && x === 0) || (j === i + 1 && x === N - 1)) continue;
      seen[j] = 1; stack.push(j);
    }
  }
  const out = new Uint8Array(N * N);
  for (let i = 0; i < N * N; i++) out[i] = seen[i] ? 0 : 1;
  if (maxHole >= 1) return out;
  // 只填小洞：大的洞是真的（比如杯柄中间的空隙），要保留
  const lim = maxHole * N * N, done = new Uint8Array(N * N);
  for (let s0 = 0; s0 < N * N; s0++) {
    if (a[s0] || seen[s0] || done[s0]) continue;
    const pix = [s0]; done[s0] = 1;
    for (let q = 0; q < pix.length; q++) {
      const i = pix[q], x = i % N;
      for (const j of [i - 1, i + 1, i - N, i + N]) {
        if (j < 0 || j >= N * N || done[j] || a[j] || seen[j]) continue;
        if ((j === i - 1 && x === 0) || (j === i + 1 && x === N - 1)) continue;
        done[j] = 1; pix.push(j);
      }
    }
    if (pix.length > lim) for (const i of pix) out[i] = 0;
  }
  return out;
}

function feather(a, N) {   // 3×3 均值，让边缘不那么锯齿
  const m = new Float32Array(N * N);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    let s = 0, n = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const X = x + dx, Y = y + dy;
      if (X >= 0 && Y >= 0 && X < N && Y < N) { s += a[Y * N + X]; n++; }
    }
    m[y * N + x] = s / n;
  }
  return m;
}

function boxMask() {   // 兜底的兜底：整张照片做成圆角卡片
  const N = SIZE, m = new Float32Array(N * N), r = N * 0.08, pad = N * 0.04;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const qx = Math.max(Math.abs(x - N / 2) - (N / 2 - pad - r), 0), qy = Math.max(Math.abs(y - N / 2) - (N / 2 - pad - r), 0);
    m[y * N + x] = Math.hypot(qx, qy) <= r ? 1 : 0;
  }
  return { mask: m, source: 'box' };
}

// 把照片和 mask 变成场景：多层同形状的薄片叠成约 0.5 cm 厚的“卡片”，拆解时各层沿 z 散开
export function buildCaptureScene(img, mask, names) {
  const N = SIZE;
  let x0 = N, y0 = N, x1 = 0, y1 = 0;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (mask[y * N + x] > 0.5) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  }
  if (x1 <= x0 || y1 <= y0) { x0 = 0; y0 = 0; x1 = N - 1; y1 = N - 1; }
  const pad = 4;
  x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad); x1 = Math.min(N - 1, x1 + pad); y1 = Math.min(N - 1, y1 + pad);
  const w = x1 - x0 + 1, h = y1 - y0 + 1;

  const src = img.getContext('2d').getImageData(x0, y0, w, h);
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) src.data[(y * w + x) * 4 + 3] = Math.round(255 * mask[(y + y0) * N + x + x0]);
  c.getContext('2d').putImageData(src, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;

  const scale = 8 / Math.max(w, h);   // 最长边 8 cm
  const geo = new THREE.PlaneGeometry(w * scale, h * scale);
  const group = new THREE.Group();
  const card = new THREE.Group();
  const LAYERS = 8, GAP = 0.07;
  const layers = [];
  for (let i = 0; i < LAYERS; i++) {
    const edge = i > 0 && i < LAYERS - 1;
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      map: tex, alphaTest: 0.5, side: THREE.DoubleSide, metalness: 0, roughness: 0.85,
      color: edge ? 0x9a9a9a : 0xffffff,   // 中间层暗一点，侧面看像有厚度
    }));
    m.position.z = (LAYERS / 2 - i) * GAP;
    card.add(m);
    layers.push({ m, z: m.position.z, k: i - (LAYERS - 1) / 2 });
  }
  group.add(card);
  const parts = [{ name: names.name, info: names.info, object: card, base: card.position.clone(), dir: new THREE.Vector3() }];
  return {
    id: 'capture', title: names.title, group, parts, skipExplode: true,
    update(t, s) {
      for (const l of layers) l.m.position.z = l.z + s.explode * l.k * 0.9;
      if (s.running) card.rotation.y = t * 0.8;
    },
  };
}

// ---------- 360° 扫描 → 3D 模型 ----------
// 用户拿着物体在镜头前原地转一圈（从上往下看逆时针），我们按固定间隔连拍并逐张抠图。
// 重建方法是“视觉外壳”（shape from silhouette）：每张照片的轮廓都是物体在那个角度的投影，
// 空间里的一个点只有在所有角度都落在轮廓内，才属于物体。把这些点留下，就雕出了物体的立体形状，
// 再用“表面网”提取网格，每个顶点从最正对它的那几张照片取颜色。
// 假设：转速大致均匀（第 k 张对应 k/N × 360°），镜头离物体比物体本身大很多（近似正交投影）。
// 局限：凹进去的地方（杯子内部）从轮廓上看不出来，会被填平。

// 找“转满一圈”的那一帧：后半段里和第一张最像的那张
export function loopClose(frames) {
  const n = frames.length;
  if (n < 8) return n;
  const sig = frames.map((c) => {
    const s = document.createElement('canvas'); s.width = s.height = 24;
    s.getContext('2d').drawImage(c, 0, 0, 24, 24);
    const d = s.getContext('2d').getImageData(0, 0, 24, 24).data, g = new Float32Array(576);
    for (let i = 0; i < 576; i++) g[i] = d[i * 4] * 0.3 + d[i * 4 + 1] * 0.59 + d[i * 4 + 2] * 0.11;
    return g;
  });
  const diff = (a, b) => { let s = 0; for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]); return s / a.length; };
  const ds = sig.map((g) => diff(g, sig[0]));
  const start = Math.floor(n * 0.4);
  let best = -1;
  for (let i = start; i < n; i++) if (best < 0 || ds[i] < ds[best]) best = i;
  const sorted = ds.slice(1).sort((a, b) => a - b), median = sorted[Math.floor(sorted.length / 2)];
  return ds[best] < median * 0.6 ? best : n;   // 明显回到起点才截断，否则全用
}

const GRID = 64;   // 体素分辨率：64³ 在笔电上不到一秒

// handMasks[k]：第 k 张里手挡住的像素。那里“看不见物体”，既不算在轮廓内也不算在外，只是不投票
export function buildModelScene(frames, masks, names, handMasks = []) {
  const N = SIZE, K = frames.length;
  // 1. 所有轮廓的外框；转轴取外框的水平中心
  let x0 = N, y0 = N, x1 = 0, y1 = 0;
  for (const m of masks) for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (m[y * N + x] > 0.5) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  }
  if (x1 <= x0 || y1 <= y0) return null;
  const cx = (x0 + x1) / 2, R = Math.max(cx - x0, x1 - cx) + 2, vTop = y0 - 2, H = y1 - y0 + 4;
  const vs = Math.max(2 * R, H) / GRID;            // 一个体素多少像素
  const PAD = 1, nx = Math.ceil(2 * R / vs) + 2 * PAD, ny = Math.ceil(H / vs) + 2 * PAD, nz = nx;
  const toObj = (gx, gy, gz) => [(gx - PAD) * vs - R, -((gy - PAD) * vs) + 0, (gz - PAD) * vs - R];   // y 向上为正，原点在顶部

  // 2. 雕刻：数一个体素在几张轮廓里，允许个别角度抠坏
  const cos = [], sin = [];
  for (let k = 0; k < K; k++) { const t = 2 * Math.PI * k / K; cos.push(Math.cos(t)); sin.push(Math.sin(t)); }
  const tol = Math.max(1, Math.round(K * 0.08));
  const occ = new Float32Array(nx * ny * nz);
  const id = (x, y, z) => x + nx * (y + ny * z);
  for (let gz = PAD; gz < nz - PAD; gz++) for (let gy = PAD; gy < ny - PAD; gy++) for (let gx = PAD; gx < nx - PAD; gx++) {
    const [X, Y, Z] = toObj(gx + 0.5, gy + 0.5, gz + 0.5);
    const v = Math.floor(vTop - Y);
    if (v < 0 || v >= N) continue;
    let miss = 0, hit = 0;
    for (let k = 0; k < K && miss <= tol; k++) {
      const xc = X * cos[k] + Z * sin[k];          // 物体转了 θ 之后，这个点在镜头里的横坐标
      const u = Math.floor(cx - xc);               // 画面是镜像的，所以是减
      if (u < 0 || u >= N) { miss++; continue; }
      const i = v * N + u;
      if (masks[k][i] > 0.5) hit++;
      else if (!handMasks[k]?.[i]) miss++;
    }
    if (miss <= tol && hit >= K * 0.3) occ[id(gx, gy, gz)] = 1;
  }
  // 3. 3×3×3 平滑，网格才不会是一格一格的
  const f = new Float32Array(occ.length);
  for (let z = 1; z < nz - 1; z++) for (let y = 1; y < ny - 1; y++) for (let x = 1; x < nx - 1; x++) {
    let s = 0;
    for (let dz = -1; dz <= 1; dz++) for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) s += occ[id(x + dx, y + dy, z + dz)];
    f[id(x, y, z)] = s / 27;
  }

  // 4. 表面网（surface nets）：每个跨越 0.5 等值面的格子放一个顶点，相邻格子连成四边形
  const iso = 0.5, cell = new Int32Array(nx * ny * nz).fill(-1), pos = [];
  const corner = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]];
  const edges = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
  for (let z = 0; z < nz - 1; z++) for (let y = 0; y < ny - 1; y++) for (let x = 0; x < nx - 1; x++) {
    const val = corner.map(([a, b, c]) => f[id(x + a, y + b, z + c)]);
    let inside = 0;
    for (const v of val) if (v > iso) inside++;
    if (inside === 0 || inside === 8) continue;
    let sx = 0, sy = 0, sz = 0, n = 0;
    for (const [a, b] of edges) {
      if ((val[a] > iso) === (val[b] > iso)) continue;
      const t = (iso - val[a]) / (val[b] - val[a]), A = corner[a], B = corner[b];
      sx += A[0] + t * (B[0] - A[0]); sy += A[1] + t * (B[1] - A[1]); sz += A[2] + t * (B[2] - A[2]); n++;
    }
    cell[id(x, y, z)] = pos.length / 3;
    pos.push(...toObj(x + sx / n, y + sy / n, z + sz / n));
  }
  const idx = [];
  const dims = [nx, ny, nz];
  for (let z = 1; z < nz - 1; z++) for (let y = 1; y < ny - 1; y++) for (let x = 1; x < nx - 1; x++) {
    const p = [x, y, z], here = f[id(x, y, z)] > iso;
    for (let a = 0; a < 3; a++) {
      const q = p.slice(); q[a]++;
      if (q[a] >= dims[a]) continue;
      if (here === (f[id(...q)] > iso)) continue;
      const b = (a + 1) % 3, c = (a + 2) % 3;
      const cl = (db, dc) => { const r = p.slice(); r[b] -= db; r[c] -= dc; return cell[id(...r)]; };
      const v0 = cl(0, 0), v1 = cl(1, 0), v2 = cl(1, 1), v3 = cl(0, 1);
      if (v0 < 0 || v1 < 0 || v2 < 0 || v3 < 0) continue;
      if (here) idx.push(v0, v1, v2, v0, v2, v3); else idx.push(v0, v2, v1, v0, v3, v2);
    }
  }
  if (idx.length < 30) return null;

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setIndex(idx);
  // 体积为负说明三角形朝里，整体翻过来
  let vol = 0;
  for (let i = 0; i < idx.length; i += 3) {
    const a = idx[i] * 3, b = idx[i + 1] * 3, c = idx[i + 2] * 3;
    vol += pos[a] * (pos[b + 1] * pos[c + 2] - pos[b + 2] * pos[c + 1]) - pos[a + 1] * (pos[b] * pos[c + 2] - pos[b + 2] * pos[c])
      + pos[a + 2] * (pos[b] * pos[c + 1] - pos[b + 1] * pos[c]);
  }
  if (vol < 0) { for (let i = 0; i < idx.length; i += 3) [idx[i + 1], idx[i + 2]] = [idx[i + 2], idx[i + 1]]; geo.setIndex(idx); }
  geo.computeVertexNormals();

  // 5. 上色：每个顶点用所有“正对它而且它落在轮廓内”的照片加权平均，越正对权重越大
  const pix = frames.map((c) => c.getContext('2d').getImageData(0, 0, N, N).data);
  const nrm = geo.getAttribute('normal').array, col = new Float32Array(pos.length);
  for (let i = 0; i < pos.length; i += 3) {
    const X = pos[i], Y = pos[i + 1], Z = pos[i + 2], v = Math.min(N - 1, Math.max(0, Math.floor(vTop - Y)));
    let r = 0, g = 0, bl = 0, wsum = 0;
    for (let k = 0; k < K; k++) {
      const facing = nrm[i] * -sin[k] + nrm[i + 2] * cos[k];   // 法线和第 k 张照片镜头方向的夹角
      if (facing <= 0.05) continue;
      const u = Math.floor(cx - (X * cos[k] + Z * sin[k]));
      if (u < 0 || u >= N || masks[k][v * N + u] <= 0.5) continue;
      const w = facing ** 4, o = (v * N + u) * 4;
      r += pix[k][o] * w; g += pix[k][o + 1] * w; bl += pix[k][o + 2] * w; wsum += w;
    }
    if (!wsum) { r = g = bl = 160; wsum = 1; }
    const lin = (c) => Math.pow(c / wsum / 255, 2.2);   // 照片是 sRGB，顶点色要线性
    col[i] = lin(r); col[i + 1] = lin(g); col[i + 2] = lin(bl);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));

  // 6. 缩放到最长边 8 cm，居中
  geo.computeBoundingBox();
  const bb = geo.boundingBox, size = bb.getSize(new THREE.Vector3()), mid = bb.getCenter(new THREE.Vector3());
  const k8 = 8 / Math.max(size.x, size.y, size.z);
  geo.translate(-mid.x, -mid.y, -mid.z); geo.scale(k8, k8, k8);
  geo.computeVertexNormals();

  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0, roughness: 0.75 }));
  const group = new THREE.Group();
  group.add(mesh);
  const parts = [{ name: names.name, info: names.info, object: mesh, base: mesh.position.clone(), dir: new THREE.Vector3() }];
  return {
    id: 'capture', title: names.title, group, parts, skipExplode: true, mesh,
    stats: { frames: K, vertices: pos.length / 3, triangles: idx.length / 3 },
    update(t, s) { if (s.running) mesh.rotation.y = t * 0.8; },
  };
}

// 导出成 .obj（带顶点颜色，Blender / MeshLab / Windows 3D 查看器都能打开）
export function toOBJ(mesh) {
  const g = mesh.geometry, p = g.getAttribute('position').array, c = g.getAttribute('color').array, ix = g.getIndex().array;
  const srgb = (x) => Math.pow(x, 1 / 2.2).toFixed(3);
  const lines = ['# AETHER Window 360° scan · units: cm'];
  for (let i = 0; i < p.length; i += 3) lines.push(`v ${p[i].toFixed(3)} ${p[i + 1].toFixed(3)} ${p[i + 2].toFixed(3)} ${srgb(c[i])} ${srgb(c[i + 1])} ${srgb(c[i + 2])}`);
  for (let i = 0; i < ix.length; i += 3) lines.push(`f ${ix[i] + 1} ${ix[i + 1] + 1} ${ix[i + 2] + 1}`);
  return lines.join('\n');
}

// ---------- 单张照片 → 3D 网格（Meta SAM 3D Objects，经服务器调用） ----------
// hiRes：高分辨率原图；mask：SIZE×SIZE 的抠图结果（手已经去掉）；label：认出来的物体名
export async function generate3D(hiRes, mask, label, names) {
  const W = hiRes.width, N = SIZE;
  const m = document.createElement('canvas');
  m.width = m.height = N;
  const md = m.getContext('2d').createImageData(N, N);
  for (let i = 0; i < N * N; i++) { const v = mask[i] > 0.5 ? 255 : 0; md.data[i * 4] = md.data[i * 4 + 1] = md.data[i * 4 + 2] = v; md.data[i * 4 + 3] = 255; }
  m.getContext('2d').putImageData(md, 0, 0);
  const big = document.createElement('canvas');
  big.width = big.height = W;
  big.getContext('2d').drawImage(m, 0, 0, W, W);
  const b64 = (c) => c.toDataURL('image/png').split(',')[1];
  const r = await fetch('/api/model3d', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ image: b64(hiRes), mask: b64(big), prompt: label || 'object' }),
    signal: AbortSignal.timeout(240000),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
  const glb = await r.arrayBuffer();
  const gltf = await new GLTFLoader().parseAsync(glb.slice(0), '');
  const obj = gltf.scene;
  obj.traverse((o) => {   // 场景要求材质有 emissive（高亮用），没有的换成标准材质
    if (o.isMesh && !o.material.emissive) o.material = new THREE.MeshStandardMaterial({ map: o.material.map || null, color: o.material.color || 0xffffff });
  });
  const box = new THREE.Box3().setFromObject(obj), size = box.getSize(new THREE.Vector3()), mid = box.getCenter(new THREE.Vector3());
  const k = 8 / Math.max(size.x, size.y, size.z);
  const holder = new THREE.Group();
  obj.position.sub(mid); holder.add(obj); holder.scale.setScalar(k);
  const group = new THREE.Group();
  group.add(holder);
  let tri = 0;
  obj.traverse((o) => { if (o.isMesh) tri += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3; });
  return {
    id: 'capture', title: names.title, group, skipExplode: true, mesh: null, glb,
    parts: [{ name: names.name, info: names.info, object: holder, base: holder.position.clone(), dir: new THREE.Vector3() }],
    stats: { frames: 1, triangles: Math.round(tri) },
    update(t, s) { if (s.running) holder.rotation.y = t * 0.8; },
  };
}
