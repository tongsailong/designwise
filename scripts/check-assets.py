#!/usr/bin/env python3
"""check-assets.py — 正式素材清单校验（可追踪 / 可复现 / 可引用）

为什么要有它：`gpt-visual-workflow.md` §4.6/§4.7.2 要求每张正式素材都进可追踪清单
（`handoff/assets.md`）+ 一图一档 prompt 档案（`assets/img-prompts/<名>.md`）。但「清单
写了没」骗得过眼睛、骗不过文件系统——图片没进清单、prompt 丢了、路径写错，都会在实现端
才爆。这个脚本把「素材是否可追踪」变成一条命令可判定的结论。

设计原则（复用而非新造）：纯标准库、无依赖；与 `check-skill.py`/`check-contrast.py` 同风格；
退出码判定，可进交付前自检。

检查三项（对应 §4.6/§4.7 的三条要求）：
  1. **可引用**：`handoff/assets.md` 里写的每个素材路径都真实存在
  2. **可追踪**：`assets/images/` 下每个位图都在 `handoff/assets.md` 里被引用（无未登记素材）
  3. **可复现**：每个位图素材都有对应的 `assets/img-prompts/<名>.md`（一图一档）

用法：
    python3 scripts/check-assets.py <项目目录>          # 项目目录含 handoff/ 与 assets/
    python3 scripts/check-assets.py <项目目录> --md      # 顺便打印素材清单汇总

退出码：0 = 通过；1 = 有未通过项；2 = 输入/结构错误（如缺 handoff/assets.md）。
"""

import argparse
import os
import re
import sys

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
# 匹配 markdown 表格/正文里出现的素材路径（含 assets/ 的相对路径）
PATH_RE = re.compile(r"assets/images/[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:png|jpe?g|webp|gif|avif)", re.I)


def list_images(images_dir: str):
    """Return bitmap paths relative to images_dir, recursively."""
    if not os.path.isdir(images_dir):
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(images_dir):
        dirnames.sort()
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() in IMAGE_EXT:
                rel = os.path.relpath(os.path.join(dirpath, name), images_dir)
                found.append(rel.replace(os.sep, "/"))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="正式素材清单校验（可追踪/可复现/可引用）")
    ap.add_argument("project", help="项目目录（应含 handoff/assets.md 与 assets/images/）")
    ap.add_argument("--md", action="store_true", help="打印素材清单汇总")
    args = ap.parse_args()

    root = os.path.abspath(args.project)

    # 定位 assets.md：优先 <root>/handoff/assets.md，兼容交付包直接放在 root（如演练目录）
    candidates = [
        os.path.join(root, "handoff", "assets.md"),
        os.path.join(root, "assets.md"),
    ]
    assets_md = next((c for c in candidates if os.path.isfile(c)), None)
    if assets_md is None:
        print(f"❌ 找不到 assets.md（试过：{' / '.join(candidates)}）")
        print("   交付包⑤ 规范见 references/design-handoff.md §2⑤")
        return 2

    # 素材目录：与 assets.md 同级优先，其次 <root>/assets/
    base = os.path.dirname(assets_md)
    images_dir = next(
        (d for d in (os.path.join(base, "assets", "images"),
                     os.path.join(root, "assets", "images")) if os.path.isdir(d)),
        os.path.join(base, "assets", "images"),
    )
    prompts_dir = os.path.join(os.path.dirname(images_dir), "img-prompts")

    if not os.path.isfile(assets_md):
        print(f"❌ 缺 assets.md，无法校验素材清单：{assets_md}")
        return 2

    text = open(assets_md, encoding="utf-8", errors="ignore").read()
    referenced = sorted({m.group(0) for m in PATH_RE.finditer(text)})
    on_disk = list_images(images_dir)

    print(f"素材清单校验 · {root}")
    print(f"  handoff/assets.md 引用位图：{len(referenced)} 张；assets/images/ 实有：{len(on_disk)} 张\n")

    fail = []

    # ① 可引用：清单里的路径都存在，且不得越出项目目录
    root_real = os.path.realpath(root)
    for rel in referenced:
        target = os.path.realpath(os.path.join(root, rel))
        try:
            inside = os.path.commonpath([root_real, target]) == root_real
        except ValueError:
            inside = False
        if not inside:
            fail.append(("可引用", f"清单引用了项目外路径：{rel}"))
        elif not os.path.isfile(target):
            fail.append(("可引用", f"清单引用了不存在的文件：{rel}"))

    # ② 可追踪：磁盘上的位图都被清单登记（用相对路径，避免同名文件互相遮蔽）
    ref_paths = set(referenced)
    unregistered = [f for f in on_disk if f"assets/images/{f}" not in ref_paths]
    for f in unregistered:
        fail.append(("可追踪", f"assets/images/{f} 未登记进 handoff/assets.md"))

    # ③ 可复现：每个位图有一图一档的 prompt。
    # prompt 目录整个缺失时不能「跳过检查」——有位图就说明每一张都缺档案。
    has_prompts = os.path.isdir(prompts_dir)
    missing_prompt = []
    for f in on_disk:
        prompt_rel = os.path.splitext(f)[0] + ".md"
        if not has_prompts or not os.path.isfile(os.path.join(prompts_dir, prompt_rel)):
            missing_prompt.append(prompt_rel)
    for rel in missing_prompt:
        fail.append(("可复现", f"assets/img-prompts/{rel} 缺失（一图一档）"))

    if args.md:
        print("| 素材文件 | 已登记清单 | 有 prompt 档案 |")
        print("|---|---|---|")
        for f in on_disk:
            prompt_rel = os.path.splitext(f)[0] + ".md"
            reg = "✅" if f"assets/images/{f}" in ref_paths else "❌"
            pr = "✅" if has_prompts and os.path.isfile(
                os.path.join(prompts_dir, prompt_rel)) else "❌"
            print(f"| assets/images/{f} | {reg} | {pr} |")
        print()

    if not on_disk:
        print("ℹ️  assets/images/ 为空——本项目无位图正式素材（图标/图形走 SVG/CSS 属正常，§4.1）")
        # 空素材不算失败，但若清单引用了不存在的图，上面已记 fail
    if unregistered and not on_disk:
        pass

    if fail:
        print(f"❌ 未通过（{len(fail)} 项）：")
        for kind, msg in fail:
            print(f"  - [{kind}] {msg}")
        return 1

    print("✅ 通过：素材全部可引用、可追踪、可复现")
    return 0


if __name__ == "__main__":
    sys.exit(main())
