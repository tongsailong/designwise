#!/usr/bin/env node
/**
 * check-ui.mjs — 页面级 UI 验收采集（无第三方依赖）
 *
 * 只做客观采集：触控尺寸、叶子文本字号、横向溢出、控制台错误、图片完整性、
 * 文字/背景计算对比度、外观指纹。不做视觉判断，也不替代 Gate 1 / Gate 2。
 *
 * 用法：
 *   node scripts/check-ui.mjs --url file:///path/index.html --tap 48 --font-min 12
 *   node scripts/check-ui.mjs --url "file:///...?fs=13" --url "file:///...?fs=15" --tap 48
 *   node scripts/check-ui.mjs --url file:///path/index.html --shot /tmp/ref.png [--full]
 *   node scripts/check-ui.mjs --url file:///path/index.html --ledger-add 项目名 [--ledger-check 10]
 *   node scripts/check-ui.mjs --ledger 20            # 只查账本，不做页面检查
 *
 * 红灯（进 pass / 退出码 1，客观事实）：触控/字号/溢出/控制台错误/图片加载失败/正文对比度不足。
 * 黄灯（只提示，不改退出码）：相对路径引图、对比度无法自动判定（渐变或图片背景）、外观与历史交付同族。
 * 账本只记录本机设计产物指纹，不是记忆系统；写不进去只报黄灯，不影响页面检查结论。
 *
 * 退出码：0 全部通过；1 有阻塞项；2 环境/用法错误（含 --shot 截图失败）。
 * 依赖：本机 Chrome/Chromium（可用 --chrome 或 CHROME 指定）+ Node >= 22（原生 WebSocket）。
 */
import { spawn } from 'node:child_process';
import {
  mkdtempSync, rmSync, existsSync, readdirSync, mkdirSync, chmodSync,
  writeFileSync, appendFileSync, readFileSync,
} from 'node:fs';
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
let shotPath = '';
let fullPage = false;
let ledgerAdd = '';
let ledgerQuery = false;
let ledgerCheck = false;
let ledgerWindow = 10;

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
  else if (a === '--shot') shotPath = path.resolve(next());
  else if (a === '--full') fullPage = true;
  else if (a === '--ledger-add') ledgerAdd = next();
  else if (a === '--ledger') {
    ledgerQuery = true;
    if (/^\d+$/.test(args[i + 1] || '')) ledgerWindow = Number(args[++i]);
  } else if (a === '--ledger-check') {
    ledgerCheck = true;
    if (/^\d+$/.test(args[i + 1] || '')) ledgerWindow = Number(args[++i]);
  } else if (a === '--help' || a === '-h') usage(0);
  else fail(`未知参数：${a}`);
}

if (!urls.length && !ledgerQuery) usage(2);
if (!Number.isFinite(tap) || tap <= 0) fail('--tap 必须是正数');
if (tapWidth === null) tapWidth = tap;
if (!Number.isFinite(tapWidth) || tapWidth < 0) fail('--tap-width 必须是 >= 0 的数');
if (!Number.isFinite(fontMin) || fontMin <= 0) fail('--font-min 必须是正数');
if (shotPath && urls.length !== 1) fail('--shot 只支持单个 --url（多页请逐个调用）');
if (fullPage && !shotPath) fail('--full 只与 --shot 一起使用');
if (!Number.isFinite(ledgerWindow) || ledgerWindow <= 0) fail('账本窗口必须是正整数');
if (typeof WebSocket === 'undefined') fail('需要 Node >= 22（原生 WebSocket）');

function usage(code) {
  process.stderr.write(
    'Usage: node scripts/check-ui.mjs --url <url> [--url <url>...] [--tap 48] [--tap-width 48] '
    + '[--font-min 12] [--width 460] [--height 960] [--settle 300] [--chrome <path>]\n'
    + '       [--shot <png> [--full]] [--ledger-add <项目名>] [--ledger-check [N]] [--ledger [N]]\n',
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
  // ---- 图片完整性 + 相对路径引图 ----
  const images = [];
  const relativeRefs = [];
  const isRelativeRef = (u) => !!u && !/^(data:|https?:|file:|blob:|about:|#)/i.test(u);
  for (const el of document.querySelectorAll('img')) {
    const src = el.currentSrc || el.src || '';
    const ir = el.getBoundingClientRect();
    const loaded = !!(el.complete && el.naturalWidth > 0);
    images.push({
      src: src.slice(0, 200),
      alt: (el.alt || '').slice(0, 80),
      loaded,
      natural: (el.naturalWidth || 0) + 'x' + (el.naturalHeight || 0),
      rendered: Math.round(ir.width) + 'x' + Math.round(ir.height),
      visible: isVisible(el),
    });
    const raw = el.getAttribute('src') || '';
    if (isRelativeRef(raw)) relativeRefs.push(raw.slice(0, 160));
  }
  const styleUrl = /url\\((['"]?)([^'")]+)\\1\\)/g;
  for (const el of (document.body ? document.body.querySelectorAll('[style*="url("]') : [])) {
    const raw = el.getAttribute('style') || '';
    styleUrl.lastIndex = 0;
    let m;
    while ((m = styleUrl.exec(raw))) {
      const u = m[2].trim();
      if (isRelativeRef(u)) relativeRefs.push(u.slice(0, 160));
    }
  }

  // ---- CSS 颜色归一化 + WCAG 对比度 ----
  const cv = document.createElement('canvas');
  cv.width = 1;
  cv.height = 1;
  const cctx = cv.getContext('2d', { willReadFrequently: true });
  const colorCache = new Map();
  const parseCss = (css) => {
    if (!css) return null;
    if (colorCache.has(css)) return colorCache.get(css);
    cctx.clearRect(0, 0, 1, 1);
    cctx.fillStyle = '#010203';
    cctx.fillStyle = css;
    let out = null;
    const invalid = cctx.fillStyle === '#010203' && css.toLowerCase().indexOf('010203') < 0;
    if (!invalid) {
      cctx.fillRect(0, 0, 1, 1);
      const d = cctx.getImageData(0, 0, 1, 1).data;
      out = [d[0], d[1], d[2], Math.round((d[3] / 255) * 1000) / 1000];
    }
    colorCache.set(css, out);
    return out;
  };
  const hexOf = (c) => '#' + c.slice(0, 3)
    .map((v) => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
  const composite = (top, bottom) => {
    const a = top[3] + bottom[3] * (1 - top[3]);
    if (a <= 0) return [0, 0, 0, 0];
    const rgb = [0, 1, 2].map((i) => Math.round((top[i] * top[3] + bottom[i] * bottom[3] * (1 - top[3])) / a));
    return [rgb[0], rgb[1], rgb[2], Math.round(a * 1000) / 1000];
  };
  const WHITE = [255, 255, 255, 1];
  const flatten = (c) => (c[3] >= 1 ? [c[0], c[1], c[2]] : composite(c, WHITE).slice(0, 3));
  const luminance = (rgb) => {
    const lin = (v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  };
  const contrastRatio = (fg, bg) => {
    const a = luminance(fg);
    const b = luminance(bg);
    const hi = Math.max(a, b);
    const lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05);
  };
  const resolveBg = (el) => {
    const layers = [];
    let node = el;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        return { unknown: '背景含渐变/图片', at: node.tagName.toLowerCase() };
      }
      const c = parseCss(cs.backgroundColor);
      if (c && c[3] > 0) {
        layers.push(c);
        if (c[3] >= 1) break;
      }
      node = node.parentElement;
    }
    if (!layers.length) return { color: [255, 255, 255] };
    let out = layers[0];
    for (let i = 1; i < layers.length; i += 1) out = composite(out, layers[i]);
    return { color: flatten(out) };
  };

  // ---- 文本对比度 + 字体 + 首屏信息密度 ----
  const contrastFailures = [];
  const contrastUnknown = [];
  const seenContrast = new Set();
  const famChars = new Map();
  let displayFamily = 'unknown';
  let displaySize = 0;
  let firstViewTextNodes = 0;
  const walker2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker2.nextNode()) {
    const node = walker2.currentNode;
    const text = (node.nodeValue || '').trim();
    if (!text) continue;
    const el = node.parentElement;
    if (!el || !isVisible(el)) continue;
    if (el.closest('svg')) continue;
    const cs = getComputedStyle(el);
    const size = parseFloat(cs.fontSize);
    if (!Number.isFinite(size) || size < 0.5) continue;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) firstViewTextNodes += 1;
    const fam = (cs.fontFamily || '').split(',')[0].replace(/["']/g, '').trim() || 'unknown';
    famChars.set(fam, (famChars.get(fam) || 0) + text.replace(/\\s+/g, '').length);
    if (size > displaySize) {
      displaySize = size;
      displayFamily = fam;
    }
    const fg = parseCss(cs.color);
    if (!fg) continue;
    const bg = resolveBg(el);
    const shown = text.replace(/\\s+/g, ' ').slice(0, 40);
    if (bg.unknown) {
      const ukey = 'u|' + fam + '|' + shown;
      if (!seenContrast.has(ukey) && contrastUnknown.length < 20) {
        contrastUnknown.push({ tag: el.tagName.toLowerCase(), label: shown, reason: bg.unknown });
      }
      seenContrast.add(ukey);
      continue;
    }
    const fgRgb = fg[3] >= 1
      ? [fg[0], fg[1], fg[2]]
      : composite(fg, [bg.color[0], bg.color[1], bg.color[2], 1]).slice(0, 3);
    const weight = Number(cs.fontWeight) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 600);
    const required = large ? 3 : 4.5;
    const ratio = Math.round(contrastRatio(fgRgb, bg.color) * 100) / 100;
    if (ratio + 0.005 >= required) continue;
    const fkey = 'f|' + hexOf(fg) + '|' + hexOf(bg.color) + '|' + Math.round(size);
    if (seenContrast.has(fkey) || contrastFailures.length >= 50) continue;
    seenContrast.add(fkey);
    contrastFailures.push({
      tag: el.tagName.toLowerCase(),
      label: shown,
      fontSize: Math.round(size * 10) / 10,
      large,
      color: hexOf(fg),
      background: hexOf(bg.color),
      ratio,
      required,
    });
  }

  // ---- 外观指纹（只记录，不做审美判断）----
  const colorHits = new Map();
  const bump = (c) => {
    const key = hexOf(c);
    colorHits.set(key, (colorHits.get(key) || 0) + 1);
  };
  const vw = document.documentElement.clientWidth || window.innerWidth;
  const vh = window.innerHeight;
  let sections = 0;
  let cards = 0;
  let columns = 1;
  const all = document.body ? document.body.querySelectorAll('*') : [];
  for (let i = 0; i < all.length && i < 5000; i += 1) {
    const el = all[i];
    const tag = el.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') continue;
    if (!isVisible(el)) continue;
    const cs = getComputedStyle(el);
    const bgc = parseCss(cs.backgroundColor);
    const rect = el.getBoundingClientRect();
    if (bgc && bgc[3] >= 0.5) bump(bgc);
    if (tag !== 'BODY' && tag !== 'HTML') {
      if (rect.height >= vh * 0.5 && rect.width >= vw * 0.5) sections += 1;
      const radius = parseFloat(cs.borderTopLeftRadius) || 0;
      const kids = el.children.length;
      if (radius >= 4 && bgc && bgc[3] >= 0.5 && kids >= 2 && kids <= 12
          && rect.width >= vw * 0.25 && rect.height >= 40 && rect.height <= vh * 0.9) cards += 1;
    }
    if (cs.display.indexOf('grid') === 0) {
      const tracks = (cs.gridTemplateColumns || '').trim();
      if (tracks && tracks !== 'none') {
        let depth = 0;
        let count = 0;
        let inTok = false;
        for (const ch of tracks) {
          if (ch === '(') depth += 1;
          else if (ch === ')') depth -= 1;
          else if (/\\s/.test(ch) && depth === 0) {
            if (inTok) {
              count += 1;
              inTok = false;
            }
            continue;
          }
          inTok = true;
        }
        if (inTok) count += 1;
        if (count > columns) columns = count;
      }
    }
  }
  const palette = Array.from(colorHits.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([color, count]) => ({ color, count }));
  let bodyFamily = 'unknown';
  let bodyCount = 0;
  for (const [fam, chars] of famChars) {
    if (chars > bodyCount) {
      bodyCount = chars;
      bodyFamily = fam;
    }
  }
  const pageBg = document.body ? resolveBg(document.body) : { color: [255, 255, 255] };

  const de = document.documentElement;
  const b = document.body;
  const brokenImages = images.filter((i) => !i.loaded);
  const uniqueRel = Array.from(new Set(relativeRefs));
  const pageWarnings = [];
  if (uniqueRel.length) {
    pageWarnings.push({
      code: 'relative-asset',
      message: uniqueRel.length + ' 处相对路径引图/资源；交付为单个 HTML（或只看这份 html）时会 404，改用 data: URI 或确认整目录一起交付',
      refs: uniqueRel.slice(0, 5),
    });
  }
  if (contrastUnknown.length) {
    pageWarnings.push({
      code: 'contrast-unknown',
      message: contrastUnknown.length + ' 处文字压在渐变/图片背景上，对比度无法自动判定，需人工或 DevTools 复核',
    });
  }
  return {
    title: document.title,
    tapFailures,
    fontFailures,
    images,
    brokenImages,
    contrastFailures,
    contrastUnknown,
    fingerprint: {
      bg: pageBg.unknown ? 'unknown' : hexOf(pageBg.color),
      palette,
      fonts: { display: displayFamily, body: bodyFamily },
      skeleton: { sections, cards, columns, firstViewTextNodes },
      viewport: vw + 'x' + vh,
    },
    warnings: pageWarnings,
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

    let shot = null;
    if (shotPath) {
      try {
        const opts = { format: 'png' };
        if (fullPage) {
          const metrics = await cdp.send('Page.getLayoutMetrics');
          const size = metrics.cssContentSize || metrics.contentSize || {};
          opts.clip = {
            x: 0,
            y: 0,
            width: Math.ceil(size.width || width),
            height: Math.ceil(size.height || height),
            scale: 1,
          };
          opts.captureBeyondViewport = true;
        }
        const grabbed = await cdp.send('Page.captureScreenshot', opts);
        mkdirSync(path.dirname(shotPath), { recursive: true });
        const buf = Buffer.from(grabbed.data, 'base64');
        writeFileSync(shotPath, buf);
        shot = { path: shotPath, bytes: buf.length, full: fullPage };
      } catch (err) {
        shot = { path: shotPath, error: String(err && err.message ? err.message : err) };
      }
    }

    await httpJson(port, `/json/close/${target.id}`).catch(() => {});
    cdp.close();

    const overflowFail = (data.overflow?.document > 1) || (data.overflow?.body > 1);
    const brokenImages = data.brokenImages || [];
    const contrastFailures = data.contrastFailures || [];
    const images = data.images || [];
    const contrastUnknown = data.contrastUnknown || [];
    const pass = !data.tapFailures?.length && !data.fontFailures?.length
      && !overflowFail && !consoleErrors.length && !exceptions.length
      && !loadError && !loadTimedOut
      && !brokenImages.length && !contrastFailures.length;

    return {
      url,
      title: data.title || '',
      pass,
      loadError,
      loadTimedOut,
      tap: { min: tap, minWidth: tapWidth, failures: data.tapFailures || [] },
      font: { min: fontMin, failures: data.fontFailures || [] },
      images: {
        total: images.length,
        broken: brokenImages.length,
        loaded: images.length - brokenImages.length,
        failures: brokenImages,
        anyRelativeRef: (data.warnings || []).some((w) => w.code === 'relative-asset'),
      },
      contrast: {
        rule: '正文 >=4.5:1；大字（>=24px，或 >=18.66px 且加粗）>=3:1',
        failures: contrastFailures,
        unknown: contrastUnknown,
      },
      fingerprint: data.fingerprint || null,
      warnings: data.warnings || [],
      shot,
      overflow: { ...data.overflow, fail: overflowFail },
      consoleErrors,
      exceptions,
    };
  } finally {
    cleanup();
  }
}

// ---- 外观账本（本机私有设计产物指纹；只提示，不阻断）----
const ledgerHome = process.env.DESIGNWISE_HOME || path.join(homedir(), '.designwise');
const ledgerPath = path.join(ledgerHome, 'ledger.jsonl');

// 账本只存"能认出这是哪次交付"的最小信息：查询串与锚点常含 token / 签名 / 会话参数，一律丢弃；
// `user:pass@` 是 basic auth 凭据，账本认交付不需要它，同样剥掉（只剥 scheme 之后到第一个 / 之前那段）。
function ledgerSafeUrl(raw) {
  const text = String(raw || '');
  if (!text) return '';
  const cut = text.split(/[?#]/)[0];
  const bare = cut.replace(/^([a-zA-Z][a-zA-Z0-9+.-]*:\/\/)[^/@]*@/, '$1');
  return bare.length > 300 ? `${bare.slice(0, 300)}…` : bare;
}

function readLedger(limit) {
  if (!existsSync(ledgerPath)) return [];
  const rows = [];
  for (const line of readFileSync(ledgerPath, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try {
      rows.push(JSON.parse(line));
    } catch {
      /* 跳过坏行，不因此失败 */
    }
  }
  return rows.slice(-limit).reverse();
}

function appendLedger(entry) {
  const dir = path.dirname(ledgerPath);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  // 目录/文件都按私有收口：账本属于本机设计记录，不是共享数据。
  // 已存在的目录或文件不会被 mkdirSync 改权限，故显式 chmod；失败不影响记录本身。
  try { chmodSync(dir, 0o700); } catch { /* 非 POSIX 或无权限时保持原样 */ }
  appendFileSync(ledgerPath, `${JSON.stringify(entry)}\n`, { mode: 0o600 });
  try { chmodSync(ledgerPath, 0o600); } catch { /* 同上 */ }
}

function familyHits(mine, theirs) {
  const hits = [];
  if (!mine || !theirs) return hits;
  if (mine.bg && mine.bg === theirs.bg && mine.bg !== 'unknown') hits.push(`同底色 ${mine.bg}`);
  const mineTop = (mine.palette || []).slice(0, 3).map((p) => p.color);
  const theirColors = (theirs.palette || []).map((p) => p.color);
  const overlap = mineTop.filter((c) => theirColors.includes(c));
  if (overlap.length >= 2) hits.push(`主色板重合 ${overlap.length} 色（${overlap.join(' ')}）`);
  const a = mine.skeleton || {};
  const b = theirs.skeleton || {};
  if (a.columns === b.columns && a.sections === b.sections && a.columns) {
    hits.push(`骨架同为 ${a.sections} 段 × ${a.columns} 列`);
  }
  return hits;
}

const chrome = urls.length ? findChrome() : '';
const reports = [];
for (const url of urls) {
  try {
    reports.push(await checkUrl(chrome, url));
  } catch (err) {
    reports.push({ url, pass: false, error: String(err && err.message ? err.message : err) });
  }
}

let ledger = null;
const ledgerNotes = [];
if (ledgerQuery || ledgerCheck || ledgerAdd) {
  const recent = readLedger(ledgerWindow);
  ledger = {
    path: ledgerPath,
    window: ledgerWindow,
    entries: recent.length,
    recent: recent.map((e) => ({
      ts: e.ts,
      project: e.project || '',
      title: e.title || '',
      url: ledgerSafeUrl(e.url),
      bg: e.fingerprint ? e.fingerprint.bg : undefined,
      skeleton: e.fingerprint ? e.fingerprint.skeleton : undefined,
    })),
  };

  if (ledgerCheck && reports.length) {
    const matches = [];
    for (const report of reports) {
      if (!report.fingerprint) continue;
      for (const prev of recent) {
        const hits = familyHits(report.fingerprint, prev.fingerprint);
        if (hits.length >= 2) {
          matches.push({
            url: report.url,
            with: prev.project || prev.title || prev.url || '(未命名)',
            ts: prev.ts,
            hits,
          });
        }
      }
      const own = matches.filter((m) => m.url === report.url);
      if (own.length) {
        report.warnings = report.warnings || [];
        report.warnings.push({
          code: 'ledger-family',
          message: `与最近 ${ledgerWindow} 个交付里的 ${own.length} 个外观同族（只提示，不阻断）：`
            + own.slice(0, 2).map((m) => `${m.with} → ${m.hits.join('、')}`).join(' | '),
        });
        ledgerNotes.push(`黄灯：${report.url} 与历史交付外观同族（${own.length} 个），确认这是有意的延续还是无意识重复`);
      }
    }
    ledger.matches = matches;
  }

  if (ledgerAdd && reports.length) {
    const added = [];
    for (const report of reports) {
      if (!report.fingerprint) continue;
      const entry = {
        ts: new Date().toISOString(),
        project: String(ledgerAdd).slice(0, 80),
        url: ledgerSafeUrl(report.url),
        title: String(report.title || '').slice(0, 80),
        fingerprint: report.fingerprint,
      };
      try {
        appendLedger(entry);
        added.push({ url: entry.url, ts: entry.ts });
      } catch (err) {
        ledger.error = String(err && err.message ? err.message : err);
      }
    }
    ledger.added = added;
  }
}

const shotFailed = reports.some((r) => r.shot && r.shot.error);

const payload = {
  unit: 'css-px',
  note: 'CSS px only; this does not prove Android dp compliance (use wm density + uiautomator bounds on device).',
  tap,
  tapWidth,
  fontMin,
  viewport: `${width}x${height}`,
  checks: {
    blocker: ['tap', 'font', 'overflow', 'consoleErrors', 'exceptions', 'images.broken', 'contrast.failures'],
    warning: ['images.anyRelativeRef', 'contrast.unknown', 'warnings'],
    note: '红灯阻断交付；绿灯/黄灯不改变退出码。对比度只算纯色背景，渐变/图片背景记 unknown 交人工。',
  },
  allPass: urls.length ? reports.every((r) => r.pass) : null,
  reports,
};
if (ledger) payload.ledger = ledger;
if (!urls.length) payload.mode = 'ledger';

process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
process.stderr.write('check-ui: 结果为 CSS px 采集，不等同于 Android dp 合规；原生界面需按 dp/真机复核。\n');

for (const note of ledgerNotes) process.stderr.write(`check-ui: ${note}\n`);
if (ledger && ledger.error) process.stderr.write(`check-ui: 账本写入失败（不影响页面检查结论）：${ledger.error}\n`);
if (shotFailed) {
  for (const r of reports) {
    if (r.shot && r.shot.error) process.stderr.write(`check-ui: 截图失败 ${r.shot.path}：${r.shot.error}\n`);
  }
}

if (ledger && ledger.added && ledger.added.length) {
  process.stderr.write(`check-ui: 已写入账本 ${ledger.added.length} 条 → ${ledgerPath}\n`);
}

const blockers = [];
for (const r of reports) {
  if (r.error) blockers.push(`${r.url}：${r.error}`);
  if (r.shot && r.shot.error) blockers.push(`${r.url}：截图失败`);
  if (r.pass) continue;
  if (r.loadError) blockers.push(`${r.url}：加载失败`);
  if (r.images && r.images.broken) blockers.push(`${r.url}：${r.images.broken} 张图片加载失败`);
  if (r.contrast && r.contrast.failures.length) blockers.push(`${r.url}：${r.contrast.failures.length} 处对比度不足`);
}
if (blockers.length) {
  process.stderr.write(`check-ui: 存在不达标项（${blockers.slice(0, 6).join('；')}）\n`);
  process.stderr.write('check-ui: 明细见 JSON 的 tap/font/overflow/consoleErrors/images/contrast\n');
}

if (shotFailed) process.exit(2);
if (!payload.allPass && urls.length) process.exit(1);
