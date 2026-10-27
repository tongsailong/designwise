#!/usr/bin/env python3
"""check-skill.py — 本 skill 的自检脚本（结构 + 引用完整性）

为什么要有它：本 skill 不是单文件——`references/` `assets/` `scripts/` `demos/`
四个子目录里有上百处被文档引用的配方、脚本与素材，缺一个就有一条路径走不通。
README「装上就能用」一节已经警告过：只同步 SKILL.md 的旧版 skills CLI 会装出
一个残缺的 skill。这个脚本把「装完是不是完整的」变成一条命令可判定的事实，
改完文档/挪完文件后跑一次，避免把悬空引用交付出去。

用法：
    python3 scripts/check-skill.py            # 结构与引用检查
    python3 scripts/check-skill.py --strict   # 额外检查孤儿文件（未被任何文档引用）
    python3 scripts/check-skill.py --root /path/to/skill   # 指定 skill 根目录

退出码：0 = 通过（无 error）；1 = 有 error（缺文件 / 悬空引用）。
warning 不影响退出码（如 demos 下按 .gitignore 由 Releases 分发的大视频）。
"""

import argparse
import os
import re
import subprocess
import sys

# ── 结构清单：这些文件/目录必须存在，否则 skill 装不完整 ────────────────────
REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "README.en.md",
    "LICENSE",
    "SECURITY.md",
    "package.json",
    "test-prompts.json",
    # GPT-first 通路的核心载体：缺了「概念图→实现」的转译就断链，故列为必需
    "references/gpt-visual-workflow.md",
    "references/design-handoff.md",
]

REQUIRED_DIRS = ["references", "assets", "scripts", "demos"]

# 被 SKILL.md / references 反复引用的关键资产与脚本——缺了会静默降级成坏经验
REQUIRED_ASSETS = [
    "assets/animations.jsx",
    "assets/ios_frame.jsx",
    "assets/android_frame.jsx",
    "assets/macos_window.jsx",
    "assets/browser_window.jsx",
    "assets/design_canvas.jsx",
    "assets/cursor.jsx",
    "assets/narration_stage.jsx",
    "assets/deck_index.html",
    "assets/deck_stage.js",
    "assets/showcases/INDEX.md",
]

REQUIRED_SCRIPTS = [
    "scripts/render-video.js",
    "scripts/render-video-seek.js",
    "scripts/convert-formats.sh",
    "scripts/add-music.sh",
    "scripts/export_deck_pdf.mjs",
    "scripts/export_deck_pptx.mjs",
    "scripts/export_deck_stage_pdf.mjs",
    "scripts/html2pptx.js",
    "scripts/pptx_from_rendered.py",
    "scripts/gen_deck_thumbs.mjs",
    "scripts/verify.py",
    "scripts/check-contrast.py",
    "scripts/check-assets.py",
    "scripts/fetch_images.py",
    "scripts/narrate-pipeline.mjs",
    "scripts/render-narration.sh",
    "scripts/design-gate-hook.sh",
]

# ── 引用扫描 ──────────────────────────────────────────────────────────────
# 只扫描面向 agent / 用户的文档；脚本内部的互相引用是另一回事，不在此范围。
SCAN_DOCS = [
    "SKILL.md",
    "README.md",
    "README.en.md",
    "SECURITY.md",
    "assets/showcases/INDEX.md",
]
SCAN_GLOB_DIRS = ["references"]  # 该目录下所有 *.md 一并扫描

SUBDIRS = ("references", "assets", "scripts", "demos")
PATH_RE = re.compile(
    r"(?<![\w./-])(" + "|".join(SUBDIRS) + r")/[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9]{2,5}"
)


def is_placeholder(path: str) -> bool:
    """排除占位符与示意路径，如 `references/xxx.md`、`scripts/xxx.sh`。"""
    low = path.lower()
    return "xxx" in low or "your-" in low or "example" in low


def find_docs(root: str):
    docs = []
    for rel in SCAN_DOCS:
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            docs.append(p)
    for d in SCAN_GLOB_DIRS:
        full = os.path.join(root, d)
        if os.path.isdir(full):
            for name in sorted(os.listdir(full)):
                if name.endswith(".md"):
                    docs.append(os.path.join(full, name))
    return docs


def git_ignored(root: str, rel: str):
    """返回 True/False；不在 git 仓库或没有 git 时返回 None（未知）。"""
    try:
        r = subprocess.run(
            ["git", "-C", root, "check-ignore", "-q", "--", rel],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # 0=ignored, 1=not ignored；其余（128=不是 git 仓库等）无法判定。
        if r.returncode not in (0, 1):
            return None
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None


def check_structure(root: str):
    errors, warnings = [], []

    for rel in REQUIRED_FILES + REQUIRED_ASSETS + REQUIRED_SCRIPTS:
        if not os.path.isfile(os.path.join(root, rel)):
            errors.append(f"缺少必需文件：{rel}")

    for rel in REQUIRED_DIRS:
        if not os.path.isdir(os.path.join(root, rel)):
            errors.append(f"缺少必需目录：{rel}/")

    # SKILL.md frontmatter：name + description 是 agent 触发 skill 的依据
    skill_md = os.path.join(root, "SKILL.md")
    if os.path.isfile(skill_md):
        with open(skill_md, encoding="utf-8") as f:
            text = f.read()
        if not text.startswith("---\n"):
            errors.append("SKILL.md 缺少 YAML frontmatter（首行应为 ---）")
        else:
            end = text.find("\n---", 4)
            if end == -1:
                errors.append("SKILL.md frontmatter 未闭合（缺少收尾的 ---）")
            else:
                fm = text[4:end]
                for key in ("name:", "description:"):
                    if key not in fm:
                        errors.append(f"SKILL.md frontmatter 缺少 {key} 字段")
                size = len(text.encode("utf-8"))
                if size > 100_000:
                    errors.append(
                        f"SKILL.md 超过 ZCode 100,000 字节读取上限（当前 {size} 字节）")
                elif size > 98_000:
                    warnings.append(
                        f"SKILL.md 已接近 100,000 字节上限（当前 {size} 字节），新增内容请移到 references/")
                m = re.search(r"^description:\s*(.*)$", fm, re.M)
                if m and len(m.group(1)) > 1024:
                    errors.append(
                        f"SKILL.md description 超过 1024 字符（当前 {len(m.group(1))}）")

    return errors, warnings


def check_references(root: str):
    errors, warnings = [], []
    referenced = set()

    for doc in find_docs(root):
        rel_doc = os.path.relpath(doc, root).replace(os.sep, "/")
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        for match in PATH_RE.finditer(text):
            ref = match.group(0).rstrip(".,;:)）」。、")
            if is_placeholder(ref):
                continue
            referenced.add(ref)
            if os.path.exists(os.path.join(root, ref)):
                continue
            ignored = git_ignored(root, ref)
            if ignored is True:
                warnings.append(f"{rel_doc} → {ref}（仓库内不存在，按 .gitignore 由 Releases 分发，属预期）")
            elif ignored is None:
                warnings.append(f"{rel_doc} → {ref}（不存在；无法判定是否 gitignore，请人工确认）")
            else:
                errors.append(f"{rel_doc} → 引用了不存在的文件：{ref}")

    return errors, warnings, referenced


def check_orphans(root: str, referenced: set):
    """--strict：references/*.md 里没有被任何扫描文档引用到的文件。"""
    warnings = []
    ref_dir = os.path.join(root, "references")
    if os.path.isdir(ref_dir):
        for name in sorted(os.listdir(ref_dir)):
            if not name.endswith(".md"):
                continue
            rel = f"references/{name}"
            if rel not in referenced:
                warnings.append(f"{rel} 未被任何文档引用（可能是孤岛文档）")
    return warnings


def main():
    ap = argparse.ArgumentParser(description="designwise 自检：结构与引用完整性")
    ap.add_argument("--root", default=None, help="skill 根目录（默认：本脚本所在目录的上一级）")
    ap.add_argument("--strict", action="store_true", help="额外检查孤儿文档")
    args = ap.parse_args()

    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(root)

    print(f"自检根目录：{root}\n")

    struct_errors, struct_warnings = check_structure(root)
    ref_errors, ref_warnings, referenced = check_references(root)
    errors = struct_errors + ref_errors

    warnings = list(struct_warnings) + list(ref_warnings)
    if args.strict:
        warnings += check_orphans(root, referenced)

    print(f"扫描文档：{len(find_docs(root))} 个 · 检出被引用路径：{len(referenced)} 个\n")

    if errors:
        print(f"❌ 错误（{len(errors)}）")
        for e in errors:
            print(f"  - {e}")
    else:
        print("✅ 结构完整、无悬空引用")

    if warnings:
        print(f"\n⚠️  提示（{len(warnings)}）")
        for w in warnings:
            print(f"  - {w}")

    print()
    if errors:
        print(f"结论：未通过（{len(errors)} 个错误需修复）")
        return 1
    print("结论：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
