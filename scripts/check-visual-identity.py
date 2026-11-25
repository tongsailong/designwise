#!/usr/bin/env python3
"""check-visual-identity.py — 跨产品视觉身份对照（只给事实，不做裁决）

用途：判断两个（或多个）产品的成品素材在**frame 层**是否同构，并把相似拆到可解释的维度上。
面向的是「商店截图 / 宣传图 / 版式化成品」这类带真实界面的构图，不是概念图方向比较——
后者用 `direction_divergence.py`。

输出的是什么（全部是可直接核对的测量事实）：
  1. 底色      边框带中位数 RGB 与亮度
  2. 明暗分带  纵向十等分的暗像素占比（文字块落在哪一段）
  3. 边缘分带  纵向十等分的强边缘占比（内容与版式的密度节奏）
  4. 左边界    纵向十等分各自的暗像素最小 x（文字区边距 / 图版边距）
  5. 强调色    暖红像素面积占比与纵向重心
两两之间再给：底色距离、分带 L1 距离与相关系数、主文字带是否相同、文字左边距差值。

**不做的事（硬边界）**：
  - 不输出 verdict，不设相似度阈值，不因相似改退出码；
  - 不判断设计好坏，也不判断「算不算同质化」——归因按
    `references/cross-product-differentiation.md` §7 的维度表由人做；
  - 不存图片。`--record` 只写事实与 sha256。

用法：
    python3 scripts/check-visual-identity.py \
        --image a.png --label 计步器 --image b.png --label 历法
    python3 scripts/check-visual-identity.py --image a.png --label 历法 --record
    python3 scripts/check-visual-identity.py --image a.png --compare-ledger 10

退出码：0 = 正常输出（无论结论如何）；2 = 用法错误或图片无法解码。

为什么不用整图相似度：实测 2026-11-25，对两个真实产品各 5 张成品，
`direction_divergence.py` 的 skeleton_correlation = 0.2138（判为「不同骨架」），
而两套素材的版式语汇高度同构——内嵌 App 界面内容不同会淹没版式同构，产生假阴性。
本脚本改用「纵向分带 + 边距 + 强调色角色」，这些量不随界面内容整体翻转。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover - 环境缺失时直接报错，不静默降级
    Image = None
    ImageChops = None

SCHEMA = "designwise-visual-identity/v1"
BANDS = 10               # 纵向十等分
BORDER = 8               # 取底色的边框带宽（像素，原始分辨率）
EDGE_MIN = 18            # 强边缘阈值（0–255 亮度差）
DARK_RATIO = 0.55        # 暗像素 = 亮度低于底色亮度的这个比例
LEDGER_DIR = ".designwise"
LEDGER_NAME = "identity-frames.jsonl"


class Fatal(Exception):
    """不可继续的错误：打印后以退出码 2 结束，绝不写占位事实。"""


def die(msg: str):
    print(f"错误：{msg}", file=sys.stderr)
    raise Fatal(msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rgb(path: Path):
    if Image is None:
        die("未安装 Pillow（python3 -m pip install pillow）；无法做视觉身份对照")
    if not path.is_file():
        die(f"图片不存在：{path}")
    try:
        with Image.open(path) as im:
            im.load()
            return im.convert("RGB")
    except Exception as exc:  # 解码失败不写占位结果
        die(f"无法解码图片 {path}：{exc}")


def rows_bands(h: int):
    step = h / BANDS
    return [(int(round(i * step)), int(round((i + 1) * step))) for i in range(BANDS)]


def border_histogram(im_l, b: int):
    """四边框带（原始分辨率）的亮度直方图，用中位数当底色亮度，避免被主体拉偏。"""
    w, h = im_l.size
    hist = [0] * 256
    for box in ((0, 0, w, b), (0, h - b, w, h), (0, 0, b, h), (w - b, 0, w, h)):
        sub = im_l.crop(box)
        if sub.width <= 0 or sub.height <= 0:
            continue
        # 缩到固定宽度再统计，控制开销且保留分布
        sub = sub.resize((max(1, min(160, sub.width)), max(1, min(160, sub.height))))
        for i, v in enumerate(sub.histogram()):
            hist[i] += v
    total = sum(hist) or 1
    acc = 0
    for i, v in enumerate(hist):
        acc += v
        if acc * 2 >= total:
            return i
    return 128


def frame_facts(path: Path) -> dict:
    """提取单张图的 frame 事实。每个字段都可对着图核对。"""
    im = load_rgb(path)
    w, h = im.size
    if w < 32 or h < 32:
        die(f"图片过小（{w}×{h}）：{path}")

    l = im.convert("L")
    bg_lum = float(border_histogram(l, BORDER))
    dark_thr = bg_lum * DARK_RATIO

    # 暗像素掩码（0/255）与纵向边缘掩码
    dark = l.point(lambda v: 255 if v < dark_thr else 0)
    up = l.crop((0, 0, w, h - 1))
    down = l.crop((0, 1, w, h))
    gy = ImageChops.difference(up, down)
    edges = gy.point(lambda v: 255 if v > EDGE_MIN else 0)

    # 暖红强调色：R 明显高于 G/B 且与最暗通道拉开距离
    r, g, b = im.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    warm = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v > 90 else 0),
                            ImageChops.subtract(r, g).point(lambda v: 255 if v > 35 else 0)),
        ImageChops.multiply(
            ImageChops.subtract(r, b).point(lambda v: 255 if v > 30 else 0),
            ImageChops.subtract(mx, mn).point(lambda v: 255 if v > 45 else 0)))

    bounds = rows_bands(h)
    dark_counts, edge_counts, left_edges = [], [], []
    for y0, y1 in bounds:
        box = (0, y0, w, max(y1, y0 + 1))
        dh = dark.crop(box)
        area = dh.width * dh.height or 1
        dark_counts.append(round(dh.histogram()[255] / area, 4))
        eh = edges.crop((0, y0, w, min(y1, h - 1)))
        earea = eh.width * eh.height or 1
        edge_counts.append(round(eh.histogram()[255] / earea, 4) if earea > 0 else 0.0)
        bbox = dh.getbbox()
        left_edges.append(round(bbox[0] / w, 4) if bbox else None)

    # 底色 RGB：用同一批边框像素的逐通道中位数
    border_pixels = []
    for box in ((0, 0, w, BORDER), (0, h - BORDER, w, h), (0, 0, BORDER, h), (w - BORDER, 0, w, h)):
        sub = im.crop(box)
        if sub.width > 0 and sub.height > 0:
            border_pixels.extend(list(sub.resize(
                (max(1, min(40, sub.width)), max(1, min(40, sub.height)))).getdata()))
    border_pixels.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    bg = border_pixels[len(border_pixels) // 2] if border_pixels else (bg_lum, bg_lum, bg_lum)

    # 强调色的面积与纵向重心（行均值 > 0 表示该行有暖红像素）
    accent_total = warm.histogram()[255]
    accent_y = None
    if accent_total:
        rows = warm.resize((1, h), Image.BOX)
        values = list(rows.getdata())
        weighted = [(y, v) for y, v in enumerate(values) if v]
        wsum = sum(v for _, v in weighted) or 1
        center = sum(y * v for y, v in weighted) / wsum
        accent_y = round(center / h, 3)

    head_half = dark_counts[: max(1, BANDS // 2)]
    dominant = max(range(len(head_half)), key=lambda i: head_half[i])
    text_lefts = [v for v in left_edges[:4] if v is not None]

    return {
        "file": path.name,
        "sha256": sha256_file(path),
        "size": [w, h],
        "bg_rgb": [int(bg[0]), int(bg[1]), int(bg[2])],
        "bg_luminance": round(bg_lum, 1),
        "dominant_text_band": dominant,
        "text_left_frac": min(text_lefts) if text_lefts else None,
        "accent_share": round(accent_total / (w * h), 4),
        "accent_y": accent_y,
        "dark_bands": dark_counts,
        "edge_bands": edge_counts,
        "left_bands": left_edges,
    }


def l1(a, b) -> float:
    return round(sum(abs(x - y) for x, y in zip(a, b)), 4)


def corr(a, b) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    if da == 0 or db == 0:
        return 0.0
    return round(num / (da * db), 4)


def band_diffs(a: dict, b: dict, key: str, tol: float = 0.10):
    """返回差值超过 tol 的分带下标——回答「哪一段不一样」，而不是「差多少分」。"""
    return [i for i, (x, y) in enumerate(zip(a[key], b[key])) if abs(x - y) > tol]


def compare(a: dict, b: dict) -> dict:
    bg_a, bg_b = a["bg_rgb"], b["bg_rgb"]
    bg_dist = round(sum((x - y) ** 2 for x, y in zip(bg_a, bg_b)) ** 0.5, 2)
    out = {
        "a": a.get("label") or a["file"],
        "b": b.get("label") or b["file"],
        "bg_distance_rgb": bg_dist,
        "bg_luminance_delta": round(abs(a["bg_luminance"] - b["bg_luminance"]), 1),
        "dark_bands_l1": l1(a["dark_bands"], b["dark_bands"]),
        "dark_bands_corr": corr(a["dark_bands"], b["dark_bands"]),
        "edge_bands_l1": l1(a["edge_bands"], b["edge_bands"]),
        "edge_bands_corr": corr(a["edge_bands"], b["edge_bands"]),
        "same_dominant_text_band": a["dominant_text_band"] == b["dominant_text_band"],
        "dominant_text_band": [a["dominant_text_band"], b["dominant_text_band"]],
        "text_left_delta_frac": (
            round(abs(a["text_left_frac"] - b["text_left_frac"]), 4)
            if a["text_left_frac"] is not None and b["text_left_frac"] is not None else None
        ),
        "accent_share": [a["accent_share"], b["accent_share"]],
        "accent_y": [a["accent_y"], b["accent_y"]],
        "bands_differing_dark": band_diffs(a, b, "dark_bands"),
        "bands_differing_edge": band_diffs(a, b, "edge_bands"),
    }
    return out


def ledger_path() -> Path:
    home = os.environ.get("DESIGNWISE_HOME") or os.path.join(os.path.expanduser("~"), LEDGER_DIR)
    return Path(home) / LEDGER_NAME


def record(entry: dict) -> Path:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def read_ledger(limit: int) -> list[dict]:
    path = ledger_path()
    if not path.is_file():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-limit:] if limit > 0 else out


def main() -> int:
    try:
        return _main()
    except Fatal:
        return 2


def _main() -> int:
    ap = argparse.ArgumentParser(
        description="跨产品视觉身份对照：frame 层事实 + 逐维度差异（不给 verdict）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0 正常；2 用法或环境错误。相似度不改变退出码。",
    )
    ap.add_argument("--image", action="append", default=[], metavar="PNG",
                    help="成品图路径，可重复")
    ap.add_argument("--label", action="append", default=[], metavar="NAME",
                    help="与 --image 顺序一一对应的产品/批次名，可省略")
    ap.add_argument("--out", default=None, help="输出 JSON 路径；缺省只打印")
    ap.add_argument("--record", action="store_true",
                    help="把事实与 sha256 追加到本机外观指纹（不存图片）")
    ap.add_argument("--compare-ledger", type=int, default=0, metavar="N",
                    help="与最近 N 条已记录指纹比较")
    ap.add_argument("--ledger", action="store_true", help="只打印已记录的指纹")
    args = ap.parse_args()

    if args.ledger:
        entries = read_ledger(args.compare_ledger or 20)
        print(json.dumps({"schema": SCHEMA + "/ledger", "path": str(ledger_path()),
                          "count": len(entries), "entries": entries},
                         ensure_ascii=False, indent=2))
        return 0

    if not args.image:
        die("至少需要一个 --image")
    if args.label and len(args.label) != len(args.image):
        die("--label 必须与 --image 数量相同（顺序一一对应）")

    results = []
    for i, raw in enumerate(args.image):
        p = Path(raw)
        facts = frame_facts(p)
        if args.label:
            facts["label"] = args.label[i]
        results.append(facts)

    pairs = [compare(results[i], results[j])
             for i in range(len(results)) for j in range(i + 1, len(results))]

    ledger_pairs = []
    if args.compare_ledger:
        history = read_ledger(args.compare_ledger)
        for cur in results:
            for old in history:
                if old.get("sha256") == cur["sha256"]:
                    continue
                ledger_pairs.append(compare(cur, old))

    payload = {
        "schema": SCHEMA,
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "bands": BANDS,
        "images": [{k: v for k, v in r.items()} for r in results],
        "pairs": pairs,
        "ledger_pairs": ledger_pairs,
        "note": (
            "这些是测量事实，不是裁决。相似落在哪一层、该改什么，按 "
            "references/cross-product-differentiation.md §7 的归因表判断；"
            "本脚本不设阈值、不输出通过/不通过。"
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

    for r in results:
        name = r.get("label") or r["file"]
        print(f"{name}: bg={r['bg_rgb']} 主文字带={r['dominant_text_band']}/9 "
              f"文字左边距={r['text_left_frac']} 强调色={r['accent_share']}@y{r['accent_y']}")
    for p in pairs:
        print(f"{p['a']} ↔ {p['b']}: bgΔ={p['bg_distance_rgb']} "
              f"darkL1={p['dark_bands_l1']} edgeL1={p['edge_bands_l1']} "
              f"主文字带={p['dominant_text_band']} 左边距Δ={p['text_left_delta_frac']}")

    if args.record:
        for r in results:
            entry = {k: r[k] for k in (
                "file", "sha256", "size", "bg_rgb", "bg_luminance", "dominant_text_band",
                "text_left_frac", "accent_share", "accent_y", "dark_bands", "edge_bands",
                "left_bands")}
            if "label" in r:
                entry["label"] = r["label"]
            entry["recorded_at"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
            path = record(entry)
        print(f"已记录 {len(results)} 条指纹 → {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
