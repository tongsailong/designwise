#!/usr/bin/env python3
"""check-motion.py — HTML 原型动效的静态事实采集（不判断动效好不好看）

只回答可机械核对的问题：有没有 motion token、有没有减少动态、时长是否超预算、
是否动画布局属性、是否存在无限循环。它不能证明转场方向正确、不能证明可中断、
不能替代录屏与设计评审。

覆盖范围：`<style>` 块、元素 `style="..."`、React/JS 字面量里的
`transition:'...'` / `animation:'...'` / `transitionProperty`；同目录相对路径的
`<link rel="stylesheet">` 与 `<script src>` 会一并读入扫描。解析 CSS 变量时长、
逗号分隔的多段 transition、`@keyframes` 体内的布局属性。远程或缺失的本地外链
不会被静默放过：缺失报错，远程只提示（静态扫描无法读取）。

用法：
    python3 scripts/check-motion.py prototype/index.html
    python3 scripts/check-motion.py prototype/index.html --json
    python3 scripts/check-motion.py prototype/index.html --strict   # warning 也判失败

退出码：0 无阻断项；1 有阻断项（缺少减少动态 / 超过 1200ms）；2 用法或文件错误。
`--strict` 把 warning 也判失败；加载指示（skeleton/shimmer/loading）的循环与较长时长
记为 info，不参与 strict 阻断。

证据边界：静态扫描不执行页面，不做语义判断；结论以真实录屏/连续帧与
`references/motion-design.md` §9 为准。
"""

import argparse
import json
import os
import re
import sys

TIME_RE = re.compile(r"(-?\d*\.?\d+)(ms|s)\b", re.I)
REDUCE_RE = re.compile(r"prefers-reduced-motion\s*:\s*reduce", re.I)
TOKEN_RE = re.compile(r"--motion-(?:duration|easing|spring)[\w-]*\s*:")
VAR_DEF_RE = re.compile(r"(--motion-duration-[\w-]+)\s*:\s*([^;}]+)")
VAR_USE_RE = re.compile(r"var\(\s*(--motion-duration-[\w-]+)\s*(?:,[^)]*)?\)")
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.I | re.S)
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
INLINE_STYLE_RE = re.compile(r"""style\s*=\s*(["'])(.*?)\1""", re.I | re.S)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.I | re.S)
SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>", re.I | re.S)
HREF_RE = re.compile(r"""href\s*=\s*(["'])(.*?)\1""", re.I | re.S)
SRC_RE = re.compile(r"""src\s*=\s*(["'])(.*?)\1""", re.I | re.S)
CSS_IMPORT_RE = re.compile(
    r"""@import\s+(?:url\(\s*)?(["'])(.*?)\1""", re.I | re.S)
JS_STYLE_RE = re.compile(
    r"""(transition|animation|transitionProperty|animationName)\s*:\s*(["'`])(.*?)\2""",
    re.I | re.S,
)
LAYOUT_PROPS = {
    "width", "height", "top", "left", "right", "bottom",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "filter", "box-shadow",
}
MOTION_PROPS = {"transition", "transition-duration", "transition-property",
                "animation", "animation-duration", "animation-name",
                "animation-iteration-count"}
UI_LIMIT_MS = 400
HARD_LIMIT_MS = 1200  # 与 motion-design.md 的 ambient/加载上限一致
LOADING_HINTS = ("skeleton", "shimmer", "loading", "spinner")


def parse_keyframes(styles):
    """按花括号配平解析 @keyframes；非贪婪正则会截断到第一个 `}`。"""
    out = {}
    for match in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", styles, re.I):
        name = match.group(1)
        index = match.end()
        depth = 1
        while index < len(styles) and depth:
            if styles[index] == "{":
                depth += 1
            elif styles[index] == "}":
                depth -= 1
            index += 1
        out[name.lower()] = styles[match.end():index - 1]
    return out


def ms_values(text):
    out = []
    for value, unit in TIME_RE.findall(text):
        try:
            num = float(value)
        except ValueError:
            continue
        out.append(int(round(num * 1000)) if unit.lower() == "s" else int(round(num)))
    return out


def duration_values(prop, value):
    """只取时长，不把 shorthand 里的 delay 当 duration。

    CSS 简写中每个逗号分段里的**第一个**时间值是 duration，第二个是 delay
    （如 `transition: transform 300ms ease 2s`）。把 delay 算进时长预算会误报超长。
    """
    if prop in ("transition-duration", "animation-duration"):
        return ms_values(value)
    if prop in ("transition", "animation"):
        out = []
        for segment in value.split(","):
            times = ms_values(segment)
            if times:
                out.append(times[0])
        return out
    return []


def split_decls(body):
    result = []
    for part in re.split(r"[;\n]", body):
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        result.append((prop.strip().lower(), value.strip()))
    return result


def resolve_vars(value, vars_map):
    def repl(match):
        return vars_map.get(match.group(1), match.group(0))
    return VAR_USE_RE.sub(repl, value)


def is_loading(selector, value, keyframes=""):
    hay = " ".join((selector, value, keyframes)).lower()
    return any(hint in hay for hint in LOADING_HINTS)


def layout_properties(value):
    """Return layout props used as transition/animation properties in a value."""
    found = []
    for segment in value.split(","):
        tokens = re.split(r"\s+", segment.strip())
        if not tokens:
            continue
        # first token of each segment is the property (transition shorthand / animation name)
        prop = tokens[0].strip().lower()
        if prop in LAYOUT_PROPS:
            found.append(prop)
    return sorted(set(found))


def scan_rule(selector, declarations, file_label, vars_map, keyframes):
    rows = []
    for prop, value in declarations:
        if prop not in MOTION_PROPS:
            continue
        resolved = resolve_vars(value, vars_map)
        durations = duration_values(prop, resolved)
        infinite = bool(re.search(r"\binfinite\b", resolved, re.I))
        layout = layout_properties(resolved)
        first_tokens = resolved.split(",")[0].strip().split()
        all_property = bool(first_tokens) and first_tokens[0].lower() == "all"
        if prop in ("animation", "animation-name"):
            name = resolved.split(",")[0].strip().split()[0] if resolved.strip() else ""
            body = keyframes.get(name.lower(), "")
            for p in re.findall(r"([a-z-]+)\s*:", body, re.I):
                p = p.lower()
                if p in LAYOUT_PROPS and p not in layout:
                    layout.append(p)
        rows.append({
            "file": file_label,
            "selector": " ".join(selector.split()),
            "property": prop,
            "raw": " ".join(resolved.split()),
            "durations_ms": durations,
            "infinite": infinite,
            "layout_properties": sorted(set(layout)),
            "all_property": all_property,
            "loading": is_loading(selector, resolved,
                                  keyframes.get(resolved.split(",")[0].strip().split()[0].lower(), "")
                                  if resolved.strip() else ""),
        })
    return rows


def collect_local_sources(path, text):
    """Return (css_text, js_text, local_files, missing, remote).

    原型要求 file:// 可跑；同目录相对外链很常见，静态扫描必须跟进去，否则
    “动效写在外部 CSS/JS 里”会得到假的通过。远程 URL 无法离线读取，只提示。
    """
    base = os.path.dirname(os.path.abspath(path))
    css_parts, js_parts, local_files = [], [], []
    missing, remote = [], []
    seen = set()

    def load(ref):
        ref = (ref or "").strip()
        if not ref:
            return None
        low = ref.lower()
        if low.startswith(("http://", "https://", "//", "data:", "javascript:")):
            remote.append(ref)
            return None
        if ref.startswith("#"):
            return None
        target = os.path.normpath(os.path.join(base, ref.split("#", 1)[0].split("?", 1)[0]))
        if target in seen:
            return None
        seen.add(target)
        if not os.path.isfile(target):
            missing.append(ref)
            return None
        try:
            with open(target, encoding="utf-8") as fh:
                body = fh.read()
        except (OSError, UnicodeDecodeError):
            missing.append(ref)
            return None
        local_files.append(os.path.relpath(target, base))
        return body

    for tag in LINK_TAG_RE.findall(text):
        if not re.search(r"""rel\s*=\s*["']?[^"'>]*stylesheet""", tag, re.I):
            continue
        href = HREF_RE.search(tag)
        body = load(href.group(2) if href else "")
        if body is not None:
            css_parts.append(body)
    for tag in SCRIPT_TAG_RE.findall(text):
        src = SRC_RE.search(tag)
        body = load(src.group(2) if src else "")
        if body is not None:
            js_parts.append(body)
    # @import 只跟一层：原型里嵌套很深的 CSS 依赖本身就不该出现。
    for _, ref in CSS_IMPORT_RE.findall("\n".join(css_parts)):
        body = load(ref)
        if body is not None:
            css_parts.append(body)
    return ("\n".join(css_parts), "\n".join(js_parts), local_files, missing, remote)


def scan_file(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    label = os.path.basename(path)
    ext_css, ext_js, local_files, missing, remote = collect_local_sources(path, text)
    styles = " ".join(STYLE_BLOCK_RE.findall(text))
    if ext_css:
        styles += "\n" + ext_css
    scan_text = text + "\n" + ext_js
    vars_map = {}
    for name, value in VAR_DEF_RE.findall(styles):
        vars_map[name] = value.strip()
    keyframes = parse_keyframes(styles)
    rules = []
    for selector, body in RULE_RE.findall(styles):
        selector = selector.strip()
        if not selector or selector.startswith("@"):
            continue
        rules.extend(scan_rule(selector, split_decls(body), label, vars_map, keyframes))
    # inline style="..." attributes
    for _, body in INLINE_STYLE_RE.findall(scan_text):
        rules.extend(scan_rule("inline-style", split_decls(body), label, vars_map, keyframes))
    # JS object literals: transition:'...' / animation:'...'
    for prop, _, value in JS_STYLE_RE.findall(scan_text):
        prop = "transition" if prop.lower() == "transitionproperty" else (
            "animation" if prop.lower() == "animationname" else prop.lower())
        rules.extend(scan_rule("inline-js", [(prop, value)], label, vars_map, keyframes))
    return {
        "file": path,
        "has_reduce": bool(REDUCE_RE.search(styles)),
        "tokens": sorted(set(TOKEN_RE.findall(styles))),
        "keyframes": sorted(keyframes),
        "vars": vars_map,
        "rules": rules,
        "external_files": local_files,
        "external_missing": missing,
        "external_remote": remote,
    }


def evaluate(results, strict):
    findings = []

    def add(level, code, message, file="", selector=""):
        findings.append({"level": level, "code": code, "message": message,
                         "file": file, "selector": selector})

    if not results:
        add("error", "motion_no_input", "没有可扫描的 HTML 文件")
    for scan in results:
        name = scan["file"]
        for ref in scan.get("external_missing", []):
            add("error", "motion_external_missing",
                "原型引用的本地 CSS/JS 不存在，动效不可能按预期运行：%s" % ref, name)
        for ref in scan.get("external_remote", []):
            add("warning", "motion_external_remote",
                "原型引用远程 CSS/JS，静态扫描读不到其中的动效：%s" % ref, name)
        if not scan["rules"]:
            add("warning", "motion_none",
                "未检测到 transition/animation；若该页面本应有动效，说明尚未实现", name)
            continue
        if not scan["has_reduce"]:
            add("error", "motion_no_reduce",
                "存在动效但没有 prefers-reduced-motion 降级（无障碍硬要求）", name)
        if not scan["tokens"]:
            add("warning", "motion_no_tokens",
                "有动效但未使用 motion token（--motion-duration/easing）", name)
        for rule in scan["rules"]:
            sel = rule["selector"]
            loading = rule["loading"]
            for duration in rule["durations_ms"]:
                if duration > HARD_LIMIT_MS:
                    add("error", "motion_too_long",
                        "动效时长 %dms 超过硬上限 %dms" % (duration, HARD_LIMIT_MS), name, sel)
                elif duration > UI_LIMIT_MS:
                    if loading:
                        add("info", "motion_loading_long",
                            "加载指示时长 %dms；允许，但需确认真实进度且减少动态下可用"
                            % duration, name, sel)
                    else:
                        add("warning", "motion_long",
                            "动效时长 %dms 超过 UI 转场预算 %dms；叙事/氛围需写理由"
                            % (duration, UI_LIMIT_MS), name, sel)
            if rule["infinite"]:
                if loading:
                    add("info", "motion_loading_loop",
                        "加载指示循环；允许，但减少动态下必须降级", name, sel)
                else:
                    add("warning", "motion_infinite",
                        "存在无限循环动画；必须有暂停/降级且不得抢注意力", name, sel)
            for prop in rule["layout_properties"]:
                add("warning", "motion_layout_property",
                    "动画布局属性 %s 易掉帧；优先 transform/opacity" % prop, name, sel)
            if rule.get("all_property"):
                add("warning", "motion_all_property",
                    "transition/animation 使用 all，可能连带布局属性；应逐项列出", name, sel)

    if strict:
        for finding in findings:
            if finding["level"] == "warning":
                finding["level"] = "error"
    errors = [f for f in findings if f["level"] == "error"]
    return findings, errors


def main(argv):
    ap = argparse.ArgumentParser(description="HTML 原型动效静态事实采集")
    ap.add_argument("files", nargs="+", help="prototype HTML 文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="warning 也判失败")
    args = ap.parse_args(argv)

    missing = [p for p in args.files if not os.path.isfile(p)]
    if missing:
        for p in missing:
            print("check-motion: 找不到文件：%s" % p, file=sys.stderr)
        return 2
    try:
        results = [scan_file(p) for p in args.files]
    except (OSError, UnicodeDecodeError) as exc:
        print("check-motion: 读取失败：%s" % exc, file=sys.stderr)
        return 2

    findings, errors = evaluate(results, args.strict)
    summary = {
        "files": len(results),
        "motion_rules": sum(len(r["rules"]) for r in results),
        "keyframes": sum(len(r["keyframes"]) for r in results),
        "has_reduced_motion": any(r["has_reduce"] for r in results),
        "has_motion": any(r["rules"] for r in results),
        "errors": len(errors),
        "warnings": sum(1 for f in findings if f["level"] == "warning"),
        "infos": sum(1 for f in findings if f["level"] == "info"),
        "external_files": sum(len(r.get("external_files", [])) for r in results),
        "findings": findings,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("check-motion: %d 个文件，%d 条动效规则，%d 个 keyframes，减少动态=%s"
              % (summary["files"], summary["motion_rules"], summary["keyframes"],
                 "是" if summary["has_reduced_motion"] else "否"))
        for finding in findings:
            where = finding["file"]
            if finding["selector"]:
                where += " :: " + finding["selector"]
            print("  [%s] %s %s — %s" % (finding["level"], finding["code"], where,
                                        finding["message"]))
        print("结论：%s（静态扫描只给事实，动效是否成立以录屏与设计评审为准）"
              % ("有阻断项" if errors else "无阻断项"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main(sys.argv[1:]))
