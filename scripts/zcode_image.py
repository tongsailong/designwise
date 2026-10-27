#!/usr/bin/env python3
"""zcode_image.py — ZCode 宿主的真实图像生成适配器

为什么有它：本 skill 原本依赖 `huashu-gpt-image` 的方法论走 CPA 生图。ZCode 侧现在
装了 `huashu-gpt-image` skill（方法论与提示词规则），但实际出图仍需一条稳定的脚本通路：
ZCode 自己配置的 CPA 代理已经暴露 `gpt-image-*` 模型。这个脚本把那条通路
收窄成一条命令，只做一件事：**真的调用图像接口，拿回真的 PNG 字节**。

它不搜索图片、不写提示词交差、不用占位图——拿不到图就非零退出并说明原因。

用法：
    python3 scripts/zcode_image.py --health
    python3 scripts/zcode_image.py --prompt "..." --out out.png
    python3 scripts/zcode_image.py --prompt "..." --out out.png --ref base.png --size 1536x1024 [--fit cover|contain|stretch]
    python3 scripts/zcode_image.py --prompt "..." --out a.png --n 2   # 输出 a-1.png a-2.png

退出码：0 = 拿到真实图片；2 = 本机无可用图像模型；1 = 调用失败。
凭据只从 ZCode provider 配置或 ZCODE_CPA_BASE_URL / ZCODE_CPA_API_KEY 读取，
不打印、不落盘。
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

CONFIG = os.path.expanduser(
    os.environ.get("ZCODE_PROVIDER_CONFIG", "~/.zcode/v2/provider_config.json"))
DEFAULT_MODEL = "gpt-image-2.5"
MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
}
MIME = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


class ConfigError(RuntimeError):
    """provider 配置缺失或不可读；消息里不出现密钥。"""


class ImageOutputError(RuntimeError):
    """上游返回的图片数据不完整或不符合契约。"""


def load_endpoint():
    """返回 (baseUrl, apiKey)。

    宿主无关的覆盖方式：同时设置 ZCODE_CPA_BASE_URL / ZCODE_CPA_API_KEY 即可，
    不要求存在 ~/.zcode 配置。两者都没设置时才回落到 ZCode provider 配置。
    """
    env_base = os.environ.get("ZCODE_CPA_BASE_URL", "").strip()
    env_key = os.environ.get("ZCODE_CPA_API_KEY", "").strip()
    if env_base and env_key:
        return env_base.rstrip("/"), env_key
    config = os.path.expanduser(os.environ.get("ZCODE_PROVIDER_CONFIG", CONFIG))
    try:
        with open(config, "r", encoding="utf-8") as f:
            cfg = json.load(f)["config"]
        for pr in cfg["providerConfigRules"]["providerRules"]:
            c = pr.get("config") or {}
            base = ((c.get("api") or {}).get("baseUrl") or "").rstrip("/")
            key = ((c.get("access") or {}).get("apiKey") or "").strip()
            if base and key and ("8317" in base or "cpa" in json.dumps(pr).lower()):
                return base, key
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"无法读取 provider 配置：{config}（{type(exc).__name__}）") from exc
    raise ConfigError(
        "找不到可用的 CPA provider 配置；可设置 ZCODE_CPA_BASE_URL / "
        f"ZCODE_CPA_API_KEY，或提供 {config}")


def post(url, key, payload, timeout):
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        data=json.dumps(payload).encode(),
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get_models(base, key):
    req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [m.get("id", "") for m in json.loads(r.read()).get("data", [])]


def health():
    try:
        base, key = load_endpoint()
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 2
    try:
        models = get_models(base, key)
    except Exception as e:
        print(f"❌ 无法列出模型：{type(e).__name__}")
        return 2
    image_models = sorted(m for m in models if "image" in m)
    if not image_models:
        print("❌ 接口可达，但没有 image 模型")
        return 2
    print("✅ 图片接口可用（零成本检查，未生成图片）")
    print("   可用模型：" + "、".join(image_models))
    return 0


def sniff(raw):
    for magic, kind in MAGIC.items():
        if raw.startswith(magic):
            return kind
    # RIFF 容器不止 WebP（WAVE/AVI 也用它）；必须再核对 WEBP 标识与 VP8 块。
    if len(raw) >= 16 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" \
            and raw[12:16] in (b"VP8 ", b"VP8L", b"VP8X"):
        return "webp"
    return None


def image_complete(raw, kind):
    """只凭魔数不足以证明「完整图片」；这里再加一个廉价的尾部/长度结构检查。"""
    if kind == "png":
        return raw.rstrip(b"\x00")[-12:].find(b"IEND") >= 0
    if kind == "jpeg":
        return raw.rstrip(b"\x00").endswith(b"\xff\xd9")
    if kind == "webp":
        if len(raw) < 12:
            return False
        size = int.from_bytes(raw[4:8], "little")
        return len(raw) >= size + 8
    return False


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 尺寸适配
# 参考实现：huashu-gpt-image 的 gen_via_cpa.py（fit_to_size / _ratio_hint）。
# CPA 实测不遵守 size 参数，最终像素只能由本地 Pillow 保证；比例诉求靠 hint
# 写进 prompt 让模型自选画布时贴近目标比例，这里的裁剪量就是模型没听话的代价。

class FitError(RuntimeError):
    """尺寸适配失败：调用方必须明确报错，不得带着错误尺寸的文件继续。"""


def _parse_size(size):
    if not size:
        return None
    m = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", size)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    return (w, h) if w > 0 and h > 0 else None


def _ratio_hint(size):
    """把目标尺寸翻成一句写给模型的构图约束（语义与参考实现一致）。"""
    t = _parse_size(size)
    if not t:
        return ""
    w, h = t
    g = math.gcd(w, h)
    rw, rh = w // g, h // g
    ratio = f"{rw}:{rh}" if max(rw, rh) <= 40 else f"{w / h:.2f}:1"
    orient = "横构图" if w > h else ("竖构图" if h > w else "方形构图")
    return (f"构图约束：按 {ratio} 的目标宽高比做{orient}，主体居中、四周留出安全边距，"
            f"不要贴边（成图会再适配到 {size}）。")


def fit_to_size(path, size, mode):
    """把已写盘的图片适配到目标像素。返回一句说明；失败抛 FitError。

    cover   = 等比铺满后居中裁剪（满幅无留白，裁掉超出的一边）
    contain = 完整保留内容，短边方向留白（不裁内容，留白区为透明，落盘为
              不支持透明的格式时合成到白底）
    stretch = 直接拉伸到目标尺寸（会变形）
    """
    target = _parse_size(size)
    if not target:
        raise FitError(f"无效的目标尺寸：{size!r}")
    try:
        from PIL import Image
    except ImportError as e:
        raise FitError("未安装 Pillow，无法保证精确输出尺寸（本脚本不做无尺寸保证的输出）") from e
    tw, th = target
    if tw < 1 or th < 1:
        raise FitError(f"目标尺寸无效：{tw}x{th}")
    try:
        with Image.open(path) as im:
            src = im.size
            if src == (tw, th):
                return f"尺寸对齐：模型原始就是 {src[0]}x{src[1]}，无需适配"
            if mode == "stretch":
                out = im.convert("RGBA").resize((tw, th), Image.LANCZOS)
                nw, nh = tw, th
            elif mode == "contain":
                scale = min(tw / src[0], th / src[1])
                nw, nh = max(1, round(src[0] * scale)), max(1, round(src[1] * scale))
                resized = im.convert("RGBA").resize((nw, nh), Image.LANCZOS)
                out = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
                out.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
            else:  # cover：等比放大到铺满，再居中裁剪
                scale = max(tw / src[0], th / src[1])
                nw, nh = max(tw, round(src[0] * scale)), max(th, round(src[1] * scale))
                resized = im.convert("RGBA").resize((nw, nh), Image.LANCZOS)
                left, top = (nw - tw) // 2, (nh - th) // 2
                out = resized.crop((left, top, left + tw, top + th))
            try:
                out.save(path)
            except OSError:
                # 目标格式存不下 alpha（如 JPEG）：合成到白底再存，留白语义不变
                bg = Image.new("RGB", out.size, (255, 255, 255))
                bg.paste(out, mask=out.split()[3])
                bg.save(path)
    except FitError:
        raise
    except Exception as e:
        raise FitError(f"图片适配失败（{type(e).__name__}）：{e}") from e

    # 最终宽高必须严格一致，不能靠「应该对了」
    try:
        with Image.open(path) as chk:
            if chk.size != (tw, th):
                raise FitError(f"适配后尺寸不符：得到 {chk.size[0]}x{chk.size[1]}，要求 {tw}x{th}")
    except FitError:
        raise
    except Exception as e:
        raise FitError(f"适配结果回读校验失败（{type(e).__name__}）：{e}") from e

    note = (f"模型产出 {src[0]}x{src[1]}（{src[0] / src[1]:.2f}:1）→ Pillow 适配到 {tw}x{th}（{tw / th:.2f}:1）")
    if mode == "stretch":
        return note + "；⚠️ stretch 是直接拉伸，原图比例与目标不一致时会变形"
    if mode == "contain":
        kept = (nw * nh) / (tw * th)
        if kept < 0.99:
            return note + f"；{'左右' if nw < tw else '上下'}留白 {1 - kept:.0%}（内容完整保留，未被裁）"
        return note
    if nw > tw:
        cut, axis = (nw - tw) / nw, "左右"
    elif nh > th:
        cut, axis = (nh - th) / nh, "上下"
    else:
        return note
    if cut <= 0.02:
        return note
    if cut >= 0.25:
        return (note + f"；🔴 {axis}裁掉 {cut:.0%}（只留原图 {1 - cut:.0%}）——主体贴边就会被切，"
                       f"建议改 --fit contain、把目标比例改得接近模型画布，或靠比例约束重出")
    if cut >= 0.08:
        return note + f"；注意{axis}裁掉 {cut:.0%}，关键信息别贴边"
    return note + f"；{axis}裁掉 {cut:.0%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt")
    ap.add_argument("--out")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--size", default=None, help="如 1536x1024；CPA 可能忽略，最终尺寸由本地 Pillow 适配保证")
    ap.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover",
                    help="尺寸适配模式：cover 居中裁剪（默认）/ contain 留白完整保留 / stretch 直接拉伸")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--ref", action="append", default=[], help="参考图路径（走 /images/edits）")
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    if a.health:
        return health()
    if not a.prompt or not a.out:
        ap.error("需要 --prompt 和 --out")

    target = _parse_size(a.size)
    if a.size and target is None:
        print(f"❌ 无效的目标尺寸：{a.size!r}（应为宽x高，如 1536x1024）")
        return 1
    hint = _ratio_hint(a.size)
    prompt = f"{a.prompt}\n{hint}" if hint else a.prompt
    # 精确尺寸依赖 Pillow：本地可预知的条件必须在发请求前检查，不能等出图后才失败。
    if target and importlib.util.find_spec("PIL") is None:
        print("❌ 指定了 --size 但未安装 Pillow；无法保证精确尺寸，未发起生成请求")
        return 1

    try:
        base, key = load_endpoint()
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 2
    if a.n > 4:
        print("⚠️ --n 上限为 4，按 4 处理")
    n = max(1, min(int(a.n), 4))

    refs = []
    for p in a.ref:
        p = os.path.abspath(os.path.expanduser(p))
        if not os.path.isfile(p):
            print(f"❌ 参考图不存在：{p}")
            return 1
        try:
            with open(p, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"❌ 参考图读取失败：{p}（{type(exc).__name__}）")
            return 1
        kind = sniff(raw)
        if not kind or not image_complete(raw, kind):
            print(f"❌ 参考图不是完整图片：{p}")
            return 1
        refs.append((p, raw, kind))
        print(f"参考图 {p} · {kind} · {len(raw)} B · sha256 {hashlib.sha256(raw).hexdigest()[:16]}")

    try:
        if refs:
            payload = {
                "model": a.model,
                "prompt": prompt,
                "n": n,
                "images": [
                    {"image_url": f"data:{MIME[kind]};base64," + base64.b64encode(r).decode()}
                    for _, r, kind in refs
                ],
            }
            data = post(base + "/images/edits", key, payload, a.timeout)
        else:
            payload = {"model": a.model, "prompt": prompt, "n": n}
            if a.size:
                payload["size"] = a.size
            data = post(base + "/images/generations", key, payload, a.timeout)
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        print(f"❌ HTTP {e.code}：{body}")
        return 1
    except Exception as e:
        print(f"❌ {type(e).__name__}：{str(e)[:200]}")
        return 1

    if not isinstance(data, dict):
        print("❌ 响应不是 JSON 对象（接口未真正返回图片数据）")
        return 1
    items = data.get("data")
    if not isinstance(items, list) or not items:
        print("❌ 响应里没有图片数据（接口未真正出图）")
        return 1
    if len(items) < n:
        print(f"❌ 只返回 {len(items)}/{n} 张图片，结果不完整")
        return 1
    items = items[:n]

    stem, ext = os.path.splitext(a.out)
    multi = n > 1
    pending = []
    try:
        # 两阶段：先把每个结果写临时文件、适配并校验；全部通过后才替换目标。
        # 任何一项失败都不会留下半批新文件，也不会覆盖既有输出。
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                raise ImageOutputError(f"第 {i + 1} 项不是对象")
            b64 = it.get("b64_json")
            if not b64 or not isinstance(b64, str):
                raise ImageOutputError(
                    f"第 {i + 1} 项只有 URL 没有 b64_json（请用 --out 要求 b64）")
            try:
                raw = base64.b64decode(b64)
            except Exception as exc:
                raise ImageOutputError(
                    f"第 {i + 1} 项 base64 解码失败（{type(exc).__name__}）") from exc
            kind = sniff(raw)
            if not kind or not image_complete(raw, kind):
                raise ImageOutputError(
                    f"第 {i + 1} 项解码后不是完整图片（前 8 字节 {raw[:8]!r}）")
            out = f"{stem}-{i + 1}{ext}" if multi else a.out
            out_dir = os.path.dirname(os.path.abspath(out)) or "."
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as exc:
                raise ImageOutputError(
                    f"无法创建输出目录 {out_dir}（{type(exc).__name__}）") from exc
            fd, tmp = tempfile.mkstemp(prefix=".zcode-image-", suffix=ext or ".img",
                                       dir=out_dir)
            pending.append((out, tmp, "", None))
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            note = fit_to_size(tmp, a.size, a.fit) if target else ""
            # 最终落盘文件必须仍是完整受支持图片。
            with open(tmp, "rb") as fh:
                final_raw = fh.read()
            final_kind = sniff(final_raw)
            if not final_kind or not image_complete(final_raw, final_kind):
                raise FitError("最终文件不是完整受支持图片")
            pending[-1] = (out, tmp, note, final_kind)
        # 预检全部目标：目录/不可写父目录必须在任何替换之前失败。
        for out, _tmp, _note, _kind in pending:
            if os.path.isdir(out):
                raise ImageOutputError(f"输出路径是目录，拒绝覆盖：{out}")
            out_dir = os.path.dirname(os.path.abspath(out)) or "."
            if not os.access(out_dir, os.W_OK):
                raise ImageOutputError(f"输出目录不可写：{out_dir}")
    except (ImageOutputError, FitError, OSError) as exc:
        for _, tmp, _, _ in pending:
            try:
                os.remove(tmp)
            except OSError:
                pass
        print(f"❌ {exc}（未写入或覆盖任何输出）")
        return 1

    backups = []   # (out, backup) for files that existed before this run
    replaced = []  # outputs successfully replaced
    try:
        for out, tmp, note, final_kind in pending:
            if os.path.exists(out):
                out_dir = os.path.dirname(os.path.abspath(out)) or "."
                fd, backup = tempfile.mkstemp(prefix=".zcode-backup-", dir=out_dir)
                os.close(fd)
                os.remove(backup)
                try:
                    os.replace(out, backup)
                except OSError:
                    try:
                        os.remove(backup)
                    except OSError:
                        pass
                    raise
                backups.append((out, backup))
            os.replace(tmp, out)
            replaced.append(out)
            print(f"✅ {out} · {final_kind} · {os.path.getsize(out)} B · "
                  f"sha256 {sha256_file(out)[:16]} · model {a.model}")
            if note:
                print(f"   {note}")
    except OSError as exc:
        # 中途失败：删除已替换的新文件，恢复原有文件，再清理剩余临时文件。
        for out in replaced:
            try:
                os.remove(out)
            except OSError:
                pass
        for out, backup in backups:
            try:
                os.replace(backup, out)
            except OSError:
                pass
        for _, tmp, _, _ in pending:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        print(f"❌ 写入输出失败（{type(exc).__name__}）：{exc}（已尝试回滚）")
        return 1

    for _, backup in backups:
        try:
            os.remove(backup)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
