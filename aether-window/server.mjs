// AETHER Window 本地服务器：静态文件 + /api/command（Claude 把自然语言变成场景动作）
// 运行：npm install && npm run setup && npm start  →  打开 http://localhost:8787
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 8787);
const MODEL = process.env.AETHER_MODEL || 'claude-opus-5-5';

// 只开放这些目录，避免把整个项目（含 .env）暴露出去
const STATIC = {
  '/': 'public/index.html',
  '/app.js': 'public/app.js',
  '/scenes.js': 'public/scenes.js',
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

// SDK 可选：没装或没有 key 时，前端自动用本地关键词兜底，演示照样能跑
let client = null;
if (process.env.ANTHROPIC_API_KEY) {
  try {
    const { default: Anthropic } = await import('@anthropic-ai/sdk');
    client = new Anthropic();
  } catch { client = null; }
}

// 结构化输出：Claude 只能回这几种动作，前端逐条执行
const ACTION_TYPES = ['explode', 'rotate', 'select', 'clear_select', 'load_scene', 'run', 'reset'];
const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['say', 'actions'],
  properties: {
    say: { type: 'string', description: '给用户的中文语音回复，1 到 2 句' },
    actions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['type', 'amount', 'target'],
        properties: {
          type: { type: 'string', enum: ACTION_TYPES },
          amount: { type: 'number', description: 'explode: 0~1；rotate: 角度；run: 1 开 0 关；其余填 0' },
          target: { type: 'string', description: 'select: 零件名；load_scene: engine|solar|dna；rotate: x|y；其余填空字符串' },
        },
      },
    },
  },
};

const SYSTEM = `你是 AETHER Window 的场景助手。用户看着一个浮在屏幕前的 3D 模型，用中文下指令或提问。
Latency-sensitive; begin your visible answer immediately.
你只能通过 actions 改场景：
- explode amount 0~1：拆开程度，0 是装好，1 是完全拆开
- rotate amount 角度，target "x" 或 "y"
- select target 零件名（必须是场景状态里 parts 列表中的名字）；clear_select 取消高亮
- load_scene target engine / solar / dna
- run amount 1 开始动画，0 停止
- reset 回到初始状态
用户问某个零件是什么时，select 它并在 say 里用一两句话讲清楚它的作用。
say 要口语化、短，适合语音朗读。没有合适动作时 actions 为空数组。`;

async function handleCommand(req, res) {
  let body = '';
  for await (const chunk of req) body += chunk;
  let input;
  try { input = JSON.parse(body); } catch { return send(res, 400, { error: 'bad json' }); }
  if (!client) return send(res, 503, { error: '没有 Anthropic 凭据，前端会用本地关键词兜底' });

  try {
    const msg = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 2000,
      betas: ['server-side-fallback-2026-07-01'],
      fallbacks: 'default',
      output_config: { effort: 'low', format: { type: 'json_schema', schema: SCHEMA } },
      system: SYSTEM,
      messages: [{
        role: 'user',
        content: JSON.stringify({ 指令: String(input.text || '').slice(0, 500), 场景状态: input.state || {} }),
      }],
    });
    if (msg.stop_reason === 'refusal') return send(res, 200, { say: '这个我帮不上忙。', actions: [] });
    const text = msg.content.find((b) => b.type === 'text')?.text;
    const out = JSON.parse(text);
    out.actions = (out.actions || []).filter((a) => ACTION_TYPES.includes(a.type));
    return send(res, 200, out);
  } catch (err) {
    if (err?.status === 401) return send(res, 503, { error: 'API key 无效' });
    if (err?.status === 429) return send(res, 429, { error: '限流，稍后再试' });
    if (err?.status) return send(res, 502, { error: `Claude API ${err.status}` });
    if (err instanceof SyntaxError) return send(res, 502, { error: '模型输出不是合法 JSON' });
    return send(res, 502, { error: String(err?.message || err) });
  }
}

function send(res, status, obj) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
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

http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/api/command') return handleCommand(req, res);
  if (req.method === 'GET') return serveStatic(req, res);
  res.writeHead(405); res.end();
}).listen(PORT, () => {
  console.log(`AETHER Window → http://localhost:${PORT}  (model: ${MODEL}, AI: ${process.env.ANTHROPIC_API_KEY ? 'on' : '未设 ANTHROPIC_API_KEY，前端用本地关键词兜底'})`);
});
