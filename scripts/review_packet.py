#!/usr/bin/env python3
"""review_packet.py — 生成对外审美咨询的评审交接包

把「产品/方向/本轮改动 + 真实截图（sha256/尺寸/屏幕/状态/缩放）」整理成一份 Markdown，
供 Copilot 的 SOL 通道按 `--materials` + `--image` 消费；本脚本只做材料装配与事实校验，
不判断设计好坏，也不调用任何模型。

用法：
    python3 scripts/review_packet.py --spec review-packet.json --out review-packet.md
    python3 scripts/review_packet.py --spec review-packet.json --json

spec（JSON）：
    {
      "product": "稍后读工具",
      "goal": "地铁碎片时间读完长文",
      "audience": "通勤族",
      "direction": "采用方向 B：纸面阅读",
      "dna": "暖白底 / 近黑正文 / 单一进度刻度 / 无卡片边框",
      "device": "Android 1080x2400 @3x（460dp 宽）",
      "version": "prototype 2026-11-24",
      "changes_since_last": "P1 主行动上移；P2 行宽收窄",
      "images": [
        {"path": "shots/r1-p1.png", "screen": "P1", "state": "默认",
         "scale": "1.0", "note": "首屏"}
      ],
      "questions": ["可选：覆盖默认九问中的部分问题"]
    }

退出码：0 = 已生成；2 = 用法/材料错误（缺字段、图片不存在、重复像素等）。

边界：图片必须是当前版本真实产物；历史修复后截图不得标成修复前状态。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - 环境缺失时直接报错，不静默降级
    Image = None

SCHEMA = "designwise-review-packet/v1"
REQUIRED = ("product", "goal", "audience", "direction", "device", "images")
QUESTIONS = (
    "这一版是否有独特且站得住的视觉概念，还是可以套到任何同类产品上？",
    "第一眼落点对不对？用户最该先看到的信息，是不是视觉上最重的元素？",
    "构图与视觉重量是否协调：主体、留白、边缘元素之间有没有互相争夺？",
    "色彩、字号层级、材质、光线是否统一在同一套关系里？",
    "有没有明显的模板感或 AI 味：无来由的渐变、阴影、大圆角卡片、玻璃拟态、装饰形状？",
    "是否匹配该产品的用户、使用场景与定位（而不是匹配某种流行风格）？",
    "哪些视觉细节值得保留，不要在后一轮打磨里改掉？",
    "如果只能改三处，改哪三处对整体提升最大？给到具体位置与目标状态。",
    "主代理可能忽略的视觉问题是什么（跨页一致性、密度节奏、极端内容、深色模式）？",
)


def die(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    raise SystemExit(2)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_spec(path: Path) -> dict:
    if not path.is_file():
        die(f"spec 不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"无法读取 spec {path}：{exc}")
    if not isinstance(data, dict):
        die("spec 顶层必须是对象")
    for key in REQUIRED:
        if key not in data:
            die(f"spec 缺少必填字段：{key}")
    if not isinstance(data["images"], list) or not data["images"]:
        die("images 必须是非空数组")
    return data


def probe_image(path: Path) -> tuple[int, int]:
    if Image is None:
        die("未安装 Pillow（python3 -m pip install pillow）；无法校验图片")
    try:
        with Image.open(path) as im:
            im.load()
            return im.width, im.height
    except Exception as exc:
        die(f"无法解码图片 {path}：{exc}")
    return 0, 0  # 不可达，保留类型完整性


def image_rows(spec: dict, base: Path) -> list[dict]:
    rows, seen_paths, seen_hashes = [], set(), set()
    for index, item in enumerate(spec["images"], start=1):
        if not isinstance(item, dict) or not item.get("path"):
            die(f"images[{index}] 缺少 path")
        if not item.get("screen"):
            die(f"images[{index}]（{item['path']}）缺少 screen")
        if not item.get("state"):
            die(f"images[{index}]（{item['path']}）缺少 state")
        raw_path = Path(item["path"])
        path = raw_path if raw_path.is_absolute() else (base / raw_path)
        if not path.is_file():
            die(f"图片不存在：{path}")
        key = str(path.resolve())
        if key in seen_paths:
            die(f"同一文件重复出现：{path}")
        seen_paths.add(key)
        data = path.read_bytes()
        digest = sha256_bytes(data)
        if digest in seen_hashes:
            die(f"两张图内容完全相同（同一 sha256）：{path}")
        seen_hashes.add(digest)
        width, height = probe_image(path)
        rows.append({
            "index": index,
            "path": str(path),
            "name": path.name,
            "screen": item["screen"],
            "state": item["state"],
            "scale": str(item.get("scale") or "1.0"),
            "note": item.get("note") or "",
            "width": width,
            "height": height,
            "sha256": digest,
        })
    return rows


def render(spec: dict, rows: list[dict]) -> str:
    questions = spec.get("questions") or list(QUESTIONS)
    if not isinstance(questions, list) or not questions:
        die("questions 必须是非空数组")
    lines = [
        "# 设计评审交接包",
        "",
        "> 本包由 DesignWise 生成。图像是当前版本的真实产物；请只依据像素判断，"
        "不要从文件名、文字或代码推断画面。看不清或被裁切的细节写“无法判断”。",
        "",
        "## 1. 产品与目标",
        "",
        f"- 产品：{spec['product']}",
        f"- 用户与场景：{spec['audience']}",
        f"- 本次目标：{spec['goal']}",
        f"- 设备与基准：{spec['device']}",
    ]
    if spec.get("version"):
        lines.append(f"- 版本：{spec['version']}")
    lines += ["", "## 2. 方向与视觉 DNA", "", f"- 方向：{spec['direction']}"]
    if spec.get("dna"):
        lines.append(f"- 视觉 DNA：{spec['dna']}")
    lines += ["", "## 3. 本轮改动", "",
              f"{spec.get('changes_since_last') or '首次评审（无上一轮）'}",
              "", "## 4. 图像材料（顺序与提交的 --image 一致）", "",
              "| # | 文件 | 屏幕 | 状态 | 缩放 | 尺寸 | sha256 | 说明 |",
              "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row['index']} | {row['name']} | {row['screen']} | {row['state']} | "
            f"{row['scale']} | {row['width']}x{row['height']} | "
            f"`{row['sha256'][:16]}…` | {row['note']} |")
    lines += ["", "## 5. 本次要回答的问题", ""]
    for i, question in enumerate(questions, start=1):
        lines.append(f"{i}. {question}")
    lines += [
        "",
        "## 6. 材料边界",
        "",
        "- 每张图的 sha256 已登记；提交时请核对与 `--image` 的对应顺序一致。",
        "- 只评本包内的当前版本，不评历史版本、不假设未提供的页面与状态。",
        "- 输出请区分**主观偏好**与**客观缺陷**（影响理解、可达、可读、一致性），"
        "并给位置与可执行改法；不接受“更高级/更精致”这类没有指向的评价。",
        "- 本包是咨询材料，不构成设计批准；采纳与否由 DesignWise 侧主代理决定。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="生成对外审美咨询的评审交接包（只装配材料，不调用模型）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0 已生成；2 用法/材料错误")
    ap.add_argument("--spec", required=True, help="交接包 spec（JSON）")
    ap.add_argument("--out", default=None, help="输出 Markdown；缺省打印到 stdout")
    ap.add_argument("--json", action="store_true",
                    help="额外输出机器可读摘要（含图片 sha256/尺寸）")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    spec = load_spec(spec_path)
    rows = image_rows(spec, spec_path.parent)
    text = render(spec, rows)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {out}")
    else:
        print(text)

    if args.json:
        summary = {
            "schema": SCHEMA,
            "spec": str(spec_path),
            "image_count": len(rows),
            "images": [
                {k: row[k] for k in ("index", "name", "screen", "state",
                                     "scale", "width", "height", "sha256")}
                for row in rows
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
