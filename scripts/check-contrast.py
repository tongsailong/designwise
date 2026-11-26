#!/usr/bin/env python3
"""check-contrast.py — WCAG 对比度三档校验（交付前机械拦截）

为什么要有它：`content-guidelines.md` 定义了对比度三档门槛（① 正文文字 / ② 重要图标图形
/ ③ 纯装饰），但「看着还行」骗得过眼睛、骗不过公式。这个脚本把交付包 `adaptation-a11y.md`
里的逐对色值变成一条命令可判定的结论：**档 ①/② 低于门槛 = exit 1 = 不许交付**。

设计原则（复用而非新造）：
  - 纯标准库，无依赖；公式即 WCAG 2.1 相对亮度
  - 输入是一个 JSON 文件，字段与交付包对照表一一对应
  - 与 `scripts/check-skill.py` 同风格：退出码判定，直接可进 CI / 交付前手动跑

用法：
    python3 scripts/check-contrast.py pairs.json          # 校验
    python3 scripts/check-contrast.py pairs.json --md     # 顺便打印可粘进交付包的 markdown 表

输入 JSON（数组），每项：
    {
      "name": "主文字 ink/bg",      # 可读描述（必填）
      "fg": "#111418",             # 前景，HEX（必填）
      "bg": "#F4F5F3",             # 背景，HEX（必填）
      "tier": "text",              # text | graphic | decorative（缺省按最严的 text）
      "size": 16,                  # 可选：字号 px；text 档用于判「大字」（>=24，或 >=18.66 且 bold）
      "bold": false                # 可选，默认 false
    }

门槛：text 正常字 >=4.5，text 大字 >=3.0，graphic >=3.0，decorative 无门槛（仅报告）。
退出码：0 = 无阻断项；1 = 存在档 ①/② 不合格项。
"""

import argparse
import json
import sys


def _srgb_channel(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise ValueError(f"非法 HEX 色值：{hex_color}")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def ratio(fg: str, bg: str) -> float:
    l1, l2 = _luminance(fg), _luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def is_large(size, bold: bool) -> bool:
    if size is None:
        return False
    size = float(size)
    return size >= 24 or (size >= 18.66 and bool(bold))


def threshold_and_tier(item: dict):
    tier = item.get("tier", "text")
    if tier == "decorative":
        return None, "decorative"
    if tier == "graphic":
        return 3.0, "graphic"
    # text
    if is_large(item.get("size"), item.get("bold", False)):
        return 3.0, "text(large)"
    return 4.5, "text"


def main() -> int:
    ap = argparse.ArgumentParser(description="WCAG 对比度三档校验（交付前机械拦截）")
    ap.add_argument("json_file", help="色值对 JSON 文件路径")
    ap.add_argument("--md", action="store_true", help="同时输出可粘进交付包的 markdown 表")
    args = ap.parse_args()

    try:
        with open(args.json_file, encoding="utf-8") as f:
            pairs = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"❌ 读取输入失败：{e}")
        return 2

    if not isinstance(pairs, list) or not pairs:
        print("❌ 输入应为非空 JSON 数组（每项含 name/fg/bg/tier）")
        return 2

    blocking = []
    usage_errors = []
    rows = []
    print(f"对比度三档校验 · {len(pairs)} 对\n")
    for it in pairs:
        name = it.get("name", "(未命名)")
        fg, bg = it.get("fg"), it.get("bg")
        if not fg or not bg:
            usage_errors.append(f"{name}：缺 fg/bg")
            print(f"  ❌ {name}：缺 fg/bg")
            continue
        try:
            r = ratio(fg, bg)
        except ValueError as e:
            usage_errors.append(f"{name}：{e}")
            print(f"  ❌ {name}：{e}")
            continue
        thr, tier = threshold_and_tier(it)
        if thr is None:
            verdict = "装饰·不承载信息（无门槛）"
            mark = "•"
        elif r + 1e-9 >= thr:
            verdict = f"PASS (≥{thr})"
            mark = "✅"
        else:
            verdict = f"FAIL (<{thr})"
            mark = "❌"
            blocking.append((name, r, thr))
        print(f"  {mark} {r:5.2f}:1  [{tier:<12}] {name}  — {verdict}")
        rows.append((name, fg, bg, f"{r:.2f}:1", tier, verdict))

    if args.md:
        print("\n| 前景 / 背景 | 实测比 | 档位 | 判定 |")
        print("|---|---|---|---|")
        for name, fg, bg, rr, tier, verdict in rows:
            print(f"| `{fg}` / `{bg}` — {name} | {rr} | {tier} | {verdict} |")

    print()
    if usage_errors:
        print(f"❌ 输入错误 {len(usage_errors)} 项（缺色值 / 非法 HEX）——**不得视为通过**：")
        for e in usage_errors:
            print(f"  - {e}")
        return 2
    if blocking:
        print(f"❌ 存在 {len(blocking)} 个阻断项（档 ①/② 低于门槛），**交付包不合格**：")
        for name, r, thr in blocking:
            print(f"  - {name}：{r:.2f}:1 < {thr} —— 须改前景/背景色，或改判为装饰并标注")
        return 1
    print("✅ 无阻断项：档 ①/② 全部达标（档 ③ 装饰项已如实标注）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
