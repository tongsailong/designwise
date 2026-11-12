#!/usr/bin/env python3
"""direction_divergence.py — 概念方向差异实测（防换皮）

对两张或多张概念图计算：
  1. palette_distance      4×4×4 RGB 直方图距离（0–1，越大越不同）
  2. skeleton_correlation  32×20 灰度边缘图相关系数（-1–1，越大骨架越像）

判定：
  palette_distance < --palette-threshold   → 同色板
  skeleton_correlation > --skeleton-threshold → 同骨架
  两者同时成立                             → reskin（换皮）

用法：
    python3 scripts/direction_divergence.py \
      --image concepts/A.png --image concepts/B.png [--image concepts/C.png] \
      --out direction-divergence.json [--strict]

退出码：0 = 正常输出；1 = --strict 下判出同骨架/换皮；2 = 用法或环境错误。

边界：脚本只给事实，不判断设计好坏，也不判断方向是否正确。概念图常带设备外框，
默认裁掉 --crop（默认 8%）边框后再测；该处理偏保守，结论仍需结合方向卡。
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - 环境缺失时直接报错，不静默降级
    Image = None

SCHEMA = "designwise-divergence/v1"
SKELETON_SIZE = (32, 20)   # (width, height)
PALETTE_BINS = 4           # 每通道 4 档 → 4×4×4 = 64 桶


def die(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    raise SystemExit(2)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_rgb(path: Path):
    if Image is None:
        die("未安装 Pillow（python3 -m pip install pillow）；无法做差异实测")
    if not path.is_file():
        die(f"图片不存在：{path}")
    try:
        with Image.open(path) as im:
            im.load()
            rgb = im.convert("RGB")
    except Exception as exc:  # 解码失败不写占位结果
        die(f"无法解码图片 {path}：{exc}")
    if rgb.width < 8 or rgb.height < 8:
        die(f"图片过小（{rgb.width}×{rgb.height}）：{path}")
    return rgb


def crop_border(im, fraction: float):
    if fraction <= 0:
        return im
    dx = int(im.width * fraction)
    dy = int(im.height * fraction)
    if im.width - 2 * dx < 8 or im.height - 2 * dy < 8:
        return im
    return im.crop((dx, dy, im.width - dx, im.height - dy))


def palette_histogram(im) -> list[float]:
    """4×4×4 RGB 直方图（已归一化）。"""
    bins = PALETTE_BINS
    hist = [0] * (bins ** 3)
    pixels = list(im.getdata())
    total = len(pixels) or 1
    step = 256 / bins
    for r, g, b in pixels:
        ri = min(bins - 1, int(r // step))
        gi = min(bins - 1, int(g // step))
        bi = min(bins - 1, int(b // step))
        hist[(ri * bins + gi) * bins + bi] += 1
    return [v / total for v in hist]


def palette_distance(h1: list[float], h2: list[float]) -> float:
    """L1/2 → 0–1。完全相同的分布为 0。"""
    return sum(abs(a - b) for a, b in zip(h1, h2)) / 2.0


def edge_vector(im) -> list[float]:
    """32×20 灰度 + 简单水平/垂直差分近似梯度，返回展平向量。"""
    small = im.convert("L").resize(SKELETON_SIZE, Image.BILINEAR)
    w, h = small.size
    px = list(small.getdata())
    vec: list[float] = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            gx = abs(px[i] - px[y * w + x - 1]) if x > 0 else 0.0
            gy = abs(px[i] - px[(y - 1) * w + x]) if y > 0 else 0.0
            vec.append((gx + gy) / 2.0)
    return vec


def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        # 两张图都没有边缘（纯色）时，无法判定骨架差异
        return 0.0
    return num / (da * db)


def verdict(palette: float, skeleton: float, p_th: float, s_th: float) -> str:
    same_palette = palette < p_th
    same_skeleton = skeleton > s_th
    if same_palette and same_skeleton:
        return "reskin"
    if same_skeleton:
        return "same-skeleton"
    if same_palette:
        return "same-palette"
    return "distinct"


def analyze(path: Path, crop: float):
    raw = path.read_bytes()
    im = load_rgb(path)
    size = list(im.size)
    im = crop_border(im, crop)
    return {
        "path": str(path),
        "sha256": sha256_bytes(raw),
        "size": size,
        "palette": palette_histogram(im),
        "skeleton": edge_vector(im),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="概念方向差异实测：色板距离 + 版式骨架相关性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0 正常；1 --strict 判出同骨架/换皮；2 用法或环境错误",
    )
    ap.add_argument("--image", action="append", default=[], metavar="PNG",
                    help="概念图路径，可重复（至少 2 个）")
    ap.add_argument("--out", default=None, help="输出 JSON 路径；缺省只打印")
    ap.add_argument("--strict", action="store_true",
                    help="任一对判为 same-skeleton / reskin 时退出码 1")
    ap.add_argument("--crop", type=float, default=0.08,
                    help="四边裁掉的边框比例（默认 0.08，用于去掉设备外框）")
    ap.add_argument("--palette-threshold", type=float, default=0.06,
                    help="色板距离阈值，低于判同色板（默认 0.06）")
    ap.add_argument("--skeleton-threshold", type=float, default=0.55,
                    help="骨架相关性阈值，高于判同骨架（默认 0.55）")
    args = ap.parse_args()

    if len(args.image) < 2:
        die("至少需要 2 个 --image；只有一个方向时不需要差异实测")
    if not (0.0 <= args.crop < 0.5):
        die("--crop 必须在 [0, 0.5) 内")
    if not (0.0 <= args.palette_threshold <= 1.0):
        die("--palette-threshold 必须在 [0, 1] 内")
    if not (-1.0 <= args.skeleton_threshold <= 1.0):
        die("--skeleton-threshold 必须在 [-1, 1] 内")

    paths = [Path(p) for p in args.image]
    results = [analyze(p, args.crop) for p in paths]

    pairs = []
    for (i, a), (j, b) in itertools.combinations(enumerate(results), 2):
        pd = palette_distance(a["palette"], b["palette"])
        sc = pearson(a["skeleton"], b["skeleton"])
        pairs.append({
            "a": paths[i].name,
            "b": paths[j].name,
            "palette_distance": round(pd, 4),
            "skeleton_correlation": round(sc, 4),
            "verdict": verdict(pd, sc, args.palette_threshold, args.skeleton_threshold),
        })

    payload = {
        "schema": SCHEMA,
        "crop": args.crop,
        "thresholds": {
            "palette": args.palette_threshold,
            "skeleton": args.skeleton_threshold,
        },
        "images": [
            {"path": r["path"], "sha256": r["sha256"], "size": r["size"]}
            for r in results
        ],
        "pairs": pairs,
        "conclusion": (
            "任一对同骨架/换皮：方向需要换骨架或换来源重出"
            if any(p["verdict"] in ("same-skeleton", "reskin") for p in pairs)
            else "无可测得的换皮；设计合格性仍须结合方向卡判断"
        ),
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {out}")
    else:
        print(text)

    for p in pairs:
        print(f"{p['a']} ↔ {p['b']}: palette={p['palette_distance']} "
              f"skeleton={p['skeleton_correlation']} → {p['verdict']}")

    if args.strict and any(p["verdict"] in ("same-skeleton", "reskin") for p in pairs):
        print("严格模式：判出同骨架/换皮，未通过。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
