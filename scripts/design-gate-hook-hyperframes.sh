#!/bin/bash
# design-gate-hook-hyperframes.sh — hyperframes-only command-layer gate
#
# 用途：只守护 DesignWise 入口层覆盖不到的外部渲染器 `hyperframes render`。
# DesignWise 自己的 render-video.js / render-video-seek.js / render-narration.sh
# 由 design-gate-check.js 在录制前校验，覆盖 npm run、子进程、bash -c、make 等
# 所有启动路径，不需要命令层重复解析。
#
# 已接入（2026-10-29）：PreToolUse(Bash) 指向本文件；legacy design-gate-hook.sh
# 保留在树内用于回滚，但不再注册。
#
# 行为：
#   - 命令里必须同时出现 hyperframes 与 render，否则立即放行；
#   - 时长取 --duration=<num>，否则项目 index.html 的 data-duration；
#   - 长片（≥45s）且项目内没有 direction-approved.md → exit 2；
#   - 时长无法判定且没有 Gate → exit 2；
#   - 显式 SKIP_DESIGN_GATE=1 → 放行。
# 已知边界：不解析 Python/Node 内部动态拼出的命令；不读取 .js 构建脚本。
#
# 依赖：python3；缺失时降级放行并告警（设计入口层仍是最后防线）。

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '⚠️ design-gate-hyperframes: 缺少 python3，命令层已降级放行（入口层仍保护 DesignWise 渲染器）。' >&2
  exit 0
fi

exec python3 -c "$(cat <<'PY'
import json
import os
import re
import sys
import time

GATE = "direction-approved.md"
MIN_LONG = 45.0
LOG_DIR = os.environ.get("DESIGN_GATE_LOG_DIR") or os.path.join(
    os.path.expanduser("~"), ".zcode", "hooks", "design-gate", "logs")


def log_block(kind, duration=None):
    try:
        os.makedirs(LOG_DIR, mode=0o700, exist_ok=True)
        day = time.strftime("%Y-%m-%d", time.localtime())
        path = os.path.join(LOG_DIR, "blocks-%s.jsonl" % day)
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
                  "source": "hook", "kind": kind}
        if isinstance(duration, (int, float)):
            record["duration"] = round(float(duration), 1)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except Exception:
        pass


def gate_ok(cwd):
    if not cwd or not os.path.isdir(cwd):
        return False
    p = os.path.abspath(cwd)
    for _ in range(3):
        if os.path.isfile(os.path.join(p, GATE)):
            return True
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return False


def html_duration(cwd):
    if not cwd:
        return None
    p = os.path.abspath(cwd)
    for _ in range(3):
        index = os.path.join(p, "index.html")
        if os.path.isfile(index):
            try:
                text = open(index, encoding="utf-8", errors="replace").read()
            except OSError:
                return None
            m = re.search(r'data-duration\s*=\s*["\']?\s*([0-9]+(?:\.[0-9]+)?)',
                          text, re.I)
            return float(m.group(1)) if m else None
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None


def skip_requested(cmd):
    """Only the rendering command's own leading assignment/export opts out.

    A trailing comment such as `npx hyperframes render # SKIP_DESIGN_GATE=1`
    must not disable the gate.
    """
    m = re.match(r"^\s*((?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*)", cmd)
    if m and "SKIP_DESIGN_GATE=1" in m.group(1).split():
        return True
    m = re.match(r"^\s*env\s+((?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*)", cmd)
    if m and "SKIP_DESIGN_GATE=1" in m.group(1).split():
        return True
    return bool(re.match(r"^\s*export\s+SKIP_DESIGN_GATE=1\s*(?:;|&&|$)", cmd))


def package_script_body(cwd, script):
    """Return the script body from package.json (cwd or up to two parents)."""
    if not cwd or not script:
        return None
    p = os.path.abspath(cwd)
    for _ in range(3):
        pkg = os.path.join(p, "package.json")
        if os.path.isfile(pkg):
            try:
                data = json.load(open(pkg, encoding="utf-8"))
            except (OSError, ValueError):
                return None
            scripts = data.get("scripts") if isinstance(data, dict) else None
            body = scripts.get(script) if isinstance(scripts, dict) else None
            return body if isinstance(body, str) else None
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None


WRAPPERS = {"npx", "npm", "pnpm", "yarn", "node", "bash", "sh", "zsh", "dash",
            "timeout", "env", "sudo", "nohup", "nice", "xargs", "command", "exec"}


def first_word(segment):
    s = segment.strip()
    while True:
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*=\S+\s+", s)
        if not m:
            break
        s = s[m.end():]
    return (s.split(None, 1)[0].lower() if s.split(None, 1) else "")


def mentions_hyperframes(cmd, cwd):
    low = cmd.lower()
    # Split into simple-command segments so `cd dir && hyperframes render`
    # and `timeout 120 hyperframes render` are still seen at command position.
    for segment in re.split(r"[;\n]|&&|\|\||\|", cmd):
        seg_low = segment.lower()
        first = first_word(segment)
        if first.startswith("hyperframes") and "render" in seg_low:
            return True
        if first in WRAPPERS and "hyperframes" in seg_low and "render" in seg_low:
            return True
    # Scaffolded HyperFrames projects pin the CLI in package.json scripts and
    # are commonly rendered with `npm run render` (official docs name that path).
    m = re.search(r"\b(?:npm|pnpm|yarn)\b[^;|&]*\b(?:run|run-script)\s+"
                  r"([A-Za-z0-9._:-]+)", cmd)
    if not m:
        # yarn/pnpm also accept the script name without `run`.
        m = re.search(r"\b(?:yarn|pnpm)\s+([A-Za-z0-9._:-]+)", cmd)
    if m:
        # `npm --prefix <dir> run render` / `pnpm -C <dir> run render`.
        prefix = re.search(r"(?:--prefix[= ]|(?:^|\s)-C\s*)([^\s;|&]+)", cmd)
        root = cwd
        if prefix:
            raw = os.path.expanduser(prefix.group(1))
            root = raw if os.path.isabs(raw) else os.path.join(cwd or ".", raw)
        body = (package_script_body(root, m.group(1)) or "").lower()
        if "hyperframes" in body and "render" in body:
            return True
    # Local shell wrappers: scan the referenced .sh for the hyperframes entry.
    for word in re.findall(r"[\w./~$-]+\.sh\b", cmd):
        path = word if os.path.isabs(word) else os.path.join(cwd or ".", word)
        try:
            if os.path.getsize(path) > (1 << 20):
                continue
            text = open(path, encoding="utf-8", errors="replace").read().lower()
        except OSError:
            continue
        if "hyperframes" in text and "render" in text:
            return True
    return False


def block(message, kind, duration=None):
    log_block(kind, duration)
    print("🛑 design-gate-hyperframes: " + message, file=sys.stderr)
    return 2


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as exc:
        # 输入不可解析时无法判断是否为 hyperframes；入口层仍保护 DesignWise 渲染器。
        print("⚠️ design-gate-hyperframes: 输入 JSON 无法解析（%s），放行。" % exc,
              file=sys.stderr)
        return 0
    if not isinstance(data, dict):
        return 0
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command", "")
    cwd = data.get("cwd", "")
    if not isinstance(command, str) or not command.strip():
        return 0
    if not mentions_hyperframes(command, cwd):
        return 0
    if skip_requested(command):
        return 0

    duration = None
    m = re.search(r"--duration\s*=\s*([0-9]+(?:\.[0-9]+)?)", command)
    if m:
        duration = float(m.group(1))
    if duration is None:
        duration = html_duration(cwd)

    if duration is None:
        if gate_ok(cwd):
            return 0
        return block("无法可靠判定 hyperframes 合成时长，且未找到 "
                     + GATE + "；按保守策略阻断。", "duration_unknown")
    if duration < MIN_LONG:
        return 0
    if gate_ok(cwd):
        return 0
    return block("hyperframes 合成时长 %.0fs（≥%.0fs 长片），但项目内未找到 %s。"
                 % (duration, MIN_LONG, GATE), "long_render_no_gate", duration)


if __name__ == "__main__":
    sys.exit(main())
PY
)"
