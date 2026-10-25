// 下载 MediaPipe 模型到 models/，比赛现场断网也能跑
import fs from 'node:fs/promises';
const BASE = 'https://storage.googleapis.com/mediapipe-models';
const MODELS = {
  'face_landmarker.task': `${BASE}/face_landmarker/face_landmarker/float16/1/face_landmarker.task`,
  'hand_landmarker.task': `${BASE}/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`,
};
await fs.mkdir(new URL('../models/', import.meta.url), { recursive: true });
for (const [name, url] of Object.entries(MODELS)) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  await fs.writeFile(new URL(`../models/${name}`, import.meta.url), buf);
  console.log(`✓ ${name} ${(buf.length / 1e6).toFixed(1)} MB`);
}
