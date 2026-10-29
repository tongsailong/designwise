#!/usr/bin/env node
/**
 * check-ui.mjs — 页面级 UI 验收采集（无第三方依赖）
 *
 * 只做客观采集：触控尺寸、叶子文本字号、横向溢出、控制台错误。
 * 不做视觉判断，也不替代 Gate 1 / Gate 2。
 *
 * 用法：
 *   node scripts/check-ui.mjs --url file:///path/index.html --tap 48 --font-min 12
 *   node scripts/check-ui.mjs --url "file:///...?fs=13" --url "file:///...?fs=15" --tap 48
 *
 * 退出码：0 全部通过；1 有阻塞项；2 环境/用法错误。
 * 依赖：本机 Chrome/Chromium（可用 --chrome 或 CHROME 指定）+ Node >= 22（原生 WebSocket）。
 */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readdirSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';
import path from 'node:path';

const args = process.argv.slice(2);
const urls = [];
let tap = 48;
let tapWidth = null;
let fontMin = 12;
let width = 460;
let height = 960;
let settle = 300;
let chromePath = process.env.CHROME || '';
let timeout = 30000;

for (let i = 0; i < args.length; i += 1) {
  const a = args[i];
  const next = () => {
    if (i + 1 >= args.length) fail(`缺少 ${a} 的值`);
    return args[++i];
  };
  if (a === '--url') urls.push(next());
  else if (a === '--tap') tap = Number(next());
  else if (a === '--tap-width') tapWidth = Number(next());
  else if (a === '--font-min') fontMin = Number(next());
  else if (a === '--width') width = Number(next());
  else if (a === '--height') height = Number(next());
  else if (a === '--settle') settle = Number(next());
  else if (a === '--timeout') timeout = Number(next());
  else if (a === '--chrome') chromePath = next();
  else if (a === '--help' || a === '-h') usage(0);
  else fail(`未知参数：${a}`);
}

if (!urls.length) usage(2);
if (!Number.isFinite(tap) || tap <= 0) fail('--tap 必须是正数');
if (tapWidth === null) tapWidth = tap;
if (!Number.isFinite(tapWidth) || tapWidth < 0) fail('--tap-width 必须是 >= 0 的数');
if (!Number.isFinite(fontMin) || fontMin <= 0) fail('--font-min 必须是正数');
if (typeof WebSocket === 'undefined') fail('需要 Node >= 22（原生 WebSocket）');

function usage(code) {
  process.stderr.write(
    'Usage: node scripts/check-ui.mjs --url <url> [--url <url>...] [--tap 48] [--tap-width 48] '
    + '[--font-min 12] [--width 460] [--height 960] [--settle 300] [--chrome <path>]\n',
  );
  process.exit(code);
}

function fail(message) {
  process.stderr.write(`check-ui: ${message}\n`);
  process.exit(2);
}

function findChrome() {
  if (chromePath) {
    if (!existsSync(chromePath)) fail(`找不到 Chrome：${chromePath}`);
    return chromePath;
  }
  const candidates = [
    '/home/ctyun/.local/bin/google-chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium',
  ];
  for (const p of candidates) if (existsSync(p)) return p;
  // Playwright 浏览器缓存：取版本号最大的 chrome
  const cache = path.join(homedir(), '.cache', 'ms-playwright');
  if (existsSync(cache)) {
    const dirs = readdirSync(cache)
      .filter((d) => d.startsWith('chromium-'))
      .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
    for (const d of dirs) {
      for (const rel of ['chrome-linux64/chrome', 'chrome-linux/chrome']) {
        const p = path.join(cache, d, rel);
        if (existsSync(p)) return p;
      }
    }
  }
  fail('找不到 Chrome/Chromium；用 --chrome 或 CHROME 指定');
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function httpJson(port, pathname, method = 'GET') {
  const res = await fetch(`http://127.0.0.1:${port}${pathname}`, { method });
  if (!res.ok) throw new Error(`${method} ${pathname} -> ${res.status}`);
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

class Cdp {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message || 'CDP error'));
        else resolve(msg.result);
        return;
      }
      if (msg.method && this.listeners.has(msg.method)) {
        for (const fn of this.listeners.get(msg.method)) fn(msg.params);
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, fn) {
    if (!this.listeners.has(method)) this.listeners.set(method, new Set());
    this.listeners.get(method).add(fn);
  }

  close() {
    try {
      this.ws.close();
    } catch {
      /* ignore */
    }
  }
}

const EVALUATE = `(() => {
  const isVisible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const label = (el) => {
    const text = (el.innerText || el.getAttribute('aria-label') || el.value || '')
      .replace(/\\s+/g, ' ').trim();
    return text.slice(0, 40) || el.tagName.toLowerCase();
  };
  const selector = 'button, a, input, textarea, select, summary, [role="button"], [onclick]';
  const tapFailures = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(selector)) {
    if (!isVisible(el)) continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const inline = cs.display.startsWith('inline');
    const rec = {
      tag: el.tagName.toLowerCase(),
      label: label(el),
      width: Math.round(r.width),
      height: Math.round(r.height),
      display: cs.display,
    };
    const key = JSON.stringify(rec);
    if (seen.has(key)) continue;
    seen.add(key);
    const minW = inline ? 0 : TAP_WIDTH;
    if (r.height + 0.5 < TAP || r.width + 0.5 < minW) tapFailures.push(rec);
  }
  const fontFailures = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seenFont = new Set();
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const text = (node.nodeValue || '').trim();
    if (!text) continue;
    const el = node.parentElement;
    if (!el || !isVisible(el)) continue;
    const cs = getComputedStyle(el);
    const size = parseFloat(cs.fontSize);
    if (!Number.isFinite(size) || size + 0.01 >= FONT_MIN) continue;
    const rec = {
      tag: el.tagName.toLowerCase(),
      label: text.replace(/\\s+/g, ' ').slice(0, 40),
      fontSize: Math.round(size * 10) / 10,
    };
    const key = JSON.stringify(rec);
    if (seenFont.has(key)) continue;
    seenFont.add(key);
    fontFailures.push(rec);
  }
  const de = document.documentElement;
  const b = document.body;
  return {
    title: document.title,
    tapFailures,
    fontFailures,
    overflow: {
      document: de.scrollWidth - de.clientWidth,
      body: b ? b.scrollWidth - b.clientWidth : 0,
      clientWidth: de.clientWidth,
      scrollWidth: de.scrollWidth,
    },
    counts: {
      interactive: document.querySelectorAll(selector).length,
    },
  };
})()`;

async function checkUrl(chrome, url) {
  const profile = mkdtempSync(path.join(tmpdir(), 'dw-check-ui-'));
  const port = 9300 + Math.floor(Math.random() * 500);
  const proc = spawn(chrome, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    `--user-data-dir=${profile}`,
    `--remote-debugging-port=${port}`,
    `--window-size=${width},${height}`,
    'about:blank',
  ], { stdio: 'ignore' });

  const cleanup = () => {
    try {
      proc.kill('SIGKILL');
    } catch {
      /* ignore */
    }
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  };

  try {
    const deadline = Date.now() + timeout;
    let ready = false;
    while (Date.now() < deadline) {
      try {
        await httpJson(port, '/json/version');
        ready = true;
        break;
      } catch {
        await sleep(120);
      }
    }
    if (!ready) throw new Error('Chrome 调试端口未就绪');

    const target = await httpJson(port, '/json/new?about:blank', 'PUT');
    const cdp = new Cdp(target.webSocketDebuggerUrl);
    await cdp.open();

    const consoleErrors = [];
    const exceptions = [];
    cdp.on('Runtime.consoleAPICalled', (p) => {
      if (p.type === 'error') {
        consoleErrors.push((p.args || []).map((a) => a.value || a.description || '').join(' ').slice(0, 300));
      }
    });
    cdp.on('Runtime.exceptionThrown', (p) => {
      exceptions.push((p.exceptionDetails && p.exceptionDetails.text) || 'uncaught exception');
    });

    await cdp.send('Runtime.enable');
    await cdp.send('Page.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    let loaded = false;
    cdp.on('Page.loadEventFired', () => {
      loaded = true;
    });
    const nav = await cdp.send('Page.navigate', { url });
    const loadError = (nav && nav.errorText) || '';
    const loadDeadline = Date.now() + timeout;
    while (!loaded && Date.now() < loadDeadline) await sleep(50);
    const loadTimedOut = !loaded;
    if (!loadError) await sleep(settle);

    const params = {
      expression: EVALUATE.replaceAll('TAP_WIDTH', String(tapWidth))
        .replaceAll('TAP', String(tap))
        .replaceAll('FONT_MIN', String(fontMin)),
      returnByValue: true,
      awaitPromise: false,
    };
    const result = await cdp.send('Runtime.evaluate', params);
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || '页面求值失败');
    const data = result.result.value || {};

    await httpJson(port, `/json/close/${target.id}`).catch(() => {});
    cdp.close();

    const overflowFail = (data.overflow?.document > 1) || (data.overflow?.body > 1);
    const pass = !data.tapFailures?.length && !data.fontFailures?.length
      && !overflowFail && !consoleErrors.length && !exceptions.length
      && !loadError && !loadTimedOut;

    return {
      url,
      title: data.title || '',
      pass,
      loadError,
      loadTimedOut,
      tap: { min: tap, minWidth: tapWidth, failures: data.tapFailures || [] },
      font: { min: fontMin, failures: data.fontFailures || [] },
      overflow: { ...data.overflow, fail: overflowFail },
      consoleErrors,
      exceptions,
    };
  } finally {
    cleanup();
  }
}

const chrome = findChrome();
const reports = [];
for (const url of urls) {
  try {
    reports.push(await checkUrl(chrome, url));
  } catch (err) {
    reports.push({ url, pass: false, error: String(err && err.message ? err.message : err) });
  }
}

const allPass = reports.every((r) => r.pass);
process.stdout.write(`${JSON.stringify({
  unit: 'css-px',
  note: 'CSS px only; this does not prove Android dp compliance (use wm density + uiautomator bounds on device).',
  tap,
  tapWidth,
  fontMin,
  viewport: `${width}x${height}`,
  allPass,
  reports,
}, null, 2)}\n`);

process.stderr.write('check-ui: 结果为 CSS px 采集，不等同于 Android dp 合规；原生界面需按 dp/真机复核。\n');

if (!allPass) {
  process.stderr.write('check-ui: 存在不达标项（详见 JSON 的 tap/font/overflow/consoleErrors）\n');
  process.exit(1);
}
