#!/bin/bash
# design-gate-hook.sh — PreToolUse(Bash) hook：长片渲染前检查设计流程 gate 文件
#
# 协议（见 designwise/SKILL.md「Gate文件协议」）：
#   - 时长 ≥45s 的长片渲染，项目目录或上两级没有 direction-approved.md → exit 2；
#   - 短片、入口源码明确短默认值（render-video*.js = 30s），
#     或无法判定时长但已确认 Gate → 放行；
#   - 无法判定时长且无 Gate、workspace 目标或控制流上下文 → exit 2（fail-closed）；
#   - 命令里显式带 SKIP_DESIGN_GATE=1（只认该渲染命令自己的前导赋值/导出环境）→ 放行。
#
# 实现：这里不再用「删引号 + 整串正则 + raw 兜底」。Python 嵌入脚本按 shell 词法
# 切分简单命令，解析引号拼接、选项、连接符、子 shell/花括号、常见包装器与嵌套
# `bash -c`，只在「该简单命令确实执行渲染入口」时检查 Gate；文本命令里的渲染字样
# 不再触发。条件/短路/循环/函数中无法可靠求值、且可能影响渲染上下文的，保守阻断。
#
# 行为上限不变：本地判断，无网络、无文件写入、无删除；只向 stderr 打印原因。
# 本 hook 不会被 skill 自动安装；只有用户手动配进 settings.json 后才生效。
#
# 覆盖范围：直接渲染入口、npm/node/npx/hyperframes、常见包装器、bash -c、子 shell/
# 花括号、无条件 cd 连接、明确 true/false 的分支、if/while/until 条件命令、空循环、
# 未调用函数定义、普通 shell 脚本内容检查；绝对路径 shell/npm/node 也按同一程序识别。
# 不保证：stdin 动态喂给 shell（... | bash）、远程执行（ssh/docker）、解释器内动态
# 拼命令、make / npm run build 等间接构建、非字面条件/循环、case、函数调用、
# workspace/filter/多个 workspace、命令替换/进程替换；这些无法可靠判定时失败关闭。
#
# 依赖：python3（解析 JSON 与 shell 词法）。缺失时按失败关闭（exit 2），不静默放行。

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '🛑 design-gate-hook: 缺少 python3，无法解析命令；按失败关闭。请安装 python3 或停用本 hook。' >&2
  exit 2
fi

exec python3 -c "$(cat <<'PY'
import json
import math
import os
import re
import sys

GATE = "direction-approved.md"
MIN_LONG = 45.0
RENDER_SCRIPTS = {"render-video.js", "render-video-seek.js"}
# 这两个渲染器的源码默认 DURATION=30（render-video.js / render-video-seek.js）。
RENDER_DEFAULTS = {"render-video.js": 30.0, "render-video-seek.js": 30.0}
SHELLS = {"bash", "sh", "zsh", "dash"}
KEYWORDS = {"then", "do", "else", "fi", "done", "esac", "elif"}
# 未求值的控制流保留字；是否阻断取决于它是否可能影响渲染/Gate。
CONTROL_WORDS = {"if", "elif", "while", "until", "for", "case"}
# 会改变执行上下文或触发渲染的词。
STATE_WORDS = {"cd", "export", "unset", "source", ".", "eval", "exec",
               "builtin", "pushd", "popd"}


def fail(message: str) -> None:
    print("🛑 design-gate-hook: " + message, file=sys.stderr)
    sys.exit(2)


class Tok:
    __slots__ = ("kind", "value", "quoted", "bad")

    def __init__(self, kind: str, value: str, quoted: bool = False,
                 bad: bool = False) -> None:
        self.kind = kind
        self.value = value
        self.quoted = quoted
        self.bad = bad


class Ctx:
    def __init__(self, cwd, prev=None, vars=None, env=None, exported=None,
                 tainted=False, functions=None, dirstack=None, function_defs=None):
        self.cwd = cwd
        self.prev = prev
        self.vars = dict(vars or {})
        self.env = dict(env or {})
        self.exported = set(exported or ())
        # tainted: 当前 cwd/env 可能被未可靠求值的控制流改变；后续渲染必须失败关闭。
        self.tainted = tainted
        # 记录已剥离的函数定义及其函数体是否含渲染/状态变化。
        self.functions = dict(functions or ())
        self.function_defs = dict(function_defs or ())
        self.dirstack = list(dirstack or ())
        self.last_status = None

    def copy(self):
        child = Ctx(self.cwd, self.prev, dict(self.vars), dict(self.env),
                    set(self.exported), self.tainted, dict(self.functions),
                    list(self.dirstack), dict(self.function_defs))
        child.last_status = self.last_status
        return child


class Finding:
    def __init__(self, cwd, duration=None, skip=False, unresolved=False,
                 reason="", raw="", default=None, html_allowed=True):
        self.cwd = cwd
        self.duration = duration
        self.skip = skip
        self.unresolved = unresolved
        self.reason = reason
        self.raw = raw
        # 已知渲染器的源码默认时长；None 表示无法从入口确定。
        self.default = default
        # render-narration 的时长来自 timeline，不是 HTML 的 data-duration。
        self.html_allowed = html_allowed


_ANSI_SIMPLE = {
    "a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f",
    "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\",
    "'": "'", '"': '"', "?": "?",
}


def _ansi_escape(s: str, j: int):
    """Decode a bash $'...' escape at s[j]=='\\'. Return (text, next, bad)."""
    if j + 1 >= len(s):
        return "\\", j + 1, True
    esc = s[j + 1]
    if esc in _ANSI_SIMPLE:
        return _ANSI_SIMPLE[esc], j + 2, False
    if esc in "01234567":
        k = j + 1
        while k < len(s) and k < j + 4 and s[k] in "01234567":
            k += 1
        try:
            return chr(int(s[j + 1:k], 8)), k, False
        except ValueError:
            return "", k, True
    if esc in ("x", "u", "U"):
        limit = {"x": 2, "u": 4, "U": 8}[esc]
        k = j + 2
        while k < len(s) and k < j + 2 + limit and s[k] in "0123456789abcdefABCDEF":
            k += 1
        if k == j + 2:
            return "", k, True
        try:
            code = int(s[j + 2:k], 16)
            if code > 0x10FFFF:
                return "", k, True
            return chr(code), k, False
        except ValueError:
            return "", k, True
    if esc == "c" and j + 2 < len(s):
        ch = s[j + 2]
        return chr(ord(ch.upper()) ^ 0x40), j + 3, False
    return esc, j + 2, True


def tokenize(s: str):
    """Shell-ish tokenizer: words (quotes concatenated), operators, redirections."""
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r":
            i += 1
            continue
        if c == "\\" and i + 1 < n and s[i + 1] == "\n":
            i += 2
            continue
        if c == "\n":
            toks.append(Tok("op", ";"))
            i += 1
            continue
        if c == "#" and (i == 0 or s[i - 1] in " \t\r\n;&|(){}"):
            while i < n and s[i] != "\n":
                i += 1
            continue
        if s.startswith("&&", i) or s.startswith("||", i) or s.startswith(";;", i):
            toks.append(Tok("op", s[i:i + 2]))
            i += 2
            continue
        if c in ";&|()":
            toks.append(Tok("op", c))
            i += 1
            continue
        if c in "{}" and (i == 0 or s[i - 1] in " \t\r\n;&|(){}") \
                and (i + 1 >= n or s[i + 1] in " \t\r\n;&|(){}"):
            toks.append(Tok("op", c))
            i += 1
            continue
        if c == "`":
            j, buf, esc = i + 1, [], False
            while j < n:
                ch = s[j]
                if esc:
                    buf.append(ch)
                    esc = False
                    j += 1
                    continue
                if ch == "\\":
                    esc = True
                    j += 1
                    continue
                if ch == "`":
                    break
                buf.append(ch)
                j += 1
            toks.append(Tok("op", "$("))
            toks.extend(tokenize("".join(buf)))
            toks.append(Tok("op", ")"))
            i = j + 1 if j < n else n
            continue
        if c == "$" and i + 1 < n and s[i + 1] == "(":
            toks.append(Tok("op", "$("))
            i += 2
            continue
        m = re.match(r"\d*>&\d+|\d*&>>?|\d*>>?|\d*<<<|\d*<<", s[i:])
        if m and (i == 0 or s[i - 1] in " \t\r\n;&|(){}"):
            toks.append(Tok("redirect", m.group(0)))
            i += m.end()
            continue
        buf, quoted, started, bad_word = [], False, False, False
        while i < n:
            c = s[i]
            if c in " \t\r\n;&|()<>":
                break
            if c in "{}" and (i == 0 or s[i - 1] in " \t\r\n;&|(){}") \
                    and (i + 1 >= n or s[i + 1] in " \t\r\n;&|(){}"):
                break
            if c == "\\":
                if i + 1 < n:
                    if s[i + 1] == "\n":
                        i += 2
                        continue
                    buf.append(s[i + 1])
                    i += 2
                    quoted = started = True
                    continue
                i += 1
                continue
            if c == "'":
                quoted = started = True
                j = i + 1
                while j < n and s[j] != "'":
                    buf.append(s[j])
                    j += 1
                i = j + 1 if j < n else n
                continue
            if c == '"':
                quoted = started = True
                j = i + 1
                while j < n:
                    if s[j] == "\\" and j + 1 < n and s[j + 1] in '"\\$`\n':
                        if s[j + 1] != "\n":
                            buf.append(s[j + 1])
                        j += 2
                        continue
                    if s[j] == '"':
                        break
                    buf.append(s[j])
                    j += 1
                i = j + 1 if j < n else n
                continue
            if c == "$" and i + 1 < n and s[i + 1] == "'":
                quoted = started = True
                j = i + 2
                while j < n:
                    if s[j] == "\\":
                        text, j, bad = _ansi_escape(s, j)
                        buf.append(text)
                        bad_word = bad_word or bad
                        continue
                    if s[j] == "'":
                        break
                    buf.append(s[j])
                    j += 1
                i = j + 1 if j < n else n
                continue
            if c == "$" and i + 1 < n and s[i + 1] == '"':
                quoted = started = True
                j = i + 2
                while j < n:
                    if s[j] == "\\" and j + 1 < n and s[j + 1] in '"\\$`\n':
                        if s[j + 1] != "\n":
                            buf.append(s[j + 1])
                        j += 2
                        continue
                    if s[j] == '"':
                        break
                    buf.append(s[j])
                    j += 1
                i = j + 1 if j < n else n
                continue
            if c == "$" and i + 1 < n and s[i + 1] == "(":
                break
            buf.append(c)
            i += 1
            started = True
        if started or buf:
            toks.append(Tok("word", "".join(buf), quoted, bad_word))
        else:
            i += 1
    return toks


def _heredoc_markers(line: str):
    """Return [(start, delimiter)] for heredocs whose << is outside quotes."""
    markers = []
    i, n = 0, len(line)
    quote = None
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"' and i + 1 < n:
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if line.startswith("<<<", i):
            i += 3
            continue
        if line.startswith("<<", i):
            j = i + 2
            if j < n and line[j] == "-":
                j += 1
            while j < n and line[j] in " \t":
                j += 1
            if j < n and line[j] in ("'", '"'):
                j += 1
            k = j
            while k < n and (line[k].isalnum() or line[k] in "_.-"):
                k += 1
            delim = line[j:k]
            if delim:
                markers.append((i, delim))
            i = k if k > i else i + 2
            continue
        i += 1
    return markers


def strip_heredocs(s: str) -> str:
    """Remove heredoc bodies (data), unless the heredoc is attached to a shell.

    A body fed to `bash/sh/zsh/dash` is executable; keep it so the parser can see
    render commands inside.  Other bodies are text and must not cause false blocks.
    """
    lines = s.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        markers = _heredoc_markers(line)
        for start, delim in markers:
            prefix = line[:start]
            shell_fed = bool(re.search(r"(?:^|[;&|(){}]\s*)(?:bash|sh|zsh|dash)\b", prefix))
            body_lines = []
            while i < len(lines):
                body = lines[i]
                i += 1
                if body.strip() == delim:
                    break
                body_lines.append(body)
            if shell_fed:
                out.extend(body_lines)
            out.append("")
    return "\n".join(out)


def _expand_word(word: str, vars_map: dict) -> str:
    def repl(m):
        name = m.group(1) or m.group(2)
        return vars_map.get(name, m.group(0))

    return re.sub(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))", repl, word)


def _is_assign(word: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word))


def _split_assign(word: str):
    name, _, value = word.partition("=")
    return name, value


def _apply_assignments(ctx: Ctx, assignments, export=False) -> None:
    for item in assignments:
        name, value = _split_assign(item)
        ctx.vars[name] = value
        if export or name in ctx.exported:
            ctx.env[name] = value


def _resolve_dir(target: str, base):
    # 不读 Hook 进程环境；~ 由 _do_cd 用命令自己的 HOME 解析。
    if not target or "$" in target or "*" in target or "?" in target \
            or target.startswith("~"):
        return None
    if not os.path.isabs(target):
        if not base:
            return None
        target = os.path.join(base, target)
    return os.path.realpath(target)


def _do_cd(args, ctx: Ctx, local_vars: dict):
    """Apply cd only when the target directory is known to exist.

    Returns True/False for a definite success/failure, None when the target is
    dynamic/unknown.  A failed cd must not change cwd: shell keeps the previous
    directory, and pretending otherwise both hides bypasses and creates false
    blocks.  Dynamic targets taint the context instead of guessing.
    """
    targets = []
    end_opts = False
    for tok in args:
        value = _expand_word(tok.value, local_vars)
        if not end_opts and value == "--":
            end_opts = True
            continue
        if not end_opts and value in ("-P", "-L", "-e", "-@", "-p"):
            continue
        if not end_opts and value.startswith("-") and value != "-":
            continue
        targets.append(value)
    home = ctx.env.get("HOME") or local_vars.get("HOME") or ctx.vars.get("HOME")
    if len(targets) == 0:
        target = home
        if not target:
            ctx.tainted = True
            ctx.last_status = None
            return None
    elif len(targets) == 1:
        target = targets[0]
    else:
        ctx.last_status = False
        return False
    if target.startswith("~"):
        if target == "~" or target.startswith("~/"):
            if not home:
                ctx.tainted = True
                ctx.last_status = None
                return None
            target = home + target[1:]
        else:
            # ~user / 其它 shell 展开不读取 Hook 进程账户数据库。
            ctx.tainted = True
            ctx.last_status = None
            return None
    if target == "-":
        target = ctx.prev
        if target is None:
            ctx.last_status = False
            return False
    resolved = _resolve_dir(target, ctx.cwd)
    if resolved is None:
        ctx.tainted = True
        ctx.last_status = None
        return None
    if not os.path.isdir(resolved):
        ctx.last_status = False
        return False
    ctx.prev = ctx.cwd
    ctx.cwd = resolved
    ctx.last_status = True
    return True


def _gate_ok(directory) -> bool:
    if not directory or not os.path.isdir(directory):
        return False
    p = os.path.abspath(directory)
    for _ in range(3):
        if os.path.isfile(os.path.join(p, GATE)):
            return True
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return False


def _html_duration(directory):
    if not directory:
        return None
    p = os.path.abspath(directory)
    for _ in range(3):
        index = os.path.join(p, "index.html")
        if os.path.isfile(index):
            try:
                text = open(index, "r", encoding="utf-8", errors="replace").read()
            except OSError:
                return None
            m = re.search(r"data-duration\s*=\s*([\"']?)\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
            if m:
                try:
                    return float(m.group(2))
                except ValueError:
                    return None
            return None
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None


def _timeline_duration(args, ctx: Ctx, local_vars: dict):
    """Read render-narration.sh's actual record duration from timeline.json.

    Returns ("missing", None) when no --timeline is supplied (the script exits
    without rendering), ("ok", seconds) for a valid totalDuration, and
    ("invalid", None) when a declared timeline cannot be read/validated.
    """
    timeline = None
    for idx, tok in enumerate(args):
        value = _expand_word(tok.value, local_vars)
        if value.startswith("--timeline="):
            timeline = value.split("=", 1)[1]
        elif value == "--timeline" and idx + 1 < len(args):
            timeline = _expand_word(args[idx + 1].value, local_vars)
    if not timeline:
        return "missing", None
    if "$" in timeline or "*" in timeline or "?" in timeline or not ctx.cwd:
        return "invalid", None
    path = timeline if os.path.isabs(timeline) else os.path.join(ctx.cwd, timeline)
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        return "invalid", None
    try:
        if os.path.getsize(path) > (1 << 20):
            return "invalid", None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return "invalid", None
    total = data.get("totalDuration") if isinstance(data, dict) else None
    try:
        total = float(total)
    except (TypeError, ValueError):
        return "invalid", None
    if not (0 < total <= 7200):
        return "invalid", None
    # render-narration.sh 的 RECORD_DURATION = ceil(totalDuration + 1)
    return "ok", float(math.ceil(total + 1))


_JS_FLOAT = re.compile(
    r"^[ \t\r\n]*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def _parse_js_float(value: str):
    """Approximate JS parseFloat: accepts +60, 1e2, ' 60', 60abc."""
    m = _JS_FLOAT.match(value)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _duration_from_args(args, local_vars: dict):
    """Use the first explicit --duration, matching render-video*.js (`find`).

    designwise 的 render-video.js / render-video-seek.js 用
    `process.argv.find(a => a.startsWith('--duration='))` 扫描，随后
    `parseFloat`。两个渲染器都不读取空格形式 `--duration 60`；这里只承认
    `--duration=<num>`，第一个显式值生效（重复值不取 max）。
    """
    for tok in args:
        value = _expand_word(tok.value, local_vars)
        if value.startswith("--duration="):
            return _parse_js_float(value.split("=", 1)[1])
    return None


def _duration_ambiguous(args, local_vars: dict) -> bool:
    """Detect duration-like arguments whose value cannot be reliably resolved."""
    for idx, tok in enumerate(args):
        value = _expand_word(tok.value, local_vars)
        if tok.kind == "op" and value == "$(":
            return True
        if "$" in value or "`" in value:
            if value.startswith("$") or value.startswith("`") \
                    or "duration" in value.lower():
                return True
        if value.startswith("--duration="):
            if _parse_js_float(value.split("=", 1)[1]) is None:
                return True
    return False


def _extract_group(tokens, start: int, closer: str):
    stack = [closer]
    inner = []
    j = start
    while j < len(tokens):
        tok = tokens[j]
        if tok.kind == "op":
            if tok.value in ("(", "$("):
                stack.append(")")
                inner.append(tok)
            elif tok.value == "{":
                stack.append("}")
                inner.append(tok)
            elif tok.value in (")", "}"):
                if tok.value == stack[-1]:
                    stack.pop()
                    if not stack:
                        return j, inner
                    inner.append(tok)
                else:
                    inner.append(tok)
            else:
                inner.append(tok)
        else:
            inner.append(tok)
        j += 1
    return len(tokens), inner


def _raw(words) -> str:
    return " ".join(w.value for w in words)


def _analyze_program(prog: str, args, ctx: Ctx, skip: bool,
                     local_vars: dict, local_env: dict, depth: int):
    if ("*" in prog or "?" in prog) and "render" in prog.lower():
        return [Finding(ctx.cwd, unresolved=True,
                        reason="命令名含通配符，无法可靠解析；保守阻断")]
    base = os.path.basename(prog)
    # 绝对路径的 shell/npm/node 仍是同一可执行程序；不能用裸名匹配漏掉。
    name = base if "/" in prog else prog

    if prog == "cd":
        _do_cd(args, ctx, local_vars)
        return []

    if prog == "pushd":
        values = [t.value for t in args]
        if any(v.startswith("+") or v.startswith("-") and v not in ("-n",)
               for v in values) or "-n" in values:
            ctx.tainted = True
            return []
        targets = [v for v in values if not v.startswith("-") or v == "-"]
        if not targets:
            if ctx.dirstack:
                ctx.cwd, ctx.dirstack[-1] = ctx.dirstack[-1], ctx.cwd
                ctx.last_status = True
            else:
                ctx.last_status = False
            return []
        if len(targets) != 1:
            ctx.tainted = True
            return []
        old_cwd = ctx.cwd
        status = _do_cd([Tok("word", targets[0])], ctx, local_vars)
        if status is True:
            ctx.dirstack.append(old_cwd)
        elif status is None:
            ctx.tainted = True
        return []

    if prog == "popd":
        values = [t.value for t in args]
        if any(v.startswith("-") or v.startswith("+") for v in values):
            ctx.tainted = True
            return []
        if not ctx.dirstack:
            ctx.last_status = False
            return []
        ctx.prev = ctx.cwd
        ctx.cwd = ctx.dirstack.pop()
        ctx.last_status = True
        return []

    if prog == "export":
        noexport = False
        for tok in args:
            value = _expand_word(tok.value, local_vars)
            if value == "-p":
                continue
            if value == "-n":
                noexport = True
                continue
            if value.startswith("-"):
                continue
            if _is_assign(value):
                varname, val = _split_assign(value)
                ctx.vars[varname] = val
                if noexport:
                    ctx.env.pop(varname, None)
                    ctx.exported.discard(varname)
                else:
                    ctx.env[varname] = val
                    ctx.exported.add(varname)
            elif noexport:
                # export -n NAME 只移除导出属性，变量本身仍在当前 shell。
                ctx.env.pop(value, None)
                ctx.exported.discard(value)
            else:
                if value in ctx.vars:
                    ctx.env[value] = ctx.vars[value]
                ctx.exported.add(value)
        return []

    if prog in ("local", "readonly", "declare", "typeset"):
        export_attr = False
        unexport = False
        for tok in args:
            value = _expand_word(tok.value, local_vars)
            if value in ("-x", "+x"):
                export_attr = value == "-x"
                unexport = value == "+x"
                continue
            if value.startswith("-") or value.startswith("+"):
                if "x" in value[1:]:
                    export_attr = value.startswith("-")
                    unexport = value.startswith("+")
                continue
            if _is_assign(value):
                name, val = _split_assign(value)
                ctx.vars[name] = val
                if export_attr:
                    ctx.env[name] = val
                    ctx.exported.add(name)
                elif unexport:
                    ctx.env.pop(name, None)
                    ctx.exported.discard(name)
            elif export_attr:
                ctx.exported.add(value)
                if value in ctx.vars:
                    ctx.env[value] = ctx.vars[value]
            elif unexport:
                ctx.env.pop(value, None)
                ctx.exported.discard(value)
        return []

    if prog == "unset":
        for tok in args:
            name = _expand_word(tok.value, local_vars)
            if name.startswith("-"):
                continue
            ctx.vars.pop(name, None)
            ctx.env.pop(name, None)
            ctx.exported.discard(name)
        return []

    if prog == "env":
        return _parse_env(args, ctx, skip, local_vars, local_env, depth)

    if prog == "sudo":
        return _parse_sudo(args, ctx, skip, local_vars, local_env, depth)

    if prog == "command":
        i = 0
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            if args[i].value in ("-v", "-V"):
                return []  # lookup only, does not execute the command
            if args[i].value == "-p":
                i += 1
            else:
                i += 1
        # command 执行的是当前 shell 的 builtin（如 cd/export/source），状态必须回写。
        return parse_simple(args[i:], ctx, skip, depth + 1) if i < len(args) else []

    if prog == "builtin":
        if args and args[0].value == "cd":
            _do_cd(args[1:], ctx, local_vars)
            return []
        if args and args[0].value in ("export", "unset", "eval", "command", "type",
                                      "echo", "printf", "source", ".", "exec",
                                      "pushd", "popd"):
            return _analyze_program(args[0].value, args[1:], ctx, skip,
                                    local_vars, local_env, depth)
        return []

    if prog == "nohup":
        return _recurse(args, ctx, skip, local_vars, local_env, depth) if args else []

    if prog == "timeout":
        i = 0
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            value = args[i].value
            if value in ("-s", "--signal", "-k", "--kill-after"):
                i += 2
            else:
                i += 1
        i += 1  # duration
        return _recurse(args[i:], ctx, skip, local_vars, local_env, depth) if i < len(args) else []

    if prog == "exec":
        i = 0
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            if args[i].value == "-a":
                i += 2
            else:
                i += 1
        return _recurse(args[i:], ctx, skip, local_vars, local_env, depth) if i < len(args) else []

    if prog == "nice":
        i = 0
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            if args[i].value in ("-n", "--adjustment"):
                i += 2
            elif args[i].value.startswith("--adjustment="):
                i += 1
            else:
                i += 1
        return _recurse(args[i:], ctx, skip, local_vars, local_env, depth) if i < len(args) else []

    if prog == "stdbuf":
        i = 0
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            value = args[i].value
            if value in ("-i", "-o", "-e"):
                i += 2
            else:
                i += 1
        return _recurse(args[i:], ctx, skip, local_vars, local_env, depth) if i < len(args) else []

    if prog == "xargs":
        i = 0
        value_opts = {"-n", "-I", "-d", "-P", "-L", "-s", "-E", "-a",
                      "--max-args", "--replace", "--delimiter", "--max-procs",
                      "--max-lines", "--max-chars", "--eof", "--arg-file"}
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            value = args[i].value
            if value == "--":
                i += 1
                break
            if value in value_opts:
                i += 2
            elif any(value.startswith(v + "=") for v in value_opts if v.startswith("--")):
                i += 1
            else:
                i += 1
        return _recurse(args[i:], ctx, skip, local_vars, local_env, depth) if i < len(args) else []

    if name in SHELLS:
        return _parse_shell(name, args, ctx, skip, local_vars, local_env, depth)

    if name == "npx":
        return _parse_npx(args, ctx, skip, local_vars, local_env, depth)

    if name in ("npm", "pnpm", "yarn"):
        return _parse_npm(name, args, ctx, skip, local_vars, local_env, depth)

    if re.match(r"^hyperframes(@[A-Za-z0-9._-]+)?$", name):
        i = 0
        while i < len(args) and args[i].value.startswith("-") and args[i].value != "-":
            i += 1
        if i < len(args) and args[i].value == "render":
            rest = args[i + 1:]
            dur = _duration_from_args(rest, local_vars)
            amb = _duration_ambiguous(rest, local_vars)
            return [Finding(ctx.cwd, dur, skip, raw=_raw([Tok("word", prog)] + args),
                            unresolved=amb,
                            reason="显式时长参数含未解析值" if amb else "")]
        return []

    if name == "node":
        return _parse_node(args, ctx, skip, local_vars, local_env, depth)

    if prog in ("source", "."):
        if args:
            script = _expand_word(args[0].value, local_vars)
            if os.path.basename(script) == "render-narration.sh":
                status, dur = _timeline_duration(args[1:], ctx, local_vars)
                if status == "missing":
                    return []  # script exits before rendering without --timeline
                if status == "invalid":
                    return [Finding(ctx.cwd, unresolved=True,
                                    reason="render-narration 的 timeline 无法可靠解析")]
                return [Finding(ctx.cwd, dur, skip, raw=_raw(args),
                                html_allowed=False)]
            return _script_findings(script, ctx, skip, depth, same_shell=True)
        return []

    if prog == "eval":
        if not args:
            return []
        inner = " ".join(_expand_word(t.value, local_vars) for t in args)
        # eval 在当前 shell 执行；cd/export 必须回写到同一上下文。
        ctx.vars = dict(local_vars)
        ctx.env = dict(local_env)
        ctx.exported = set(local_env)
        return parse_tokens(tokenize(strip_heredocs(inner)), ctx, skip, depth + 1)

    if base == "render-narration.sh":
        status, dur = _timeline_duration(args, ctx, local_vars)
        if status == "missing":
            return []  # script exits before rendering without --timeline
        if status == "invalid":
            return [Finding(ctx.cwd, unresolved=True,
                            reason="render-narration 的 timeline 无法可靠解析")]
        return [Finding(ctx.cwd, dur, skip, raw=_raw([Tok("word", prog)] + args),
                        html_allowed=False)]

    direct = _inspect_direct_script(prog, ctx, skip, depth)
    if direct:
        return direct

    if base in RENDER_SCRIPTS:
        dur = _duration_from_args(args, local_vars)
        amb = _duration_ambiguous(args, local_vars)
        return [Finding(ctx.cwd, dur, skip, raw=_raw([Tok("word", prog)] + args),
                        default=RENDER_DEFAULTS.get(base), html_allowed=False,
                        unresolved=amb,
                        reason="显式时长参数含未解析值" if amb else "")]

    return []


def _recurse(words, ctx: Ctx, skip: bool, local_vars: dict, local_env: dict, depth: int):
    if not words:
        return []
    child = ctx.copy()
    child.vars = dict(local_vars)
    child.env = dict(local_env)
    child.exported = set(local_env)
    return parse_simple(words, child, skip, depth + 1)


def _parse_inner_string(inner: str, ctx: Ctx, skip: bool, local_vars: dict,
                        local_env: dict, cwd_override, depth: int):
    child = ctx.copy()
    child.vars = dict(local_vars)
    child.env = dict(local_env)
    child.exported = set(local_env)
    if cwd_override:
        child.cwd = _resolve_dir(cwd_override, ctx.cwd)
    return parse_tokens(tokenize(strip_heredocs(inner)), child, skip, depth + 1)


def _parse_env(args, ctx: Ctx, skip: bool, local_vars: dict, local_env: dict, depth: int):
    i = 0
    cwd = None
    while i < len(args):
        value = args[i].value
        if value == "--":
            i += 1
            break
        if value in ("-i", "--ignore-environment"):
            local_env = {}
            skip = False
            i += 1
            continue
        if value in ("-u", "--unset") or (value.startswith("-u") and value != "-u"):
            if value not in ("-u", "--unset"):
                name = value[2:]
                i += 1
            elif i + 1 < len(args):
                name = args[i + 1].value
                i += 2
            else:
                i += 1
                continue
            local_env.pop(name, None)
            if name == "SKIP_DESIGN_GATE":
                skip = False
            continue
        if value.startswith("--unset="):
            name = value.split("=", 1)[1]
            local_env.pop(name, None)
            if name == "SKIP_DESIGN_GATE":
                skip = False
            i += 1
            continue
        if value in ("-C", "--chdir"):
            if i + 1 < len(args):
                cwd = args[i + 1].value
                i += 2
            else:
                i += 1
            continue
        if value.startswith("--chdir="):
            cwd = value.split("=", 1)[1]
            i += 1
            continue
        if value in ("-S", "--split-string"):
            if i + 1 < len(args):
                return _parse_inner_string(args[i + 1].value, ctx, skip,
                                           local_vars, local_env, cwd, depth)
            i += 1
            continue
        if value.startswith("--split-string="):
            return _parse_inner_string(value.split("=", 1)[1], ctx, skip,
                                       local_vars, local_env, cwd, depth)
        if value.startswith("-") and value != "-":
            i += 1
            continue
        if _is_assign(value):
            name, val = _split_assign(value)
            local_vars[name] = val
            local_env[name] = val
            i += 1
            continue
        break
    return _parse_inner_words(args[i:], ctx, skip, local_vars, local_env, cwd, depth)


def _parse_inner_words(words, ctx: Ctx, skip: bool, local_vars: dict,
                       local_env: dict, cwd_override, depth: int):
    if not words:
        return []
    child = ctx.copy()
    child.vars = dict(local_vars)
    child.env = dict(local_env)
    child.exported = set(local_env)
    if cwd_override:
        child.cwd = _resolve_dir(cwd_override, ctx.cwd)
    return parse_simple(words, child, skip, depth + 1)


def _parse_sudo(args, ctx: Ctx, skip: bool, local_vars: dict, local_env: dict, depth: int):
    value_opts = {"-u", "--user", "-g", "--group", "-p", "--prompt", "-C",
                  "--close-from", "-h", "--host", "-r", "--role", "-t", "--type",
                  "-T", "--command-timeout", "-R", "--chroot", "-D", "--chdir",
                  "-U", "--other-user"}
    i = 0
    cwd = None
    while i < len(args):
        value = args[i].value
        if value == "--":
            i += 1
            break
        if value in value_opts:
            if value in ("-D", "--chdir") and i + 1 < len(args):
                cwd = args[i + 1].value
            i += 2
            continue
        if value.startswith("--chdir="):
            cwd = value.split("=", 1)[1]
            i += 1
            continue
        if value.startswith("-") and value != "-":
            i += 1
            continue
        if _is_assign(value):
            name, val = _split_assign(value)
            local_vars[name] = val
            local_env[name] = val
            i += 1
            continue
        break
    return _parse_inner_words(args[i:], ctx, skip, local_vars, local_env, cwd, depth)


def _shell_script_path(script: str, ctx: Ctx):
    if not script or "$" in script or "*" in script or "?" in script:
        return None
    path = script
    if not os.path.isabs(path):
        if not ctx.cwd:
            return None
        path = os.path.join(ctx.cwd, path)
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            head = fh.read(256).decode("utf-8", "replace")
    except OSError:
        return None
    first = head.splitlines()[0] if head.splitlines() else ""
    if path.endswith(".sh") or re.match(r"#!.*\b(?:bash|sh|zsh|dash)\b", first):
        return path
    return None


def _inspect_direct_script(prog: str, ctx: Ctx, skip: bool, depth: int):
    if "/" not in prog and not prog.startswith("."):
        return []
    path = _shell_script_path(prog, ctx)
    if not path:
        return []
    return _script_findings(prog, ctx, skip, depth, same_shell=False)


def _script_findings(script: str, ctx: Ctx, skip: bool, depth: int, same_shell: bool = False):
    if not script:
        return []
    if ("*" in script or "?" in script) and "render" in script.lower():
        return [Finding(ctx.cwd, unresolved=True,
                        reason="脚本路径含通配符，无法可靠解析；保守阻断")]
    if "$" in script or "`" in script or script.startswith("~"):
        return [Finding(ctx.cwd, unresolved=True,
                        reason="脚本路径含未解析值；保守阻断")]
    path = script
    if not os.path.isabs(path):
        if not ctx.cwd:
            return []
        path = os.path.join(ctx.cwd, path)
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        return []
    try:
        if os.path.getsize(path) > (1 << 20):
            return [Finding(ctx.cwd, unresolved=True, reason="脚本过大，无法可靠解析；保守阻断")]
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    child = ctx if same_shell else ctx.copy()
    if not same_shell:
        child.vars = dict(ctx.env)
        child.env = dict(ctx.env)
        child.exported = set(ctx.env)
    return parse_tokens(tokenize(strip_heredocs(text)), child, skip, depth + 1)


def _parse_shell(prog: str, args, ctx: Ctx, skip: bool,
                 local_vars: dict, local_env: dict, depth: int):
    i = 0
    c_flag = False
    noexec = False
    while i < len(args):
        value = args[i].value
        if value == "--":
            i += 1
            break
        if value.startswith("-") and value != "-":
            if "n" in value[1:]:
                noexec = True
            if "c" in value[1:]:
                c_flag = True
                i += 1
                break
            if value in ("-o", "+o", "-O", "+O"):
                i += 2
                continue
            i += 1
            continue
        break
    if i >= len(args):
        return []
    if noexec:
        return []
    if c_flag:
        inner = _expand_word(args[i].value, local_vars)
        child = ctx.copy()
        child.vars = dict(local_env)
        child.env = dict(local_env)
        child.exported = set(local_env)
        return parse_tokens(tokenize(strip_heredocs(inner)), child, skip, depth + 1)
    script = _expand_word(args[i].value, local_vars)
    if os.path.basename(script) == "render-narration.sh":
        status, dur = _timeline_duration(args[i + 1:], ctx, local_vars)
        if status == "missing":
            return []
        if status == "invalid":
            return [Finding(ctx.cwd, unresolved=True,
                            reason="render-narration 的 timeline 无法可靠解析")]
        return [Finding(ctx.cwd, dur, skip, raw=_raw([Tok("word", prog)] + args),
                        html_allowed=False)]
    # 普通 shell 脚本也可能调用渲染入口；读取脚本内容做同一套语义解析。
    return _script_findings(script, ctx, skip, depth, same_shell=False)


def _parse_npx(args, ctx: Ctx, skip: bool, local_vars: dict, local_env: dict, depth: int):
    i = 0
    while i < len(args):
        value = args[i].value
        if value == "--":
            i += 1
            break
        if value in ("-p", "--package"):
            i += 2
            continue
        if value.startswith("--package="):
            i += 1
            continue
        if value.startswith("-") and value != "-":
            i += 1
            continue
        break
    return _parse_inner_words(args[i:], ctx, skip, local_vars, local_env, None, depth)


def _npm_flag_value(args, i):
    return args[i + 1].value if i + 1 < len(args) else None


def _parse_npm(prog: str, args, ctx: Ctx, skip: bool,
               local_vars: dict, local_env: dict, depth: int):
    """Parse npm/pnpm/yarn run target options.

    Verified semantics:
      - npm accepts --workspace/-w and --prefix after the script name.
      - pnpm run stops parsing at the script name; later flags go to the script.
        pnpm's own -C/--dir is accepted before the script, while -w/-F/-r are
        workspace selectors that cannot be resolved here.
      - yarn is not installed here; target-changing flags are fail-closed rather
        than assuming npm semantics.
    """
    i = 0
    cwd = None
    script = None
    rest = []
    workspace_unresolved = False
    after_ddash = False

    def mark_workspace(step=1, takes_value=False):
        nonlocal i, workspace_unresolved
        workspace_unresolved = True
        i += 2 if takes_value else step

    while i < len(args):
        value = args[i].value
        if value == "--":
            # npm/pnpm 的 -- 之后仍是 command/remain；不能因为 -- 直接放弃扫描。
            i += 1
            continue
        if value in ("run", "run-script"):
            i += 1
            break
        if value == "exec":
            return _parse_npx(args[i + 1:], ctx, skip, local_vars, local_env, depth)
        if prog == "npm":
            if value in ("--prefix", "-C"):
                cwd = _npm_flag_value(args, i)
                i += 2
                continue
            if value.startswith("--prefix="):
                cwd = value.split("=", 1)[1]
                i += 1
                continue
            if value in ("--workspace", "-w"):
                mark_workspace(takes_value=True)
                continue
            if value.startswith("--workspace=") or value.startswith("-w="):
                mark_workspace()
                continue
            if value in ("--workspaces", "--ws", "-ws", "--include-workspace-root"):
                mark_workspace()
                continue
            if value.startswith("--workspaces=") or value.startswith("--ws=") \
                    or value.startswith("--include-workspace-root="):
                mark_workspace()
                continue
            if value.startswith("-w") and not value.startswith("--") \
                    and value not in ("-w", "-ws"):
                mark_workspace()
                continue
        elif prog == "pnpm":
            if value in ("-C", "--dir"):
                cwd = _npm_flag_value(args, i)
                i += 2
                continue
            if value.startswith("-C") and len(value) > 2 and not value.startswith("--"):
                cwd = value[2:]
                i += 1
                continue
            if value.startswith("--dir="):
                cwd = value.split("=", 1)[1]
                i += 1
                continue
            if value in ("-F", "--filter", "--filter-prod"):
                mark_workspace(takes_value=True)
                continue
            if value.startswith("--filter=") or value.startswith("--filter-prod="):
                mark_workspace()
                continue
            # pnpm run 的 -w 是 workspace-root 开关，不是 npm 的 -w <name>。
            if value in ("-w", "--workspace-root", "-r", "--recursive",
                         "--workspaces", "--ws", "-ws", "--include-workspace-root"):
                mark_workspace()
                continue
            if value.startswith("--workspaces=") or value.startswith("--ws=") \
                    or value.startswith("--include-workspace-root="):
                mark_workspace()
                continue
            if value.startswith("-w") and not value.startswith("--") \
                    and value not in ("-w", "-ws"):
                mark_workspace()
                continue
        elif prog == "yarn":
            # 未在本机验证 yarn 的 --cwd/workspace 语义；不按 npm 猜测。
            if value in ("--cwd", "--workspace", "-w", "--filter", "-F"):
                mark_workspace(takes_value=True)
                continue
            if value in ("--workspaces", "--ws", "-ws", "-r", "--recursive",
                         "--include-workspace-root"):
                mark_workspace()
                continue
            if value.startswith("--workspaces=") or value.startswith("--ws=") \
                    or value.startswith("--include-workspace-root="):
                mark_workspace()
                continue
            if value.startswith("--cwd=") or value.startswith("--workspace="):
                mark_workspace()
                continue
            if value.startswith("-w") and not value.startswith("--") \
                    and value not in ("-w", "-ws"):
                mark_workspace()
                continue
        if value in ("--loglevel", "--reporter", "--cache", "--userconfig",
                     "--globalconfig", "--registry"):
            i += 2
            continue
        if value.startswith("-") and value != "-":
            i += 1
            continue
        if prog in ("yarn", "pnpm") and value == "render":
            script = _expand_word(value, local_vars)
            rest = args[i + 1:]
            break
        i += 1

    if script is None:
        while i < len(args):
            value = args[i].value
            if value == "--":
                # run 之后的 -- 表示“其后全部是脚本参数”；下一 token 是脚本名。
                i += 1
                after_ddash = True
                break
            if prog == "npm":
                if value in ("--prefix", "-C"):
                    cwd = _npm_flag_value(args, i)
                    i += 2
                    continue
                if value.startswith("--prefix="):
                    cwd = value.split("=", 1)[1]
                    i += 1
                    continue
                if value in ("--workspace", "-w"):
                    mark_workspace(takes_value=True)
                    continue
                if value.startswith("--workspace=") or value.startswith("-w="):
                    mark_workspace()
                    continue
                if value in ("--workspaces", "--ws", "-ws", "--include-workspace-root"):
                    mark_workspace()
                    continue
                if value.startswith("--workspaces=") or value.startswith("--ws=") \
                        or value.startswith("--include-workspace-root="):
                    mark_workspace()
                    continue
                if value.startswith("-w") and not value.startswith("--") \
                        and value not in ("-w", "-ws"):
                    mark_workspace()
                    continue
            elif prog == "pnpm":
                if value in ("-C", "--dir"):
                    cwd = _npm_flag_value(args, i)
                    i += 2
                    continue
                if value.startswith("-C") and len(value) > 2 and not value.startswith("--"):
                    cwd = value[2:]
                    i += 1
                    continue
                if value.startswith("--dir="):
                    cwd = value.split("=", 1)[1]
                    i += 1
                    continue
                if value in ("-F", "--filter", "--filter-prod"):
                    mark_workspace(takes_value=True)
                    continue
                if value.startswith("--filter=") or value.startswith("--filter-prod="):
                    mark_workspace()
                    continue
                if value in ("-w", "--workspace-root", "-r", "--recursive",
                             "--workspaces", "--ws", "-ws", "--include-workspace-root"):
                    mark_workspace()
                    continue
                if value.startswith("--workspaces=") or value.startswith("--ws=") \
                        or value.startswith("--include-workspace-root="):
                    mark_workspace()
                    continue
                if value.startswith("-w") and not value.startswith("--") \
                        and value not in ("-w", "-ws"):
                    mark_workspace()
                    continue
            elif prog == "yarn":
                if value in ("--cwd", "--workspace", "-w", "--filter", "-F"):
                    mark_workspace(takes_value=True)
                    continue
                if value.startswith("--cwd=") or value.startswith("--workspace="):
                    mark_workspace()
                    continue
                if value in ("--workspaces", "--ws", "-ws", "-r", "--recursive",
                             "--include-workspace-root"):
                    mark_workspace()
                    continue
                if value.startswith("--workspaces=") or value.startswith("--ws=") \
                        or value.startswith("--include-workspace-root="):
                    mark_workspace()
                    continue
                if value.startswith("-w") and not value.startswith("--") \
                        and value not in ("-w", "-ws"):
                    mark_workspace()
                    continue
            if value.startswith("-") and value != "-":
                i += 1
                continue
            break
        if i < len(args):
            script = _expand_word(args[i].value, local_vars)
            rest = args[i + 1:]

    if script is None:
        if workspace_unresolved:
            return [Finding(ctx.cwd, unresolved=True,
                            reason="npm/pnpm/yarn 目标目录或 workspace 范围无法可靠解析")]
        return []
    if "$" in script or "*" in script or "?" in script:
        return [Finding(ctx.cwd, unresolved=True,
                        reason="npm 脚本名含未解析变量；保守阻断")]
    if not re.match(r"^render($|[^A-Za-z0-9_])", script):
        return []

    # npm 在脚本名之后仍然解析 workspace/prefix；pnpm/yarn 的后续 token
    # 按各自文档传给脚本，不当作包管理器目标参数。
    if prog == "npm" and not after_ddash:
        j = 0
        while j < len(rest):
            value = rest[j].value
            if value == "--":
                break
            if value in ("--prefix", "-C"):
                cwd = _npm_flag_value(rest, j)
                j += 2
                continue
            if value.startswith("--prefix="):
                cwd = value.split("=", 1)[1]
                j += 1
                continue
            if value in ("--workspace", "-w"):
                workspace_unresolved = True
                j += 2
                continue
            if value.startswith("-w") and not value.startswith("--") \
                    and value not in ("-w", "-ws"):
                workspace_unresolved = True
                j += 1
                continue
            if value.startswith("--workspace=") or value.startswith("-w="):
                workspace_unresolved = True
                j += 1
                continue
            if value in ("--workspaces", "--ws", "-ws", "--include-workspace-root"):
                workspace_unresolved = True
                j += 1
                continue
            if value.startswith("--workspaces=") or value.startswith("--ws=") \
                    or value.startswith("--include-workspace-root="):
                workspace_unresolved = True
                j += 1
                continue
            j += 1
    elif prog == "yarn":
        # yarn 未安装，无法确认脚本名后的 target 参数到底属于 yarn 还是脚本；
        # 含目标语义的参数一律保守阻断，不把未实测假设写成“脚本参数”。
        for tok in rest:
            value = tok.value
            if value == "--":
                break
            if value in ("--cwd", "--workspace", "-w", "--filter", "-F",
                         "--workspaces", "--ws", "-ws", "-r", "--recursive",
                         "--include-workspace-root") \
                    or value.startswith("--cwd=") or value.startswith("--workspace=") \
                    or value.startswith("--workspaces=") or value.startswith("--ws=") \
                    or value.startswith("--include-workspace-root="):
                workspace_unresolved = True
                break

    if workspace_unresolved:
        return [Finding(ctx.cwd, unresolved=True,
                        reason="npm/pnpm/yarn 目标目录或 workspace 范围无法可靠解析")]

    child = ctx.copy()
    child.vars = dict(local_vars)
    child.env = dict(local_env)
    child.exported = set(local_env)
    if cwd:
        resolved = _resolve_dir(cwd, ctx.cwd)
        if resolved is None:
            return [Finding(ctx.cwd, unresolved=True,
                            reason="npm/pnpm/yarn 目标目录无法可靠解析")]
        child.cwd = resolved
    dur = _duration_from_args(rest, local_vars)
    amb = _duration_ambiguous(rest, local_vars)
    return [Finding(child.cwd, dur, skip, raw=_raw([Tok("word", prog)] + args),
                    unresolved=amb,
                    reason="显式时长参数含未解析值" if amb else "")]


def _parse_node(args, ctx: Ctx, skip: bool, local_vars: dict, local_env: dict, depth: int):
    value_opts = {"-r", "--require", "--loader", "--experimental-loader",
                  "--import", "--inspect-port", "--max-old-space-size",
                  "--title", "--redirect-warnings", "--diagnostic-dir",
                  "--icu-data-dir", "--openssl-config", "--tls-cipher-list",
                  "--use-largepages", "--v8-pool-size", "--stack-trace-limit",
                  "--heapsnapshot-signal", "--report-directory", "--report-filename",
                  "--experimental-policy", "--conditions", "--input-type", "--env-file"}
    i = 0
    while i < len(args):
        value = args[i].value
        if value == "--":
            i += 1
            break
        if value in ("-e", "--eval", "-p", "--print"):
            return []
        if value in ("-v", "--version", "-h", "--help", "--check"):
            return []
        if value in value_opts:
            i += 2
            continue
        if value.startswith("-") and value != "-":
            i += 1
            continue
        break
    if i >= len(args):
        return []
    script = _expand_word(args[i].value, local_vars)
    if "$" in script or "`" in script or script.startswith("~"):
        return [Finding(ctx.cwd, unresolved=True,
                        reason="node 脚本路径含未解析值；保守阻断")]
    if "*" in script:
        if "render" in script:
            return [Finding(ctx.cwd, unresolved=True, reason="node 脚本路径含通配符；保守阻断")]
        return []
    script_base = os.path.basename(script)
    if script_base in RENDER_SCRIPTS:
        rest = args[i + 1:]
        dur = _duration_from_args(rest, local_vars)
        amb = _duration_ambiguous(rest, local_vars)
        return [Finding(ctx.cwd, dur, skip, raw=_raw(args),
                        default=RENDER_DEFAULTS.get(script_base),
                        html_allowed=False, unresolved=amb,
                        reason="显式时长参数含未解析值" if amb else "")]
    return []


def parse_simple(words, ctx: Ctx, inherited_skip: bool, depth: int):
    if depth > 10:
        return [Finding(ctx.cwd, unresolved=True, reason="嵌套过深")]
    if any(getattr(t, "bad", False) for t in words):
        return [Finding(ctx.cwd, unresolved=True,
                        reason="ANSI-C 转义无法可靠解析；保守阻断")]
    i = 0
    while i < len(words):
        value = words[i].value
        if value == "!":
            i += 1
            continue
        if value == "time":
            i += 1
            while i < len(words) and words[i].value.startswith("-"):
                i += 1
            continue
        break
    words = words[i:]
    assignments = []
    i = 0
    while i < len(words) and _is_assign(words[i].value):
        assignments.append(words[i].value)
        i += 1
    if i >= len(words):
        _apply_assignments(ctx, assignments, export=False)
        ctx.last_status = True
        return []
    prog_raw = words[i].value
    args = words[i + 1:]
    local_vars = dict(ctx.vars)
    local_env = dict(ctx.env)
    for item in assignments:
        name, value = _split_assign(item)
        local_vars[name] = value
        local_env[name] = value
    skip = (inherited_skip
            or local_env.get("SKIP_DESIGN_GATE") == "1"
            or ctx.env.get("SKIP_DESIGN_GATE") == "1")
    prog = _expand_word(prog_raw, local_vars)
    ctx.last_status = None
    if not skip and ctx.functions.get(prog):
        return [Finding(ctx.cwd, unresolved=True,
                        reason="调用可能改变渲染上下文的函数；保守阻断")]
    if "$" in prog or "`" in prog:
        return [Finding(ctx.cwd, unresolved=True,
                        reason="命令名含未解析变量；保守阻断")]
    if "*" in prog or "?" in prog:
        if "render" in prog.lower():
            return [Finding(ctx.cwd, unresolved=True,
                            reason="命令名含通配符，无法可靠解析；保守阻断")]
        joined = " ".join(w.value for w in args)
        if re.search(r"(?i)(render|hyperframes)", joined):
            return [Finding(ctx.cwd, unresolved=True, reason="命令名含通配符；保守阻断")]
        return []
    if prog in ("true", ":"):
        ctx.last_status = True
    elif prog == "false":
        ctx.last_status = False
    result = _analyze_program(prog, args, ctx, skip, local_vars, local_env, depth)
    if ctx.tainted:
        for finding in result:
            if not finding.skip:
                finding.unresolved = True
                finding.reason = "控制流使 cwd/env 无法可靠确定；按保守策略阻断"
    return result


def _cmd_start(tokens, idx: int) -> bool:
    if idx == 0:
        return True
    prev = tokens[idx - 1]
    if prev.kind == "op" and prev.value in (";", "&&", "||", "|", "&",
                                            "(", "{", "}"):
        return True
    return prev.kind == "word" and prev.value in (
        "then", "do", "else", "if", "elif", "while", "until", "!")


def _tokens_renderish(tokens) -> bool:
    """Broad scan used for dynamic command substitution values."""
    for tok in tokens:
        if tok.kind != "word":
            continue
        name = os.path.basename(tok.value).lower()
        if name in STATE_WORDS or name in {"npm", "pnpm", "yarn", "node", "npx",
                                           "bash", "sh", "zsh", "dash", "hyperframes"}:
            return True
        if "render" in name or "hyperframes" in name or "npm" in name or "node" in name:
            return True
    return False


def _tokens_relevant(tokens) -> bool:
    for i, tok in enumerate(tokens):
        if tok.kind != "word" or tok.quoted or not _cmd_start(tokens, i):
            continue
        name = os.path.basename(tok.value).lower()
        if name in STATE_WORDS or name in {"npm", "pnpm", "yarn", "node", "npx",
                                           "bash", "sh", "zsh", "dash", "hyperframes"}:
            return True
        if "render" in name or "hyperframes" in name:
            return True
    return False


def _if_parts(tokens, start: int):
    """Return (then_idx, else_idx, fi_idx) for the matching if block."""
    then_i = else_i = fi_i = None
    depth = 0
    paren = brace = 0
    for j in range(start + 1, len(tokens)):
        tok = tokens[j]
        if tok.kind == "op":
            if tok.value in ("(", "$("):
                paren += 1
            elif tok.value == ")":
                paren = max(0, paren - 1)
            elif tok.value == "{":
                brace += 1
            elif tok.value == "}":
                brace = max(0, brace - 1)
            continue
        if paren or brace:
            continue
        v = tok.value
        if v == "if" and _cmd_start(tokens, j):
            depth += 1
        elif v == "fi" and _cmd_start(tokens, j):
            if depth == 0:
                fi_i = j
                break
            depth -= 1
        elif depth == 0 and v == "then" and then_i is None and _cmd_start(tokens, j):
            then_i = j
        elif depth == 0 and v == "else" and then_i is not None and else_i is None \
                and _cmd_start(tokens, j):
            else_i = j
    return then_i, else_i, fi_i


def _loop_parts(tokens, start: int):
    """Return (do_idx, done_idx) for while/until/for."""
    do_i = done_i = None
    depth = 0
    paren = brace = 0
    for j in range(start + 1, len(tokens)):
        tok = tokens[j]
        if tok.kind == "op":
            if tok.value in ("(", "$("):
                paren += 1
            elif tok.value == ")":
                paren = max(0, paren - 1)
            elif tok.value == "{":
                brace += 1
            elif tok.value == "}":
                brace = max(0, brace - 1)
            continue
        if paren or brace:
            continue
        v = tok.value
        if v in ("while", "until", "for") and _cmd_start(tokens, j):
            depth += 1
        elif v == "done" and _cmd_start(tokens, j):
            if depth == 0:
                done_i = j
                break
            depth -= 1
        elif depth == 0 and v == "do" and do_i is None and _cmd_start(tokens, j):
            do_i = j
    return do_i, done_i


def _function_at(tokens, idx: int):
    """Return (name, end_idx, body) for a function definition at idx."""
    if tokens[idx].kind != "word":
        return None
    if idx + 3 < len(tokens) and tokens[idx + 1].value == "(" \
            and tokens[idx + 2].value == ")" and tokens[idx + 3].value == "{":
        name = tokens[idx].value
        end, body = _extract_group(tokens, idx + 4, "}")
        return name, end, body
    if tokens[idx].value == "function" and idx + 2 < len(tokens) \
            and tokens[idx + 1].kind == "word":
        name = tokens[idx + 1].value
        if tokens[idx + 2].value == "{":
            end, body = _extract_group(tokens, idx + 3, "}")
            return name, end, body
        if idx + 4 < len(tokens) and tokens[idx + 2].value == "(" \
                and tokens[idx + 3].value == ")" and tokens[idx + 4].value == "{":
            end, body = _extract_group(tokens, idx + 5, "}")
            return name, end, body
    return None


def _function_relevant(tokens) -> bool:
    """Conservative function-body scan: wrappers/absolute paths/quoted names count."""
    for tok in tokens:
        if tok.kind != "word":
            continue
        v = tok.value.lower()
        if v in STATE_WORDS or v in {"npm", "pnpm", "yarn", "node", "npx",
                                     "bash", "sh", "zsh", "dash", "hyperframes"}:
            return True
        if "render" in v or "hyperframes" in v or "npm" in v or "node" in v:
            return True
    return False


def _finalize_functions(ctx: Ctx) -> None:
    """Propagate dangerous function bodies through transitive calls."""
    changed = True
    while changed:
        changed = False
        for name, body in ctx.function_defs.items():
            if ctx.functions.get(name):
                continue
            relevant = _function_relevant(body)
            if not relevant:
                for tok in body:
                    if tok.kind == "word" and ctx.functions.get(tok.value):
                        relevant = True
                        break
            if relevant:
                ctx.functions[name] = True
                changed = True


def _strip_control(tokens, ctx: Ctx):
    """Strip definitely-dead / definitely-executed literal control blocks.

    Unknown control flow is intentionally left in place; parse_tokens then
    fails closed if it may affect a render or the Gate context.
    """
    out = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.kind == "word" and not tok.quoted and _cmd_start(tokens, i):
            if tok.value == "if":
                then_i, else_i, fi_i = _if_parts(tokens, i)
                if then_i is not None and fi_i is not None:
                    cond = [t.value for t in tokens[i + 1:then_i]
                            if t.kind == "word" and not t.quoted]
                    if cond in (["true"], ["false"]):
                        has_elif = any(t.kind == "word" and not t.quoted
                                       and t.value == "elif"
                                       for t in tokens[then_i:fi_i])
                        # `if false ... elif ...` 的后续分支可能执行；不把整块当死代码。
                        if not (cond == ["false"] and has_elif):
                            if cond == ["true"]:
                                selected = tokens[then_i + 1:else_i if else_i is not None else fi_i]
                            else:
                                selected = tokens[else_i + 1:fi_i] if else_i is not None else []
                            out.extend(_strip_control(selected, ctx))
                            i = fi_i + 1
                            continue
            if tok.value in ("while", "until"):
                do_i, done_i = _loop_parts(tokens, i)
                if do_i is not None and done_i is not None:
                    cond = [t.value for t in tokens[i + 1:do_i]
                            if t.kind == "word" and not t.quoted]
                    # while 条件为 false 是零次；until 条件为 true 才是零次。
                    if (tok.value == "while" and cond == ["false"]) \
                            or (tok.value == "until" and cond == ["true"]):
                        i = done_i + 1
                        continue
            if tok.value == "for":
                do_i, done_i = _loop_parts(tokens, i)
                if do_i is not None and done_i is not None:
                    between = tokens[i + 1:do_i]
                    # quoted 空词 "" 仍是一个迭代项，不能当作空列表。
                    words = [t for t in between if t.kind == "word"]
                    has_in = any(t.value == "in" for t in words)
                    after_in = []
                    seen_in = False
                    for t in words:
                        if t.value == "in":
                            seen_in = True
                            continue
                        if seen_in:
                            after_in.append(t.value)
                    if has_in and not after_in:
                        i = done_i + 1
                        continue
            fn = _function_at(tokens, i)
            if fn:
                name, end, body = fn
                ctx.function_defs[name] = body
                ctx.functions[name] = _function_relevant(body)
                i = end + 1
                continue
        out.append(tok)
        i += 1
    _finalize_functions(ctx)
    return out


def _case_parts(tokens, start: int):
    depth = 0
    paren = brace = 0
    for j in range(start + 1, len(tokens)):
        tok = tokens[j]
        if tok.kind == "op":
            if tok.value in ("(", "$("):
                paren += 1
            elif tok.value == ")":
                paren = max(0, paren - 1)
            elif tok.value == "{":
                brace += 1
            elif tok.value == "}":
                brace = max(0, brace - 1)
            continue
        if paren or brace:
            continue
        if tok.value == "case" and _cmd_start(tokens, j):
            depth += 1
        elif tok.value == "esac" and _cmd_start(tokens, j):
            if depth == 0:
                return j
            depth -= 1
    return None


def _render_subject(tokens) -> bool:
    """Whether a command position can plausibly reach a render entry.

    Fail-closed control-flow handling is only warranted when a render may
    actually run.  Without this guard, read-only composites such as
    `for d in ...; do (cd "$d" && find ...); done` are blocked merely for
    containing `cd`, which is a false positive.
    """
    executors = {"npm", "pnpm", "yarn", "node", "npx", "bash", "sh", "zsh",
                 "dash", "source", ".", "eval", "exec", "builtin"}
    wrappers = {"xargs", "nohup", "sudo", "env", "timeout", "nice", "stdbuf",
                "command", "time"}

    def is_render_name(value: str) -> bool:
        name = os.path.basename(value).lower()
        return (name in RENDER_SCRIPTS or name == "render-narration.sh"
                or name in executors
                or "render" in name or "hyperframes" in name)

    for i, tok in enumerate(tokens):
        if tok.kind != "word" or not _cmd_start(tokens, i):
            continue
        name = os.path.basename(tok.value).lower()
        if is_render_name(tok.value) and name not in wrappers:
            return True
        if name in wrappers:
            # 包装器本身可能是无害的（例如 xargs sha256sum）；只有它的参数里
            # 出现渲染入口时才当作渲染主体。
            for arg in tokens[i + 1:]:
                if arg.kind == "op":
                    break
                if arg.kind == "word" and is_render_name(arg.value):
                    return True
    return False


def _tokens_state_relevant(tokens, ctx: Ctx) -> bool:
    """Whether a control block can change cwd/env or call a dangerous function."""
    for i, tok in enumerate(tokens):
        if tok.kind != "word":
            continue
        if tok.value in ctx.functions and ctx.functions[tok.value]:
            return True
        if not _cmd_start(tokens, i):
            continue
        name = os.path.basename(tok.value).lower()
        if name in STATE_WORDS or name == "command":
            return True
    return False


def _control_risk(tokens, ctx: Ctx) -> bool:
    """Whether unparsed control flow may affect a render or context.

    State-changing control flow (cd/export/source/eval/functions/...) always
    fails closed: a condition can change cwd before a later render, and the
    condition command is not otherwise evaluated by the parser.  A block that
    only contains text or a render command does not change context; it is
    allowed when a Gate is already confirmed, and otherwise fails closed.
    If the command cannot reach a render at all, control flow is irrelevant
    and must not block ordinary read-only composites.
    """
    if not _render_subject(tokens):
        return False
    gate = _gate_ok(ctx.cwd)
    control_seen = False
    matched = False

    def check_block(block):
        if _tokens_state_relevant(block, ctx):
            return True
        return (not gate) and _tokens_relevant(block)

    for i, tok in enumerate(tokens):
        if tok.kind != "word" or not _cmd_start(tokens, i):
            continue
        # 命令位置的 quoted/escaped 词仍可能是函数调用；函数名检查不看 quoted。
        if tok.value in ctx.functions and ctx.functions[tok.value]:
            return True
        if tok.quoted:
            continue
        if tok.value == "if":
            then_i, _else_i, fi_i = _if_parts(tokens, i)
            if then_i is not None and fi_i is not None:
                control_seen = matched = True
                if check_block(tokens[i:fi_i + 1]):
                    return True
        elif tok.value in ("while", "until", "for"):
            do_i, done_i = _loop_parts(tokens, i)
            if do_i is not None and done_i is not None:
                control_seen = matched = True
                if check_block(tokens[i:done_i + 1]):
                    return True
        elif tok.value == "case":
            esac_i = _case_parts(tokens, i)
            if esac_i is not None:
                control_seen = matched = True
                if check_block(tokens[i:esac_i + 1]):
                    return True
        elif tok.value == "function":
            control_seen = True
    if control_seen and not matched:
        return _tokens_state_relevant(tokens, ctx) or (
            (not gate) and _tokens_relevant(tokens))
    return False


def _ctx_changed(a: Ctx, b: Ctx) -> bool:
    return (a.cwd != b.cwd or a.prev != b.prev or a.vars != b.vars
            or a.env != b.env or a.exported != b.exported)


def parse_tokens(tokens, ctx: Ctx, inherited_skip: bool = False, depth: int = 0):
    if depth > 10:
        return [Finding(ctx.cwd, unresolved=True, reason="嵌套过深")]
    tokens = _strip_control(tokens, ctx)
    if _control_risk(tokens, ctx):
        if inherited_skip:
            return []
        return [Finding(ctx.cwd, unresolved=True,
                        reason="未可靠求值的控制流可能改变渲染上下文；按保守策略阻断")]

    findings = []
    cmd = []
    seg_snap = None
    pipe_base = None
    unit_snap = None
    mode = "definite"          # definite | conditional | skipped
    mode_status = None         # result of a skipped &&/|| chain
    i = 0

    def snapshot():
        return (ctx.cwd, ctx.prev, dict(ctx.vars), dict(ctx.env), set(ctx.exported))

    def restore(snap):
        if snap is None:
            return
        ctx.cwd, ctx.prev = snap[0], snap[1]
        ctx.vars, ctx.env, ctx.exported = dict(snap[2]), dict(snap[3]), set(snap[4])

    def run_group(inner, target, branch_mode):
        before = (target.cwd, target.prev, dict(target.vars),
                  dict(target.env), set(target.exported))
        result = parse_tokens(inner, target, inherited_skip, depth + 1)
        if branch_mode == "conditional":
            for finding in result:
                if not finding.skip:
                    finding.unresolved = True
                    finding.reason = "条件分支的执行上下文无法可靠确定；按保守策略阻断"
            after = (target.cwd, target.prev, dict(target.vars),
                     dict(target.env), set(target.exported))
            if after != before:
                ctx.tainted = True
        findings.extend(result)

    def flush():
        nonlocal cmd, mode_status
        if not cmd:
            return
        if mode == "definite":
            findings.extend(parse_simple(cmd, ctx, inherited_skip, depth))
        elif mode == "conditional":
            child = ctx.copy()
            before = (child.cwd, child.prev, dict(child.vars),
                      dict(child.env), set(child.exported))
            result = parse_simple(cmd, child, inherited_skip, depth)
            for finding in result:
                if not finding.skip:
                    finding.unresolved = True
                    finding.reason = "条件命令的执行上下文无法可靠确定；按保守策略阻断"
            findings.extend(result)
            after = (child.cwd, child.prev, dict(child.vars),
                     dict(child.env), set(child.exported))
            if after != before:
                ctx.tainted = True
            ctx.last_status = None
        else:  # skipped: the command does not execute at all; ignore its findings
            ctx.last_status = mode_status
        cmd = []

    while i < len(tokens):
        tok = tokens[i]
        if tok.kind == "word":
            if not cmd and tok.value in KEYWORDS:
                i += 1
                continue
            if not cmd:
                seg_snap = snapshot()
                if unit_snap is None:
                    unit_snap = seg_snap
            cmd.append(tok)
            i += 1
            continue
        if tok.kind == "redirect":
            if not cmd:
                seg_snap = snapshot()
                if unit_snap is None:
                    unit_snap = seg_snap
            i += 1
            if i < len(tokens) and tokens[i].kind == "word" \
                    and not re.search(r">&\\d+$", tok.value):
                i += 1
            continue
        op = tok.value
        if op in (";", "&&", "||"):
            prev_mode = mode
            flush()
            if pipe_base is not None:
                restore(pipe_base)
                pipe_base = None
            prev_status = ctx.last_status
            if op == ";":
                mode = "definite"
                mode_status = None
                ctx.last_status = None
                unit_snap = None
            elif prev_mode != "definite":
                # 已进入条件/跳过链后继续串联，最终状态不再可靠。
                ctx.tainted = True
                mode = "conditional"
                mode_status = None
            else:
                if op == "&&":
                    mode = ("definite" if prev_status is True else
                            "skipped" if prev_status is False else "conditional")
                    mode_status = False if prev_status is False else None
                else:
                    mode = ("definite" if prev_status is False else
                            "skipped" if prev_status is True else "conditional")
                    mode_status = True if prev_status is True else None
            i += 1
            continue
        if op == "|":
            flush()
            if pipe_base is None:
                pipe_base = unit_snap if unit_snap is not None else snapshot()
            restore(pipe_base)
            seg_snap = None
            mode = "definite"
            mode_status = None
            ctx.last_status = None
            i += 1
            continue
        if op == "&":
            flush()
            # 后台列表在子 shell 中执行；不能把其中的 cd/export 带回父 shell。
            restore(unit_snap)
            seg_snap = None
            pipe_base = None
            unit_snap = None
            mode = "definite"
            mode_status = None
            ctx.last_status = None
            i += 1
            continue
        if op in ("(", "$("):
            dynamic = op == "$(" and (
                not cmd
                or all(_is_assign(t.value) for t in cmd)
                or (cmd and cmd[0].value in {"eval", "command", "exec", "nohup",
                                              "sudo", "env", "timeout", "nice",
                                              "stdbuf", "builtin"})
            )
            j, inner = _extract_group(tokens, i + 1, ")")
            if dynamic and mode != "skipped" \
                    and (_tokens_renderish(inner) or _tokens_renderish(tokens[j + 1:])):
                # 赋值值、命令位置或 eval/包装器参数中的命令替换无法静态确定；
                # 若它可能变成渲染命令，失败关闭而不是猜测展开结果。
                findings.append(Finding(
                    ctx.cwd, skip=inherited_skip, unresolved=True,
                    reason="命令替换可能改变实际执行目标；保守阻断"))
            flush()
            if unit_snap is None:
                unit_snap = snapshot()
            seg_snap = None
            child = ctx.copy()
            run_group(inner, child, mode)
            i = j + 1
            continue
        if op == "{":
            flush()
            if unit_snap is None:
                unit_snap = snapshot()
            seg_snap = None
            j, inner = _extract_group(tokens, i + 1, "}")
            if mode == "definite":
                run_group(inner, ctx, "definite")
            else:
                child = ctx.copy()
                run_group(inner, child, mode)
            i = j + 1
            continue
        if op in (")", "}"):
            flush()
            i += 1
            continue
        i += 1
    flush()
    return findings


def _long_message(directory, duration):
    return (f"该合成时长 {duration:g}s（≥{MIN_LONG:g}s 长片），但项目内未找到 {GATE}。\n"
            "huashu-design 铁律：长片渲染前必须完成「三方向真实视觉给用户选择」"
            "（或用户明示豁免），并把选择/豁免记录写入项目目录的 "
            f"{GATE}（含：展示了哪几版、截图路径、用户的选择原话）。\n"
            "补齐后重渲；用户当面明说跳过时，在该渲染命令前加 "
            "SKIP_DESIGN_GATE=1 显式放行。")


def main() -> int:
    raw_input = sys.stdin.read()
    try:
        data = json.loads(raw_input)
    except Exception as exc:
        fail(f"无法解析输入 JSON（{exc}）；按失败关闭。")
        return 2
    if not isinstance(data, dict):
        fail("输入 JSON 顶层不是对象；按失败关闭。")
        return 2
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command", "")
    cwd = data.get("cwd", "")
    if not isinstance(command, str):
        command = str(command or "")
    if not command.strip():
        return 0
    cwd_missing = not isinstance(cwd, str) or not cwd.strip()
    if cwd_missing:
        # 不把 Hook 进程 cwd 当成项目 cwd；只有命令自身 cd/prefix 到绝对路径时才有可信目标。
        base = None
    else:
        base = cwd if os.path.isabs(cwd) else os.path.abspath(cwd)

    cleaned = strip_heredocs(command)
    tokens = tokenize(cleaned)
    ctx = Ctx(base, None, {}, {}, set())
    findings = parse_tokens(tokens, ctx, False, 0)
    if not findings:
        return 0

    for finding in findings:
        if finding.skip:
            continue
        if finding.unresolved:
            fail(f"无法可靠判定该渲染命令（{finding.reason}）；按保守策略阻断。")
        # 优先级：首个显式 --duration（JS 入口不读 HTML）> 30s 源码默认；
        # 未知 npm/hyperframes 才用项目 data-duration；都无时只有确认 Gate 才放行。
        duration = finding.duration
        if duration is None and finding.html_allowed \
                and finding.cwd and os.path.isdir(finding.cwd):
            duration = _html_duration(finding.cwd)
        if duration is None:
            duration = finding.default
        if duration is None:
            # 时长不可判定时不能静默放行；只有能确认 Gate 已存在才允许。
            if finding.cwd and os.path.isdir(finding.cwd) and _gate_ok(finding.cwd):
                continue
            fail("无法可靠判定渲染时长，且无法确认 Gate；按保守策略阻断。")
        if duration < MIN_LONG:
            continue
        if not finding.cwd or not os.path.isdir(finding.cwd):
            fail("长片渲染但 cwd 缺失/无效，无法核对 "
                 f"{GATE}；按保守策略阻断。")
        if _gate_ok(finding.cwd):
            continue
        fail(_long_message(finding.cwd, duration))
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
)"
