#!/usr/bin/env node
'use strict';
/**
 * design-gate-check.js — 长片渲染入口的 Gate 校验（不依赖 Python、不依赖 Hook）。
 *
 * 保护条件（与 designwise/SKILL.md「Gate文件协议」一致）：
 *   - 合成时长 ≥45s 视为长片；
 *   - 长片渲染前，项目目录或上两级必须有 direction-approved.md；
 *   - 命令前导赋值 SKIP_DESIGN_GATE=1 是文档化的用户放行口，本模块同样接受。
 *
 * 为什么不放在 PreToolUse Hook 里做：Hook 只能看到命令行文本，无法覆盖
 * npm run / make / Python 子进程 / bash -c 等启动路径，还会误拦无关命令。
 * 放在渲染入口，任何启动方式都会走到同一处校验，且能在录制开始前退出。
 *
 * 阻断时向 ~/.zcode/hooks/design-gate/logs/blocks-YYYY-MM-DD.jsonl 追加一行
 * JSONL（时间/来源/类别/时长，不含完整命令与环境变量值）。日志失败不影响渲染。
 *
 * CLI 用法（供其他渲染入口或测试复用）：
 *   node design-gate-check.js --duration=60 [--entry=render-video.js] [--html=out.html]
 * 退出码：0 放行；2 阻断；其他非零表示用法错误。
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const GATE = 'direction-approved.md';
const MIN_LONG = 45;
const MAX_PARENT_HOPS = 2; // 自身 + 上两级，与 Hook 的 _gate_ok 保持一致
const LOG_DIR = process.env.DESIGN_GATE_LOG_DIR
  || path.join(os.homedir(), '.zcode', 'hooks', 'design-gate', 'logs');

function findGate(startDirs) {
  const seen = new Set();
  for (const start of startDirs) {
    if (!start) continue;
    let dir;
    try {
      dir = path.resolve(start);
    } catch {
      continue;
    }
    for (let hop = 0; hop <= MAX_PARENT_HOPS; hop += 1) {
      if (seen.has(dir)) break;
      seen.add(dir);
      try {
        if (fs.existsSync(path.join(dir, GATE))) return dir;
      } catch {
        /* 目录不可读：继续向上找 */
      }
      const up = path.dirname(dir);
      if (up === dir) break;
      dir = up;
    }
  }
  return null;
}

function logBlock({ entry, duration }) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true, mode: 0o700 });
    const now = new Date();
    const day = now.toISOString().slice(0, 10);
    const file = path.join(LOG_DIR, `blocks-${day}.jsonl`);
    const record = {
      ts: now.toISOString(),
      source: 'entry',
      kind: 'long_render_no_gate',
      entry: typeof entry === 'string' ? path.basename(entry).slice(0, 64) : 'unknown',
      duration: Math.round(Number(duration) * 10) / 10,
    };
    fs.appendFileSync(file, JSON.stringify(record) + '\n', { mode: 0o600 });
  } catch {
    /* 观测失败绝不能影响渲染判断 */
  }
}

function blockMessage(duration) {
  return [
    `🛑 design-gate: 该合成时长 ${duration}s（≥${MIN_LONG}s 长片），但项目内未找到 ${GATE}。`,
    'huashu-design 铁律：长片渲染前必须完成「三方向真实视觉给用户选择」（或用户明示豁免），',
    `并把选择/豁免记录写入项目目录的 ${GATE}（含：展示了哪几版、截图路径、用户的选择原话）。`,
    '补齐后重渲；用户当面明说跳过时，在该渲染命令前加 SKIP_DESIGN_GATE=1 显式放行。',
  ].join('\n');
}

/**
 * 在真正开始录制前调用。
 * @param {{duration: number, entry: string, startDirs: Array<string|null>}} opts
 * @returns {boolean} true 表示放行
 */
function enforce(opts) {
  const { duration, entry, startDirs } = opts || {};
  if (process.env.SKIP_DESIGN_GATE === '1') return true;
  const seconds = Number(duration);
  if (!Number.isFinite(seconds) || seconds < MIN_LONG) return true;
  if (findGate(startDirs || [])) return true;
  logBlock({ entry, duration: seconds });
  process.stderr.write(blockMessage(seconds) + '\n');
  return false;
}

module.exports = { enforce, findGate, MIN_LONG, GATE };

if (require.main === module) {
  const arg = (name) => {
    const hit = process.argv.find((a) => a.startsWith(`--${name}=`));
    return hit ? hit.slice(name.length + 3) : null;
  };
  const duration = Number(arg('duration'));
  const entry = arg('entry') || 'design-gate-check.js';
  const html = arg('html');
  if (!Number.isFinite(duration) || duration <= 0) {
    process.stderr.write('Usage: node design-gate-check.js --duration=<seconds> [--entry=<name>] [--html=<file>]\n');
    process.exit(64);
  }
  const startDirs = [];
  if (html) startDirs.push(path.dirname(path.resolve(html)));
  startDirs.push(process.cwd());
  process.exit(enforce({ duration, entry, startDirs }) ? 0 : 2);
}
