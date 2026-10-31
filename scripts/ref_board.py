#!/usr/bin/env python3
"""ref_board.py — 参考板采集：真实参考 URL / 本地图 → 截图 + 一块看板。

只做三件事：
1. 用 check-ui.mjs 的 Chrome/CDP 通路给每个参考网址截一张真实像素图（不新增 Playwright 依赖）；
2. 把真实截图与本地图排成 board.html（网格看板），供人眼与 agent 一起量；
3. 有 Pillow 时另出一张 board.jpg，并做疑似空白/未渲染检测。

它不判断美丑，也不产出可交付素材：看板里的像素是**参考**，不是本项目的成品。

用法：
  python3 scripts/ref_board.py --out ./ref-board --url https://example.com --image ./ref.jpg
  python3 scripts/ref_board.py --out ./ref-board --image ./a.png --image ./b.png --title "登录页参考"

退出码：0 成功；1 部分来源失败（已成功的仍出板）；2 用法/环境错误（如缺 Chrome 或 node）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import os
import shutil
import subprocess
import sys

try:  # Pillow 可选：只用于 board.jpg 与空白检测
    from PIL import Image, ImageStat
except Exception:  # pragma: no cover - 环境相关
    Image = None
    ImageStat = None

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK_UI = os.path.join(HERE, "check-ui.mjs")

CHROME_CANDIDATES = (
    "/home/ctyun/.local/bin/google-chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
)


class RefBoardError(RuntimeError):
    """环境或用法错误：必须让调用方看到，不能悄悄出半块板。"""


def find_chrome(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    env = os.environ.get("CHROME")
    if env and os.path.isfile(env):
        return env
    for candidate in CHROME_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    # Playwright 自带的 chromium 也可用（本项目不依赖 playwright，但本机可能装过）
    cache = os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright")
    if os.path.isdir(cache):
        versions = sorted(
            (d for d in os.listdir(cache) if d.startswith("chromium-")),
            key=lambda d: int(d.split("-")[1]) if d.split("-")[1].isdigit() else 0,
            reverse=True,
        )
        for version in versions:
            for rel in ("chrome-linux64/chrome", "chrome-linux/chrome"):
                path = os.path.join(cache, version, rel)
                if os.path.isfile(path):
                    return path
    return None


def summarize_blockers(report: dict) -> list[str]:
    """把 check-ui 的红灯压成一句句可读事实；参考站点不要求达标，只记录。"""
    out: list[str] = []
    if not report:
        return out
    for key, label in (("tap", "触控尺寸"), ("font", "字号")):
        section = report.get(key) or {}
        if section.get("failures"):
            out.append(f"{label}不达标 {len(section['failures'])} 处")
    if (report.get("overflow") or {}).get("fail"):
        out.append("横向溢出")
    if report.get("consoleErrors"):
        out.append(f"控制台错误 {len(report['consoleErrors'])} 条")
    if (report.get("images") or {}).get("broken"):
        out.append(f"图片加载失败 {report['images']['broken']} 张")
    contrast = report.get("contrast") or {}
    if contrast.get("failures"):
        out.append(f"文字对比度不足 {len(contrast['failures'])} 处")
    return out


def capture_url(url: str, shot_path: str, chrome: str, width: int, height: int,
                full: bool = False, timeout: int = 120) -> dict:
    """调 check-ui.mjs 截一张真实像素图。截图没落地就报错，不返回假成功。"""
    node = shutil.which("node")
    if not node:
        raise RefBoardError("找不到 node：截图依赖 scripts/check-ui.mjs（需要 Node >= 22）")
    if not os.path.isfile(CHECK_UI):
        raise RefBoardError(f"找不到 {CHECK_UI}")
    os.makedirs(os.path.dirname(os.path.abspath(shot_path)), exist_ok=True)
    cmd = [
        node, CHECK_UI, "--url", url, "--shot", shot_path,
        "--width", str(width), "--height", str(height),
        "--font-min", "10", "--chrome", chrome,
    ]
    if full:
        cmd.append("--full")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RefBoardError(f"截图超时（{timeout}s）：{url}") from exc

    data = {}
    if proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = {}
    report = (data.get("reports") or [{}])[0]
    shot = report.get("shot") or {}
    if shot.get("error") or not os.path.isfile(shot_path):
        detail = shot.get("error") or (proc.stderr.strip().splitlines() or ["未知错误"])[0]
        raise RefBoardError(f"截图失败：{url} → {detail}")
    return {
        "title": report.get("title") or "",
        "blockers": summarize_blockers(report),
        "bytes": os.path.getsize(shot_path),
    }


def detect_blank(path: str, stddev_threshold: float = 2.0) -> dict:
    """疑似空白检测：整张图近乎单一颜色 → 可能没渲染出来（WebGL/懒加载/权限页）。

    返回 {"blank": bool|None, "stddev": float|None, "reason": str}；无 Pillow 时 blank 为 None。
    """
    if Image is None or ImageStat is None:
        return {"blank": None, "stddev": None, "reason": "未安装 Pillow，跳过空白检测"}
    try:
        with Image.open(path) as img:
            gray = img.convert("L")
            stat = ImageStat.Stat(gray)
            stddev = float(stat.stddev[0])
            mean = float(stat.mean[0])
    except Exception as exc:  # 坏图/非图片
        return {"blank": None, "stddev": None, "reason": f"无法读取图片：{exc}"}
    blank = stddev < stddev_threshold
    reason = "近乎单一颜色（疑似空白/未渲染）" if blank else "有内容"
    return {"blank": blank, "stddev": round(stddev, 2), "mean": round(mean, 1), "reason": reason}


def compose_sheet(entries: list[dict], out_path: str, thumb_width: int = 420) -> dict:
    """把成板截图拼成一张 board.jpg（有 Pillow 才做）。失败只报原因，不影响 board.html。"""
    if Image is None:
        return {"ok": False, "reason": "未安装 Pillow，未生成 board.jpg"}
    usable = [e for e in entries if e.get("shot") and os.path.isfile(e["shot"])]
    if not usable:
        return {"ok": False, "reason": "没有可用截图"}
    thumbs = []
    try:
        for entry in usable:
            with Image.open(entry["shot"]) as img:
                ratio = thumb_width / img.width
                size = (thumb_width, max(1, int(img.height * ratio)))
                thumbs.append(img.convert("RGB").resize(size))
        cols = min(3, len(thumbs))
        rows = (len(thumbs) + cols - 1) // cols
        gap = 12
        cell_w = thumb_width
        cell_h = max(t.height for t in thumbs)
        sheet = Image.new("RGB", (cols * cell_w + gap * (cols + 1),
                                  rows * cell_h + gap * (rows + 1)), (18, 18, 20))
        for i, thumb in enumerate(thumbs):
            x = gap + (i % cols) * (cell_w + gap)
            y = gap + (i // cols) * (cell_h + gap)
            sheet.paste(thumb, (x, y))
        sheet.save(out_path, "JPEG", quality=88)
    except Exception as exc:
        return {"ok": False, "reason": f"合成失败：{exc}"}
    return {"ok": True, "path": out_path, "columns": cols, "count": len(thumbs)}


def build_board_html(entries: list[dict], title: str, created: str) -> str:
    """生成自包含看板（只引本地截图，不联网）。"""
    cards = []
    for i, entry in enumerate(entries, 1):
        src = entry.get("rel_shot") or ""
        label = entry.get("label") or entry.get("source") or f"#{i}"
        meta = []
        if entry.get("title"):
            meta.append(f"页面标题：{entry['title']}")
        meta.append("来源：" + ("网址" if entry.get("kind") == "url" else "本地图"))
        if entry.get("blockers"):
            meta.append("采集提示：" + "；".join(entry["blockers"]))
        if entry.get("blank") is True:
            meta.append("⚠ 疑似空白：" + (entry.get("blank_reason") or "近乎单一颜色"))
        elif entry.get("blank") is False:
            meta.append("像素有内容")
        note = entry.get("note") or ""
        if entry.get("kind") == "url" and entry.get("source"):
            shown = entry["source"]
            source_html = (
                f'<div class="src">{html.escape(shown)}</div>'
                f'<a class="open" href="{html.escape(shown)}" target="_blank" '
                f'rel="noreferrer">打开来源 ↗</a>'
            )
        else:
            source_html = f'<div class="src">{html.escape(entry.get("source") or "")}</div>'
        cards.append(f"""    <figure class="card">
      <div class="shot"><span class="no">{i:02d}</span><img src="{html.escape(src)}" alt="{html.escape(label)}" loading="lazy"></div>
      <figcaption>
        <div class="label">{html.escape(label)}</div>
        {source_html}
        <ul class="meta">{''.join(f'<li>{html.escape(m)}</li>' for m in meta)}</ul>
        {f'<p class="note">{html.escape(note)}</p>' if note else ''}
      </figcaption>
    </figure>""")
    empty = ('    <p class="empty">还没有来源。用 --url 采集网址，或 --image 加入本地参考图。</p>'
             if not cards else "")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 28px; background: #14151a; color: #e8e8ea;
    font: 15px/1.6 -apple-system, "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif; }}
  header {{ max-width: 1400px; margin: 0 auto 24px; }}
  h1 {{ margin: 0 0 6px; font-size: 22px; letter-spacing: .2px; }}
  .sub {{ color: #9aa0aa; font-size: 13px; }}
  .board {{ max-width: 1400px; margin: 0 auto; display: grid; gap: 18px;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }}
  .card {{ margin: 0; background: #1c1d24; border: 1px solid #2a2c35; border-radius: 12px;
    overflow: hidden; display: flex; flex-direction: column; }}
  .shot {{ position: relative; background: #0e0f13; display: flex; align-items: flex-start;
    justify-content: center; max-height: 620px; overflow: hidden; }}
  .shot img {{ display: block; width: 100%; height: auto; }}
  .no {{ position: absolute; top: 8px; left: 8px; padding: 2px 7px; border-radius: 999px;
    background: rgba(0,0,0,.66); color: #fff; font-size: 12px; font-variant-numeric: tabular-nums; }}
  figcaption {{ padding: 12px 14px 14px; display: grid; gap: 6px; }}
  .label {{ font-weight: 600; }}
  .src {{ font-size: 12px; color: #8fb4ff; word-break: break-all; }}
  .open {{ justify-self: start; min-height: 48px; display: inline-flex; align-items: center;
    padding: 0 14px; border: 1px solid #3a3d48; border-radius: 8px; color: #cfd6e4;
    text-decoration: none; font-size: 13px; }}
  .open:hover {{ border-color: #6f7890; }}
  .meta {{ margin: 4px 0 0; padding-left: 16px; color: #9aa0aa; font-size: 12px; }}
  .note {{ margin: 4px 0 0; font-size: 12px; color: #c8cbd2; }}
  .empty {{ max-width: 1400px; margin: 0 auto; color: #9aa0aa; }}
  footer {{ max-width: 1400px; margin: 28px auto 0; padding-top: 16px; border-top: 1px solid #2a2c35;
    color: #9aa0aa; font-size: 12px; }}
  footer b {{ color: #e8e8ea; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="sub">真实参考像素 · {len(entries)} 个来源 · 生成于 {html.escape(created)}</div>
</header>
<main class="board">
{''.join(cards)}
{empty}
</main>
<footer>
  <b>这块板是参考，不是成品。</b>拆的是方法——网格栏数、字号比例、主色占比、图文关系、母题——
  不搬别人的标识、字体版权与独有插画。规则沉淀写进设计记录，不写进这里。
</footer>
</body>
</html>
"""


def collect(args) -> tuple[list[dict], list[str]]:
    out_dir = os.path.abspath(args.out)
    shots_dir = os.path.join(out_dir, "shots")
    os.makedirs(shots_dir, exist_ok=True)

    chrome = None
    if args.urls:
        if args.no_capture:
            raise RefBoardError("--no-capture 不能与 --url 一起用：网址只能靠截图采集")
        chrome = find_chrome(args.chrome)
        if not chrome:
            raise RefBoardError(
                "找不到 Chrome/Chromium，无法给网址截图。"
                "用 --chrome 指定路径，或先手动截图再用 --image 加入；不要声称已采集。"
            )

    entries: list[dict] = []
    errors: list[str] = []

    for i, url in enumerate(args.urls, 1):
        shot = os.path.join(shots_dir, f"url-{i:02d}.png")
        try:
            info = capture_url(url, shot, chrome, args.width, args.height, args.full)
        except RefBoardError as exc:
            errors.append(str(exc))
            continue
        entry = {
            "kind": "url",
            "source": url,
            "label": args.labels[i - 1] if args.labels and len(args.labels) >= i and args.labels[i - 1] else url,
            "shot": shot,
            "rel_shot": os.path.relpath(shot, out_dir),
            "title": info.get("title", ""),
            "blockers": info.get("blockers", []),
        }
        entry.update(_blank_fields(shot))
        entries.append(entry)

    for j, image in enumerate(args.images, 1):
        src = os.path.abspath(image)
        if not os.path.isfile(src):
            errors.append(f"本地参考图不存在：{image}")
            continue
        ext = os.path.splitext(src)[1].lower() or ".png"
        dest = os.path.join(shots_dir, f"local-{j:02d}{ext}")
        shutil.copyfile(src, dest)
        entry = {
            "kind": "image",
            "source": image,
            "label": os.path.basename(image),
            "shot": dest,
            "rel_shot": os.path.relpath(dest, out_dir),
            "title": "",
            "blockers": [],
        }
        entry.update(_blank_fields(dest))
        entries.append(entry)

    return entries, errors


def _blank_fields(path: str) -> dict:
    info = detect_blank(path)
    return {"blank": info.get("blank"), "blank_reason": info.get("reason")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="采集真实参考像素并生成看板（chrome 通路复用 check-ui.mjs）",
    )
    parser.add_argument("--out", required=True, help="输出目录（会写入 shots/、board.html）")
    parser.add_argument("--url", dest="urls", action="append", default=[], help="参考网址，可多次")
    parser.add_argument("--image", dest="images", action="append", default=[], help="本地参考图，可多次")
    parser.add_argument("--label", dest="labels", action="append", default=[],
                        help="按 --url 顺序给标签（可选）")
    parser.add_argument("--note", action="append", default=[], help="给整块板加一条备注（可多次）")
    parser.add_argument("--title", default="参考板 Reference Board", help="看板标题")
    parser.add_argument("--width", type=int, default=1280, help="视口宽（默认 1280）")
    parser.add_argument("--height", type=int, default=900, help="视口高（默认 900）")
    parser.add_argument("--full", action="store_true", help="截整页（默认只截首屏）")
    parser.add_argument("--chrome", default=None, help="Chrome/Chromium 路径")
    parser.add_argument("--no-capture", action="store_true", help="只用现有本地图，不启动浏览器")
    args = parser.parse_args(argv)

    if not args.urls and not args.images:
        parser.error("至少要给一个 --url 或 --image")
    if args.labels and args.images and not args.urls:
        parser.error("--label 只对应 --url；本地图用文件名作标签")

    try:
        entries, errors = collect(args)
    except RefBoardError as exc:
        print(f"ref_board: {exc}", file=sys.stderr)
        return 2

    out_dir = os.path.abspath(args.out)
    if not entries:
        print("ref_board: 没有任何来源采集成功，未生成看板。", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    created = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    board_html = os.path.join(out_dir, "board.html")
    with open(board_html, "w", encoding="utf-8") as fh:
        fh.write(build_board_html(entries, args.title, created))

    sheet = compose_sheet(entries, os.path.join(out_dir, "board.jpg"))

    manifest = {
        "title": args.title,
        "created": created,
        "notes": args.note,
        "entries": [{k: v for k, v in e.items() if k != "shot"} | {"shot": e.get("rel_shot")}
                    for e in entries],
        "errors": errors,
        "sheet": sheet,
        "pillow": Image is not None,
    }
    with open(os.path.join(out_dir, "board.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    blank = [e for e in entries if e.get("blank") is True]
    print(f"ref_board: {len(entries)} 个来源 → {board_html}")
    if sheet.get("ok"):
        print(f"ref_board: 拼图 → {sheet['path']}")
    else:
        print(f"ref_board: 未生成 board.jpg（{sheet.get('reason')}）")
    if blank:
        print("ref_board: ⚠ 疑似空白截图（可能没渲染出来，需人工确认）："
              + "、".join(e.get("label") or e.get("source", "") for e in blank), file=sys.stderr)
    for err in errors:
        print(f"ref_board: 失败来源 → {err}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
