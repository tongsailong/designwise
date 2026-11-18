#!/usr/bin/env python3
"""zcode_image.py — ZCode 宿主的真实图像生成适配器

为什么有它：生图方法论已并入本 skill（见 `references/image-generation.md`），不依赖任何
外部生图 skill。ZCode 自己配置的 CPA 代理已暴露 `gpt-image-*` 模型，这个脚本把那条通路
收窄成一条命令，只做一件事：**真的调用图像接口，拿回真的 PNG 字节**。

它不搜索图片、不写提示词交差、不用占位图——拿不到图就非零退出并说明原因。

用法：
    python3 scripts/zcode_image.py --health
    python3 scripts/zcode_image.py --prompt "..." --out out.png
    python3 scripts/zcode_image.py --prompt "..." --out out.webp --profile premium \
      --size 1024x1536 --fit cover --output-format webp --compression 82 \
      --meta-out out.meta.json
    python3 scripts/zcode_image.py --prompt "..." --out out.png --ref base.png --size 1536x1024 [--fit cover|contain|stretch]
    python3 scripts/zcode_image.py --prompt "..." --out a.png --n 2   # 输出 a-1.png a-2.png

模型路由（默认 final = gpt-image-2.6-sunburst / high / high）：
    final     Sunburst  high    high    正式素材默认
    premium   Sunburst  high    xhigh   核心主题插画/首页主视觉
    max       Sunburst  high    max     少量最高优先级资产
    explore   Flare     medium  medium  快速探索/多方案初稿
    draft     Flare     low     low     低成本构图验证
`--model` / `--complexity` / `--quality` 可逐项覆盖；脚本不会在失败时静默回退到旧模型。

退出码：0 = 拿到真实图片；2 = 本机无可用图像模型或默认 2.6 模型缺失；1 = 调用失败。
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
import time
import urllib.error
import urllib.request
from datetime import datetime

CONFIG = os.path.expanduser(
    os.environ.get("ZCODE_PROVIDER_CONFIG", "~/.zcode/v2/provider_config.json"))

# GPT-Image-2.6 把「生成前规划」与「像素渲染质量」拆成两个参数：
# complexity 控制规划算力（默认 high），quality 控制渲染细节。两者不能混用。
PROFILES = {
    "final": {"model": "gpt-image-2.6-sunburst", "complexity": "high", "quality": "high",
              "purpose": "正式素材默认：常规插画、场景与重要页面素材"},
    "premium": {"model": "gpt-image-2.6-sunburst", "complexity": "high", "quality": "xhigh",
                "purpose": "精品素材：核心主题插画、首页主视觉、精细编辑"},
    "max": {"model": "gpt-image-2.6-sunburst", "complexity": "high", "quality": "max",
            "purpose": "少量最高优先级精品资产"},
    "explore": {"model": "gpt-image-2.6-flare", "complexity": "medium", "quality": "medium",
                "purpose": "快速探索、多方案初稿、普通素材尝试"},
    "draft": {"model": "gpt-image-2.6-flare", "complexity": "low", "quality": "low",
              "purpose": "低成本构图验证与快速迭代"},
}
DEFAULT_PROFILE = "final"
DEFAULT_MODEL = PROFILES[DEFAULT_PROFILE]["model"]
COMPLEXITY_VALUES = ("low", "medium", "high")
QUALITY_VALUES = ("auto", "low", "medium", "high", "xhigh", "max")
OUTPUT_FORMATS = ("png", "jpeg", "webp")
BACKGROUND_VALUES = ("auto", "opaque", "transparent")
IMAGE_26_PREFIX = "gpt-image-2.6"
EXT_BY_FORMAT = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}
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
    print("   默认 final：" + DEFAULT_MODEL + "（Sunburst / complexity=high / quality=high）")
    if DEFAULT_MODEL not in image_models:
        print(f"❌ 默认模型 {DEFAULT_MODEL} 不在可用列表；本脚本不会静默降级到旧模型")
        print("   可用模型：" + "、".join(image_models))
        return 2
    if PROFILES["explore"]["model"] not in image_models:
        print(f"   ⚠️ 快速探索模型 {PROFILES['explore']['model']} 不在可用列表；"
              "explore/draft 档不可用")
    models_26 = [m for m in image_models if m.startswith(IMAGE_26_PREFIX)]
    print("   可用 2.6 模型：" + ("、".join(models_26) if models_26 else "无"))
    print("   全部 image 模型：" + "、".join(image_models))
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


def size_error(size):
    """官方尺寸约束：宽高为 16 的倍数，宽高比 1:3–3:1。返回错误说明或 None。"""
    t = _parse_size(size)
    if not t:
        return f"无效的目标尺寸：{size!r}（应为宽x高，如 1024x1536）"
    w, h = t
    if w % 16 or h % 16:
        return f"尺寸 {w}x{h} 不符合官方约束：宽高都必须是 16 的倍数"
    if not (1 / 3 <= w / h <= 3):
        return f"尺寸 {w}x{h} 不符合官方约束：宽高比必须在 1:3 到 3:1 之间"
    return None


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


def convert_format(path, fmt, compression=None):
    """把已写盘图片转成目标格式（Pillow）。返回说明；失败抛 FitError。

    Image API 的 output_format 在当前 CPA 网关会被规范化成 PNG，所以最终格式
    必须由本地保证；JPEG/WebP 的 output_compression 同样在这里落地。
    """
    if fmt not in OUTPUT_FORMATS:
        raise FitError(f"不支持的输出格式：{fmt!r}")
    try:
        from PIL import Image
    except ImportError as e:
        raise FitError("未安装 Pillow，无法转换输出格式") from e
    try:
        with Image.open(path) as im:
            src = (im.format or "").lower()
            if src == fmt and not (fmt in ("jpeg", "webp") and compression is not None):
                return ""
            if fmt == "jpeg":
                out = im.convert("RGB")
            elif im.mode in ("RGBA", "LA") or "transparency" in im.info:
                out = im.convert("RGBA")
            else:
                out = im.convert("RGB")
            kwargs = {}
            if fmt in ("jpeg", "webp") and compression is not None:
                kwargs["quality"] = compression
            if fmt == "jpeg":
                kwargs["optimize"] = True
            elif fmt == "webp":
                kwargs["method"] = 6
            target_format = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[fmt]
            out_dir = os.path.dirname(os.path.abspath(path)) or "."
            fd, tmp = tempfile.mkstemp(prefix=".zcode-convert-",
                                       suffix=EXT_BY_FORMAT[fmt], dir=out_dir)
            os.close(fd)
            try:
                out.save(tmp, format=target_format, **kwargs)
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
    except FitError:
        raise
    except Exception as e:
        raise FitError(f"格式转换失败（{type(e).__name__}）：{e}") from e
    note = f"{src or '未知'}→{fmt}"
    if fmt in ("jpeg", "webp") and compression is not None:
        note += f"（压缩 {compression}）"
    return note


def image_info(path):
    """回读最终文件的真实格式/尺寸/字节数；失败抛 FitError。"""
    try:
        from PIL import Image
    except ImportError as e:
        raise FitError("未安装 Pillow，无法回读图片信息") from e
    try:
        with Image.open(path) as im:
            return {
                "width": im.width,
                "height": im.height,
                "format": (im.format or "").lower(),
                "mode": im.mode,
                "has_alpha": (im.mode in ("RGBA", "LA", "PA")
                              or (im.mode == "P" and "transparency" in im.info)),
                "bytes": os.path.getsize(path),
            }
    except Exception as e:
        raise FitError(f"回读图片信息失败（{type(e).__name__}）：{e}") from e


def write_meta(path, meta):
    """原子写入生成元数据 JSON；不包含 prompt 正文或任何凭据。"""
    path = os.path.abspath(path)
    out_dir = os.path.dirname(path) or "."
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".zcode-meta-", suffix=".json", dir=out_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt")
    ap.add_argument("--out")
    ap.add_argument("--profile", choices=sorted(PROFILES), default=DEFAULT_PROFILE,
                    help="模型/参数路由档位（默认 final = 2.6 Sunburst high/high）")
    ap.add_argument("--model", default=None,
                    help=f"覆盖模型；默认取 profile（正式默认 {DEFAULT_MODEL}）")
    ap.add_argument("--complexity", choices=COMPLEXITY_VALUES, default=None,
                    help="覆盖 complexity（2.6 默认 high）")
    ap.add_argument("--quality", choices=QUALITY_VALUES, default=None,
                    help="覆盖 quality（默认 high；精品可用 xhigh/max）")
    ap.add_argument("--output-format", choices=OUTPUT_FORMATS, default="png",
                    help="最终文件格式（默认 png；普通素材建议 webp）")
    ap.add_argument("--compression", type=int, default=None,
                    help="JPEG/WebP 压缩质量 0-100；PNG 不支持")
    ap.add_argument("--background", choices=BACKGROUND_VALUES, default=None,
                    help="背景：auto / opaque / transparent（透明需回读 alpha 验证）")
    ap.add_argument("--meta-out", default=None,
                    help="把请求参数与产物元数据写成 JSON（不含 prompt 正文与凭据）")
    ap.add_argument("--size", default=None, help="如 1536x1024；网关可能只近似遵守，最终尺寸由本地 Pillow 保证")
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

    profile = PROFILES[a.profile]
    model = a.model or profile["model"]
    complexity = a.complexity if a.complexity is not None else profile["complexity"]
    quality = a.quality if a.quality is not None else profile["quality"]
    fmt = a.output_format
    compression = a.compression

    if compression is not None and not (0 <= compression <= 100):
        print("❌ --compression 必须在 0-100 之间")
        return 1
    if compression is not None and fmt not in ("jpeg", "webp"):
        print("❌ PNG 不支持 output_compression；请改用 --output-format webp 或 jpeg")
        return 1
    if a.background == "transparent" and fmt == "jpeg":
        print("❌ JPEG 不支持透明背景；请改用 --output-format png 或 webp")
        return 1
    if not model.startswith(IMAGE_26_PREFIX):
        print(f"⚠️ 显式使用非 2.6 模型 {model}；脚本不会自动回退，但该模型不在默认路由内")
        if a.complexity is not None:
            print("   ⚠️ 该模型未声明 complexity 参数，已忽略 --complexity")
            complexity = None

    stem, ext = os.path.splitext(a.out)
    if not ext:
        a.out = a.out + EXT_BY_FORMAT[fmt]
        stem, ext = os.path.splitext(a.out)
    ext_formats = {".png": {"png"}, ".jpg": {"jpeg"}, ".jpeg": {"jpeg"}, ".webp": {"webp"}}
    if fmt not in ext_formats.get(ext.lower(), set()):
        print(f"❌ 输出扩展名 {ext} 与 --output-format {fmt} 不一致；请对齐后重试")
        return 1

    if a.size:
        err = size_error(a.size)
        if err:
            print(f"❌ {err}")
            return 1
    target = _parse_size(a.size)
    hint = _ratio_hint(a.size)
    prompt = f"{a.prompt}\n{hint}" if hint else a.prompt
    # 精确尺寸、格式转换与元数据回读都依赖 Pillow：本地可预知的条件必须在发请求前检查。
    if importlib.util.find_spec("PIL") is None:
        need = []
        if target:
            need.append("--size 的精确尺寸")
        if fmt != "png":
            need.append(f"--output-format {fmt} 的格式转换")
        if a.meta_out:
            need.append("--meta-out 的产物回读")
        if need:
            print("❌ 未安装 Pillow，无法保证" + "、".join(need) + "；未发起生成请求")
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

    endpoint = "/images/edits" if refs else "/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "quality": quality,
        "output_format": fmt,
    }
    if complexity:
        payload["complexity"] = complexity
    if a.size:
        payload["size"] = a.size
    if a.background:
        payload["background"] = a.background
    if compression is not None:
        payload["output_compression"] = compression
    if refs:
        payload["images"] = [
            {"image_url": f"data:{MIME[kind]};base64," + base64.b64encode(r).decode()}
            for _, r, kind in refs
        ]
    print(f"请求：{endpoint} · profile={a.profile} · model={model} · "
          f"complexity={complexity or '-'} · quality={quality} · format={fmt} · "
          f"size={a.size or 'auto'} · background={a.background or 'default'}"
          + (f" · compression={compression}" if compression is not None else ""))
    request_started = time.time()
    try:
        data = post(base + endpoint, key, payload, a.timeout)
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        print(f"❌ HTTP {e.code}：{body}")
        return 1
    except Exception as e:
        print(f"❌ {type(e).__name__}：{str(e)[:200]}")
        return 1
    elapsed_s = round(time.time() - request_started, 2)

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
    response_meta = {k: data.get(k) for k in
                     ("created", "size", "quality", "background", "output_format", "usage")
                     if k in data}
    response_meta["complexity_echoed"] = "complexity" in data
    if response_meta.get("quality") and response_meta["quality"] != quality:
        response_meta["quality_echo_mismatch"] = True
        print(f"⚠️ 网关响应 quality={response_meta['quality']} 与请求 {quality} 不一致；"
              "响应字段不能作为生效质量证据，以实际产物与视觉验收为准")
    try:
        # 两阶段：先把每个结果写临时文件、适配/转格式并校验；全部通过后才替换目标。
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
            fd, tmp = tempfile.mkstemp(prefix=".zcode-image-",
                                       suffix=EXT_BY_FORMAT.get(kind, ".img"), dir=out_dir)
            pending.append((out, tmp, [], None, None))
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            notes = []
            source_info = image_info(tmp) if a.meta_out else None
            if target:
                notes.append(fit_to_size(tmp, a.size, a.fit))
            with open(tmp, "rb") as fh:
                current_raw = fh.read()
            current_kind = sniff(current_raw)
            if current_kind != fmt or (fmt in ("jpeg", "webp") and compression is not None):
                note = convert_format(tmp, fmt, compression)
                if note:
                    notes.append(note + "（本地 Pillow 规范化）")
            # 最终落盘文件必须是目标格式、完整、且尺寸严格等于请求值。
            with open(tmp, "rb") as fh:
                final_raw = fh.read()
            final_kind = sniff(final_raw)
            if not final_kind or not image_complete(final_raw, final_kind):
                raise FitError("最终文件不是完整受支持图片")
            if final_kind != fmt:
                raise FitError(f"最终格式 {final_kind} 与请求的 {fmt} 不一致")
            info = image_info(tmp) if (target or a.meta_out
                                       or a.background == "transparent") else None
            if target and (info["width"], info["height"]) != target:
                raise FitError(
                    f"最终尺寸 {info['width']}x{info['height']} 与请求的 {a.size} 不一致")
            if a.background == "transparent" and not info.get("has_alpha"):
                raise FitError("请求了 transparent 背景，但产物没有 alpha 通道；"
                               "不得把不透明图当作透明素材交付（可改用纯色幕布 + chroma_key）")
            asset_meta = None
            if a.meta_out:
                clean_notes = [n for n in notes if n]
                asset_meta = {
                    "file": out,
                    "sha256": sha256_file(tmp),
                    "bytes": info["bytes"],
                    "width": info["width"],
                    "height": info["height"],
                    "format": info["format"],
                    "mode": info["mode"],
                    "source_format": (source_info or {}).get("format"),
                    "source_width": (source_info or {}).get("width"),
                    "source_height": (source_info or {}).get("height"),
                    "notes": clean_notes,
                }
            pending[-1] = (out, tmp, [n for n in notes if n], final_kind, asset_meta)
        # 预检全部目标：目录/不可写父目录必须在任何替换之前失败。
        for out, _tmp, _notes, _kind, _meta in pending:
            if os.path.isdir(out):
                raise ImageOutputError(f"输出路径是目录，拒绝覆盖：{out}")
            out_dir = os.path.dirname(os.path.abspath(out)) or "."
            if not os.access(out_dir, os.W_OK):
                raise ImageOutputError(f"输出目录不可写：{out_dir}")
    except (ImageOutputError, FitError, OSError) as exc:
        for _, tmp, _, _, _ in pending:
            try:
                os.remove(tmp)
            except OSError:
                pass
        print(f"❌ {exc}（未写入或覆盖任何输出）")
        return 1

    backups = []   # (out, backup) for files that existed before this run
    replaced = []  # outputs successfully replaced
    try:
        for out, tmp, notes, final_kind, asset_meta in pending:
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
                  f"sha256 {sha256_file(out)[:16]} · model {model} · "
                  f"profile {a.profile} · complexity {complexity or '-'} · quality {quality}")
            for note in notes:
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
        for _, tmp, _, _, _ in pending:
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

    if a.meta_out:
        meta = {
            "schema": "designwise-image-meta/v1",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "endpoint": endpoint,
            "elapsed_s": elapsed_s,
            "request": {
                "model": model,
                "profile": a.profile,
                "profile_purpose": profile.get("purpose"),
                "complexity": complexity,
                "quality": quality,
                "size": a.size,
                "fit": a.fit if target else None,
                "output_format": fmt,
                "compression": compression,
                "background": a.background,
                "n": n,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "refs": [{"file": p, "sha256": hashlib.sha256(r).hexdigest()}
                         for p, r, _ in refs],
            },
            "response": response_meta,
            "assets": [m for _, _, _, _, m in pending if m],
        }
        try:
            write_meta(a.meta_out, meta)
        except OSError as exc:
            print(f"❌ 元数据写入失败（{type(exc).__name__}）：{a.meta_out}；图片已写入")
            return 1
        print(f"元数据：{a.meta_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
