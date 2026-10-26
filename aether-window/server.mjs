// AETHER Window 本地服务器：静态文件 + /api/command（大模型把自然语言变成场景动作）+ /api/segment（抠图）
// 运行：双击 start.bat，或 node server.mjs  →  打开 http://localhost:8787
// 换模型只改 ai.config.json（照 ai.config.example.json 复制一份），不用改代码。
import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 8787);

// 只开放这些目录，避免把整个项目（含 ai.config.json 里的 key）暴露出去
const STATIC = {
  '/': 'public/index.html',
  '/app.js': 'public/app.js',
  '/scenes.js': 'public/scenes.js',
  '/capture.js': 'public/capture.js',
  '/style.css': 'public/style.css',
};
const PREFIXES = [
  ['/vendor/', 'public/vendor/'],
  ['/models/', 'models/'],
];
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.wasm': 'application/wasm', '.task': 'application/octet-stream',
  '.json': 'application/json',
};

// ---------- 配置 ----------
// chat.provider：
//   "none"      不接大模型，前端用本地关键词兜底
//   "meta"      Meta Llama API（OpenAI 兼容接口，默认 baseUrl 见下）
//   "openai"    任何 OpenAI 兼容接口（自己填 baseUrl）
//   "anthropic" Claude（需要 npm install @anthropic-ai/sdk）
// model3d.provider：
//   "none"      扫描后在浏览器里用轮廓重建（视觉外壳，粗糙）
//   "runware"   Meta SAM 3D Objects（单张照片 → 带贴图的 GLB 网格），通过 Runware 调用，按次计费约 0.006 美元
// segment.provider：
//   "none"      前端用本地抠图兜底
//   "http"      把图片 POST 到 segment.url（SAM 3.1 拿到后接这里，见 callSegmenter）
const PRESETS = {
  meta: { baseUrl: 'https://api.llama.com/compat/v1', model: 'Llama-4-Maverick-17B-128E-Instruct-FP8' },
  openai: { baseUrl: 'https://api.openai.com/v1', model: '' },
  anthropic: { model: 'claude-opus-5-5' },
};

async function loadConfig() {
  let file = {};
  try { file = JSON.parse(await fs.readFile(path.join(ROOT, 'ai.config.json'), 'utf8')); }
  catch (err) { if (err.code !== 'ENOENT') console.log(`ai.config.json 读不了（${err.message}），先按没有配置运行`); }
  const chat = { provider: 'none', ...file.chat };
  const segment = { provider: 'none', ...file.segment };
  const model3d = { provider: 'none', ...file.model3d };
  if (process.env.AETHER_3D_KEY) { model3d.provider = 'runware'; model3d.apiKey = process.env.AETHER_3D_KEY; }
  if (model3d.provider !== 'none' && !model3d.apiKey) model3d.provider = 'none';
  // 环境变量优先，方便不改文件临时切换
  if (process.env.AETHER_PROVIDER) chat.provider = process.env.AETHER_PROVIDER;
  if (process.env.AETHER_API_KEY) chat.apiKey = process.env.AETHER_API_KEY;
  if (process.env.AETHER_MODEL) chat.model = process.env.AETHER_MODEL;
  if (process.env.AETHER_BASE_URL) chat.baseUrl = process.env.AETHER_BASE_URL;
  if (chat.provider === 'none' && process.env.ANTHROPIC_API_KEY) chat.provider = 'anthropic';   // 兼容旧用法
  const preset = PRESETS[chat.provider] || {};
  chat.baseUrl = (chat.baseUrl || preset.baseUrl || '').replace(/\/+$/, '');
  chat.model ||= preset.model || '';
  if (chat.provider !== 'none' && chat.provider !== 'anthropic' && !chat.apiKey) chat.provider = 'none';
  return { chat, segment, model3d };
}
const CONFIG = await loadConfig();

let anthropic = null;
if (CONFIG.chat.provider === 'anthropic') {
  try {
    const { default: Anthropic } = await import('@anthropic-ai/sdk');
    anthropic = new Anthropic(CONFIG.chat.apiKey ? { apiKey: CONFIG.chat.apiKey } : {});
  } catch { CONFIG.chat.provider = 'none'; }
}

// ---------- 场景动作协议 ----------
// 大模型只能回这几种动作，前端逐条执行
const ACTION_TYPES = ['explode', 'rotate', 'select', 'clear_select', 'load_scene', 'run', 'reset', 'capture'];
const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['say', 'actions'],
  properties: {
    say: { type: 'string', description: 'Spoken reply, 1-2 short sentences, in the user\'s language' },
    actions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['type', 'amount', 'target'],
        properties: {
          type: { type: 'string', enum: ACTION_TYPES },
          amount: { type: 'number', description: 'explode: 0..1; rotate: degrees; run: 1 start, 0 stop; otherwise 0' },
          target: { type: 'string', description: 'select: a part name from state.parts; load_scene: engine|solar|dna|capture; rotate: x|y; otherwise ""' },
        },
      },
    },
  },
};

const SYSTEM = `You are the scene assistant inside AETHER Window. The user is looking at a 3D model floating in front of their screen and gives commands or asks questions by voice.
Latency-sensitive; begin your visible answer immediately.
Reply in the same language the user used (Chinese or English).
You can change the scene only through actions:
- explode amount 0..1: how far apart the parts are (0 assembled, 1 fully exploded)
- rotate amount in degrees, target "x" or "y"
- select target = a part name, copied exactly from state.parts; clear_select removes the highlight
- load_scene target engine / solar / dna / capture (capture = the last object photographed by the camera)
- run amount 1 starts the animation, 0 stops it
- reset returns to the initial view
- capture: take a photo of the real object the user holds up and turn it into a 3D card
When the user asks what a part is, select it and explain its job in one or two sentences in "say".
Keep "say" short and conversational, suitable for text-to-speech. If no action fits, return an empty actions array.
Output only one JSON object: {"say": string, "actions": [{"type": string, "amount": number, "target": string}]}.`;

async function askOpenAICompatible(userContent) {
  const { baseUrl, apiKey, model } = CONFIG.chat;
  const body = (format) => JSON.stringify({
    model, max_tokens: 600, temperature: 0.2,
    messages: [{ role: 'system', content: SYSTEM }, { role: 'user', content: userContent }],
    ...(format ? { response_format: { type: 'json_schema', json_schema: { name: 'scene_actions', schema: SCHEMA, strict: true } } } : {}),
  });
  const call = (format) => fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${apiKey}` },
    body: body(format),
    signal: AbortSignal.timeout(7000),
  });
  let r = await call(true);
  if (r.status === 400 || r.status === 422) r = await call(false);   // 有的接口不支持 json_schema，退回只靠提示词
  if (!r.ok) throw Object.assign(new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`), { status: r.status });
  const data = await r.json();
  return data.choices?.[0]?.message?.content ?? '';
}

async function askAnthropic(userContent) {
  const msg = await anthropic.beta.messages.create({
    model: CONFIG.chat.model,
    max_tokens: 2000,
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    output_config: { effort: 'low', format: { type: 'json_schema', schema: SCHEMA } },
    system: SYSTEM,
    messages: [{ role: 'user', content: userContent }],
  });
  if (msg.stop_reason === 'refusal') return JSON.stringify({ say: '', actions: [] });
  return msg.content.find((b) => b.type === 'text')?.text ?? '';
}

// 模型偶尔会在 JSON 外面包一层说明或代码块，取最外层的 {...}
function parseActions(text) {
  const s = String(text || ''), a = s.indexOf('{'), b = s.lastIndexOf('}');
  if (a < 0 || b <= a) throw new SyntaxError('no json');
  const out = JSON.parse(s.slice(a, b + 1));
  return {
    say: String(out.say || ''),
    actions: (Array.isArray(out.actions) ? out.actions : [])
      .filter((x) => x && ACTION_TYPES.includes(x.type))
      .map((x) => ({ type: x.type, amount: Number(x.amount) || 0, target: String(x.target ?? '') })),
  };
}

async function handleCommand(req, res) {
  let input;
  try { input = JSON.parse(await readBody(req, 64 * 1024)); } catch { return send(res, 400, { error: 'bad json' }); }
  if (CONFIG.chat.provider === 'none') return send(res, 503, { error: '没有配置大模型，前端会用本地关键词兜底' });

  const userContent = JSON.stringify({ command: String(input.text || '').slice(0, 500), state: input.state || {} });
  try {
    const text = CONFIG.chat.provider === 'anthropic' ? await askAnthropic(userContent) : await askOpenAICompatible(userContent);
    return send(res, 200, parseActions(text));
  } catch (err) {
    if (err?.status === 401 || err?.status === 403) return send(res, 503, { error: 'API key 无效' });
    if (err?.status === 429) return send(res, 429, { error: '限流，稍后再试' });
    if (err?.status) return send(res, 502, { error: `模型接口 ${err.status}` });
    if (err instanceof SyntaxError) return send(res, 502, { error: '模型输出不是合法 JSON' });
    return send(res, 502, { error: String(err?.message || err) });
  }
}

// ---------- 抠图 ----------
// 输入：{ image: PNG/JPEG 的 base64（不带 data: 前缀）, point: [x, y]（0~1，物体中心）, prompt: 文字描述（可空） }
// 输出：{ mask: PNG 的 base64，白色 = 物体 }
// SAM 3.1 拿到后，只要把下面这个函数改成它的真实请求格式即可，前端不用动。
async function callSegmenter({ image, point, prompt }) {
  const { url, apiKey } = CONFIG.segment;
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...(apiKey ? { authorization: `Bearer ${apiKey}` } : {}) },
    body: JSON.stringify({ image_base64: image, points: [point], text_prompt: prompt || '' }),
    signal: AbortSignal.timeout(15000),
  });
  if (!r.ok) throw Object.assign(new Error(`HTTP ${r.status}`), { status: r.status });
  const data = await r.json();
  const mask = data.mask_base64 || data.mask || data.masks?.[0];
  if (!mask) throw new Error('返回里没有 mask');
  return String(mask).replace(/^data:image\/\w+;base64,/, '');
}

async function handleSegment(req, res) {
  let input;
  try { input = JSON.parse(await readBody(req, 8 * 1024 * 1024)); } catch { return send(res, 400, { error: 'bad json' }); }
  if (CONFIG.segment.provider !== 'http' || !CONFIG.segment.url) return send(res, 503, { error: '没有配置抠图模型，前端用本地抠图' });
  try {
    return send(res, 200, { mask: await callSegmenter(input) });
  } catch (err) {
    return send(res, 502, { error: String(err?.message || err) });
  }
}

// ---------- 单张照片 → 3D 网格（SAM 3D Objects） ----------
// 输入：{ image: PNG 的 base64, mask: PNG 的 base64（白色 = 物体）, prompt: 物体名称 }
// 输出：GLB 二进制（服务器下载好再转给浏览器，避免跨域）
const RUNWARE = process.env.AETHER_3D_URL || 'https://api.runware.ai/v1';
async function runware(tasks, timeoutMs) {
  const r = await fetch(RUNWARE, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${CONFIG.model3d.apiKey}` },
    body: JSON.stringify(tasks),
    signal: AbortSignal.timeout(timeoutMs),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok || data.errors?.length) {
    const msg = data.errors?.[0]?.message || `HTTP ${r.status}`;
    throw Object.assign(new Error(msg), { status: r.status });
  }
  return data.data || [];
}
const fileUrl = (rows, id) => {
  const row = rows.find((d) => d.taskUUID === id) || rows[0];
  return row?.outputs?.files?.[0]?.url || row?.outputFiles?.[0]?.url || row?.fileURL || null;
};

async function handleModel3d(req, res) {
  let input;
  try { input = JSON.parse(await readBody(req, 16 * 1024 * 1024)); } catch { return send(res, 400, { error: 'bad json' }); }
  if (CONFIG.model3d.provider !== 'runware') return send(res, 503, { error: '没有配置 3D 生成模型' });
  const taskUUID = crypto.randomUUID();
  const what = String(input.prompt || 'object').slice(0, 80);
  try {
    // 先异步提交，再每 3 秒问一次结果，最多等 3 分钟（官方实测一次约 1 分钟）
    await runware([{
      taskType: '3dInference', taskUUID, model: 'meta:sam@3d',
      positivePrompt: `Reconstruct the single ${what} held up to the camera as a complete, high-fidelity 3D object, preserving its shape, proportions, materials and colours. Do not include hands.`,
      inputs: { image: `data:image/png;base64,${input.image}`, mask: `data:image/png;base64,${input.mask}` },
      outputType: 'URL', outputFormat: 'GLB', deliveryMethod: 'async',
    }], 30000);
    let url = null;
    for (let i = 0; i < 60 && !url; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      url = fileUrl(await runware([{ taskType: 'getResponse', taskUUID }], 15000), taskUUID);
    }
    if (!url) return send(res, 504, { error: '3D 生成超时' });
    const glb = await fetch(url, { signal: AbortSignal.timeout(60000) });
    if (!glb.ok) return send(res, 502, { error: `下载 GLB 失败 ${glb.status}` });
    res.writeHead(200, { 'content-type': 'model/gltf-binary' });
    return res.end(Buffer.from(await glb.arrayBuffer()));
  } catch (err) {
    if (err?.status === 401 || err?.status === 403) return send(res, 503, { error: '3D 模型的 API key 无效' });
    return send(res, 502, { error: String(err?.message || err) });
  }
}

function status() {
  const { chat, segment, model3d } = CONFIG;
  return {
    chat: chat.provider === 'none' ? null : { provider: chat.provider, model: chat.model },
    segment: segment.provider === 'http' && segment.url ? { provider: 'http' } : null,
    model3d: model3d.provider === 'none' ? null : { provider: model3d.provider, model: 'SAM 3D Objects' },
  };
}

// ---------- HTTP ----------
async function readBody(req, limit) {
  let body = '';
  for await (const chunk of req) {
    body += chunk;
    if (body.length > limit) throw new Error('too large');
  }
  return body;
}

function send(res, code, obj) {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}

async function serveStatic(req, res) {
  const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  let rel = STATIC[url];
  if (!rel) {
    for (const [prefix, dir] of PREFIXES) {
      if (url.startsWith(prefix)) { rel = dir + url.slice(prefix.length); break; }
    }
  }
  const file = rel && path.resolve(ROOT, rel);
  if (!file || !file.startsWith(ROOT + path.sep) || file.includes('..')) {
    res.writeHead(404); return res.end('not found');
  }
  try {
    const data = await fs.readFile(file);
    res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404); res.end('not found');
  }
}

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/api/command') return handleCommand(req, res).catch(() => send(res, 500, { error: 'server' }));
  if (req.method === 'POST' && req.url === '/api/model3d') return handleModel3d(req, res).catch(() => send(res, 500, { error: 'server' }));
  if (req.method === 'POST' && req.url === '/api/segment') return handleSegment(req, res).catch(() => send(res, 500, { error: 'server' }));
  if (req.method === 'GET' && req.url === '/api/status') return send(res, 200, status());
  if (req.method === 'GET') return serveStatic(req, res);
  res.writeHead(405); res.end();
});
server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {   // 旧窗口还开着：它每次请求都会重新读文件，所以直接用它就行
    console.log(`AETHER Window 已经在运行（端口 ${PORT}），直接用浏览器打开 http://localhost:${PORT} 即可。`);
    console.log('（如果刚改了 ai.config.json，要先关掉旧的黑色窗口再重新双击 start.bat。）');
    process.exit(0);
  }
  throw err;
});
server.listen(PORT, () => {
  const { chat, segment } = CONFIG;
  const ai = chat.provider === 'none' ? '未配置（本地关键词兜底）' : `${chat.provider} · ${chat.model}`;
  const seg = segment.provider === 'http' && segment.url ? `http · ${segment.url}` : '未配置（本地抠图兜底）';
  const m3 = CONFIG.model3d.provider === 'runware' ? 'SAM 3D Objects（Runware）' : '未配置（浏览器轮廓重建）';
  console.log(`AETHER Window → http://localhost:${PORT}\n  AI 模型：${ai}\n  抠图模型：${seg}\n  3D 生成：${m3}`);
});
