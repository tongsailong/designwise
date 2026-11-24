#!/usr/bin/env python3
"""design_measure.py — 界面截图的客观视觉事实（不判断好坏）

给评审提供"往哪里看"的事实，不提供结论：
  - 背景/留白占比、主色面积比、中性色占比、冷暖倾向
  - 视觉重心的位置与集中度、三分区能量分布、边缘密度、左右对称性
  - 多图之间的色板重合、背景明度差、冷暖一致性与密度差

用法：
    python3 scripts/design_measure.py --image shots/p1.png
    python3 scripts/design_measure.py --image shots/p1.png --image shots/p2.png \
        --out measure.json

退出码：0 = 正常输出；2 = 用法或环境错误。

边界：**脚本只给事实**。留白 62% 不代表好，18% 也不代表坏；数值异常只说明"往这里看"，
是否成立由评审按 `critique-guide.md`「构成与视觉关系判据」结合真实内容判断。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - 环境缺失时直接报错，不静默降级
    np = None
    Image = None

SCHEMA = "designwise-measure/v1"
PALETTE_BINS = 32          # 每通道 32 档，合并邻近色
NEUTRAL_CHROMA = 12        # max-min ≤ 12 视为近中性
WARM_DELTA = 6.0           # 平均 R−B 的冷暖分界（仅统计有色像素）
BACKGROUND_TOLERANCE = 20  # 与主背景色的 RGB 欧氏距离 ≤ 20 视为背景
INK_LUMA = 0.35            # 亮度低于此值视为深色内容（文字/控件）


def die(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    raise SystemExit(2)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rgb_array(path: Path) -> np.ndarray:
    if np is None or Image is None:
        die("未安装 Pillow 与 numpy（python3 -m pip install pillow numpy）；无法测量")
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
    return np.asarray(rgb, dtype=np.float32)


def quantize(arr: np.ndarray) -> np.ndarray:
    step = 256.0 / PALETTE_BINS
    return np.minimum(PALETTE_BINS - 1,
                      (arr // step).astype(np.int32))


def palette_top(arr: np.ndarray, limit: int = 8) -> list[dict]:
    q = quantize(arr)
    keys = (q[:, :, 0] * PALETTE_BINS + q[:, :, 1]) * PALETTE_BINS + q[:, :, 2]
    counts = np.bincount(keys.ravel(), minlength=PALETTE_BINS ** 3)
    total = int(keys.size) or 1
    order = np.argsort(counts)[::-1][:limit]
    step = 256.0 / PALETTE_BINS
    out = []
    for idx in order:
        count = int(counts[idx])
        if count == 0:
            continue
        r = int((idx // (PALETTE_BINS * PALETTE_BINS)) * step + step / 2)
        g = int(((idx // PALETTE_BINS) % PALETTE_BINS) * step + step / 2)
        b = int((idx % PALETTE_BINS) * step + step / 2)
        out.append({
            "rgb": [r, g, b],
            "hex": "#%02x%02x%02x" % (r, g, b),
            "ratio": round(count / total, 4),
        })
    return out


def gradient_map(luma: np.ndarray) -> np.ndarray:
    gx = np.zeros_like(luma)
    gy = np.zeros_like(luma)
    gx[:, 1:] = np.abs(np.diff(luma, axis=1))
    gy[1:, :] = np.abs(np.diff(luma, axis=0))
    return (gx + gy) / 2.0


def thirds(values: np.ndarray) -> list[list[float]]:
    h, w = values.shape
    total = float(values.sum()) or 1.0
    grid = []
    for row in range(3):
        cells = []
        for col in range(3):
            block = values[row * h // 3:(row + 1) * h // 3,
                           col * w // 3:(col + 1) * w // 3]
            cells.append(round(float(block.sum()) / total, 4))
        grid.append(cells)
    return grid


def centroid(values: np.ndarray) -> tuple[float, float]:
    h, w = values.shape
    total = float(values.sum())
    if total <= 0:
        return 0.5, 0.5
    xs = np.arange(w, dtype=np.float64)
    ys = np.arange(h, dtype=np.float64)
    cx = float((values.sum(axis=0) * xs).sum() / total) / max(w - 1, 1)
    cy = float((values.sum(axis=1) * ys).sum() / total) / max(h - 1, 1)
    return round(cx, 4), round(cy, 4)


def symmetry_score(luma: np.ndarray) -> float:
    """左右镜像相关性（亮度场，不是边缘尖峰）；先降采样，避免 1px 错位判成不对称。"""
    small = np.asarray(Image.fromarray(luma.astype(np.float32)).resize(
        (32, 32), Image.BILINEAR))
    mirrored = small[:, ::-1]
    a = small.ravel()
    b = mirrored.ravel()
    if float(a.std()) == 0 or float(b.std()) == 0:
        return 1.0
    return round(float(np.corrcoef(a, b)[0, 1]), 4)


def analyze(path: Path) -> dict:
    arr = rgb_array(path)
    raw = path.read_bytes()
    h, w, _ = arr.shape
    luma = (0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1]
            + 0.0722 * arr[:, :, 2]) / 255.0
    edges = gradient_map(luma)
    top = palette_top(arr)
    bg = np.array(top[0]["rgb"], dtype=np.float32)
    distance = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    background = distance <= BACKGROUND_TOLERANCE

    chroma = arr.max(axis=2) - arr.min(axis=2)
    colored = chroma > NEUTRAL_CHROMA
    colored_count = int(colored.sum())
    if colored_count:
        delta = float((arr[:, :, 0] - arr[:, :, 2])[colored].mean())
    else:
        delta = 0.0
    temperature = "warm" if delta > WARM_DELTA else (
        "cool" if delta < -WARM_DELTA else "neutral")

    cx, cy = centroid(edges)
    grid = thirds(edges)
    concentration = round(max(max(row) for row in grid), 4)

    return {
        "path": str(path),
        "sha256": sha256_bytes(raw),
        "width": w,
        "height": h,
        "background_ratio": round(float(background.mean()), 4),
        "ink_ratio": round(float((luma < INK_LUMA).mean()), 4),
        "neutral_ratio": round(1.0 - colored_count / max(w * h, 1), 4),
        "temperature": temperature,
        "temperature_delta": round(delta, 2),
        "palette_top": top,
        "centroid": {"x": cx, "y": cy},
        "thirds_energy": grid,
        "concentration": concentration,
        "edge_density": round(float(edges.mean()), 4),
        "symmetry": symmetry_score(luma),
    }


def consistency(results: list[dict]) -> dict:
    """多图之间的事实差异；命中与否是事实描述，不是设计结论。"""
    if len(results) < 2:
        return {}
    palette_sets = []
    for item in results:
        palette_sets.append({tuple(c["rgb"]) for c in item["palette_top"][:6]})
    overlaps = []
    for i in range(len(palette_sets)):
        for j in range(i + 1, len(palette_sets)):
            a, b = palette_sets[i], palette_sets[j]
            union = a | b
            overlaps.append(len(a & b) / len(union) if union else 0.0)
    backgrounds = [c["palette_top"][0]["rgb"] for c in results]
    bg_luma = [round(sum(0.2126 * r + 0.7152 * g + 0.0722 * b
                        for r, g, b in [bg]) / 255.0, 4)
               for bg in backgrounds]
    densities = [item["edge_density"] for item in results]
    temps = [item["temperature"] for item in results]
    return {
        "pair_palette_overlap": [round(v, 4) for v in overlaps],
        "background_luma": bg_luma,
        "background_luma_spread": round(max(bg_luma) - min(bg_luma), 4),
        "edge_density_spread": round(max(densities) - min(densities), 4),
        "temperature_values": temps,
        "temperature_consistent": len(set(temps)) == 1,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="界面截图的客观视觉事实（不判断好坏）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0 正常；2 用法或环境错误")
    ap.add_argument("--image", action="append", default=[], metavar="PNG",
                    help="截图路径，可重复；多张时额外输出一致性事实")
    ap.add_argument("--out", default=None, help="输出 JSON 路径；缺省只打印")
    args = ap.parse_args()

    if not args.image:
        die("至少需要一个 --image")
    paths = [Path(p) for p in args.image]
    results = [analyze(p) for p in paths]

    payload = {
        "schema": SCHEMA,
        "images": results,
        "consistency": consistency(results),
        "note": "只给客观事实，不判断设计好坏；是否成立由评审结合内容与判据判断",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {out}")
    else:
        print(text)

    for item in results:
        print(f"{Path(item['path']).name}: 背景 {item['background_ratio']:.0%} · "
              f"重心 ({item['centroid']['x']:.2f}, {item['centroid']['y']:.2f}) · "
              f"三分区集中度 {item['concentration']:.2f} · "
              f"{item['temperature']} · 边缘密度 {item['edge_density']:.3f}")
    if len(results) > 1:
        c = payload["consistency"]
        print(f"一致性事实：色板重合 {c['pair_palette_overlap']} · "
              f"背景明度差 {c['background_luma_spread']} · "
              f"密度差 {c['edge_density_spread']} · 冷暖一致 {c['temperature_consistent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
