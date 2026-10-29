#!/usr/bin/env python3
"""zcode_vision.py — DesignWise 的外部 GPT 视觉评审入口（需用户明确授权）

它是什么：直连 ZCode 自己的 CPA 代理（Responses API 的 `input_image`），把「把真实图片像素
送进评审」收窄成一条命令。它**只接受磁盘上的真实图片**，**可以使用 GPT 模型**
（默认 `gpt-6-astra-high`）。它**不是 Copilot Skill 的正式 REVIEW**（不写台账/审计/轮次限制），
但**同样是外部 GPT 裁决**：只有用户**明确授权 GPT 评审通道**（点名 GPT / GPT 视觉评审 /
Copilot / 正式 REVIEW）时才可调用，且调用方必须传 `--confirm-gpt-review`。
未授权时用 DesignWise 原生视觉自检（主模型直接读真实图片），不得用它绕过 Copilot 的启用限制。

硬约束：只接受磁盘上的真实图片文件。传路径不存在的、传纯文字、传 base64 字符串、
传「请想象一张图」的提示词——一律拒绝并且非零退出。**不拿文字冒充视觉评审。**
响应必须是非空、完整成功的文本：`status` 非 completed、带 error 或带 incomplete_details
一律按失败处理，不把截断文本当成评审结论。失败时如实报告「未获得有效视觉裁决」，
按缺证处理，不伪造 PASS、不静默切换到 Copilot、不自动无限重试。

用法（仅在用户明确授权 GPT 评审通道后）：
    python3 scripts/zcode_vision.py --confirm-gpt-review --image shot.png --prompt "评估这个界面的视觉层级"
    python3 scripts/zcode_vision.py --confirm-gpt-review --image a.png --image b.png --prompt "比较两个方向，给推荐+依据+风险"
    python3 scripts/zcode_vision.py --health          # 零成本探测，不需要授权标志

退出码：0 = 拿到评审结论；2 = 未授权 / 无法送图 / 无视觉模型；1 = 调用失败。
凭据只从 ZCode provider 配置或 ZCODE_CPA_BASE_URL / ZCODE_CPA_API_KEY 读取，
不打印、不落盘。
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

CONFIG = os.path.expanduser(
    os.environ.get("ZCODE_PROVIDER_CONFIG", "~/.zcode/v2/provider_config.json"))
DEFAULT_MODEL = "gpt-6-astra-high"
# 格式按文件头魔数判定，与 copilot/scripts/lib_common.py 的 sniff_image_mime 同一口径
# （png/jpeg/webp/gif）。本脚本是默认视觉评审入口；刻意不 import copilot，保持独立：
# 硬依赖 copilot 目录会让默认路径随另一条通道一起失效；两处白名单需同步维护。
IMAGE_FORMATS = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_image_mime(head: bytes):
    """按文件头判定 MIME；不支持或无法确认的格式返回 None（由调用方明确失败）。"""
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    for prefix, mime in IMAGE_FORMATS:
        if head.startswith(prefix):
            return mime
    return None


def data_url(mime: str, b64: str) -> str:
    return f"data:{mime};base64," + b64


class ConfigError(RuntimeError):
    """provider 配置缺失或不可读；消息里不出现密钥。"""


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


def text_of(resp):
    out = []
    for item in resp.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for c in item.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") == "output_text" \
                    and isinstance(c.get("text", ""), str):
                out.append(c.get("text", ""))
    return "".join(out).strip()


# 良性 output 类型：其余类型（function_call / web_search_call / …）按安全事件处理。
BENIGN_OUTPUT_TYPES = {"message", "reasoning"}


def response_problem(resp):
    """返回不可交付的原因；完整成功的响应返回 None。

    与 copilot 正式 REVIEW 同一判定口径（响应完整性校验）：只取到非空文本不足以说明评审成立——
    截断（incomplete_details）、出错（error）或非 completed 状态的文本都可能
    只是半句话，按成功退出会把它当成 Gate 结论。
    """
    if not isinstance(resp, dict):
        return f"响应不是 JSON 对象（{type(resp).__name__}）"
    err = resp.get("error")
    if err:
        detail = err.get("message") if isinstance(err, dict) else str(err)
        return f"响应带错误：{detail}"
    status = str(resp.get("status") or "").lower()
    # 没有完成状态就不是可交付的完整成功；不能因为「有文字」放行。
    if not status:
        return "响应缺少完成状态"
    if status not in ("completed", "succeeded"):
        extra = resp.get("incomplete_details")
        return f"响应状态 {status}" + (f"，incomplete_details={extra}" if extra else "")
    if resp.get("incomplete_details"):
        return f"响应不完整：incomplete_details={resp.get('incomplete_details')}"
    output = resp.get("output")
    if not isinstance(output, list) or not output:
        return "响应缺少 output"
    for it in output:
        if not isinstance(it, dict):
            return f"响应 output 结构异常：{type(it).__name__}"
        if it.get("type") and it["type"] not in BENIGN_OUTPUT_TYPES:
            return f"响应含非预期 output 类型：{it.get('type')}"
        msg_status = str(it.get("status") or "").lower()
        if msg_status and msg_status != "completed":
            return f"响应 message 状态 {msg_status}"
        content = it.get("content")
        if content is not None and not isinstance(content, list):
            return "响应 message content 结构异常"
        for c in content or []:
            if not isinstance(c, dict):
                return f"响应 content 结构异常：{type(c).__name__}"
            if c.get("type") == "output_text" and not isinstance(c.get("text", ""), str):
                return "响应 output_text 不是字符串"
    return None


def refuse(message):
    print("拒绝：" + message, file=sys.stderr)
    raise SystemExit(2)


def load_image(path):
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(p):
        refuse(f"{path} 不是磁盘上的真实文件。视觉评审必须基于真实像素。")
    with open(p, "rb") as fh:  # 一次读取：大小、魔数、指纹与发送字节来自同一快照
        raw = fh.read()
    if len(raw) < 64:
        refuse(f"{path} 太小（{len(raw)} B），不像真实图片。")
    mime = sniff_image_mime(raw[:64])
    if mime is None:
        refuse(f"{path} 不是受支持的图片格式（支持 png/jpeg/webp/gif，"
               f"按文件头判定；前 8 字节 {raw[:8]!r}）。")
    return p, mime, base64.b64encode(raw).decode(), len(raw), hashlib.sha256(raw).hexdigest()[:16]


def health():
    try:
        base, key = load_endpoint()
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 2
    try:
        req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=60) as r:
            ids = [m.get("id", "") for m in json.loads(r.read()).get("data", [])]
    except Exception as e:
        print(f"❌ 无法列出模型：{type(e).__name__}")
        return 2
    if not ids:
        print("❌ 接口可达但模型列表为空")
        return 2
    print("✅ provider 可达（未发起评审，零成本检查）")
    print("   可用模型：" + "、".join(ids))
    if DEFAULT_MODEL not in ids:
        print(f"   ⚠️ 默认模型 {DEFAULT_MODEL} 不在列表；请用 --model 指定实际可用模型")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", action="append", default=[], help="真实图片路径，可重复")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--confirm-gpt-review", action="store_true",
                    help="确认用户已明确授权 GPT 评审通道；未授权调用会被拒绝")
    a = ap.parse_args()

    if a.health:
        return health()
    if not a.confirm_gpt_review:
        print("拒绝：外部 GPT 视觉评审需要用户明确授权（点名 GPT / GPT 视觉评审 / "
              "Copilot / 正式 REVIEW）。未授权时请用 DesignWise 原生视觉自检；"
              "授权后由调用方传 --confirm-gpt-review。")
        return 2
    if not a.image:
        print("拒绝：至少需要一张 --image。文字或提示词不能替代真实视觉评审。")
        return 2
    if not a.prompt.strip():
        ap.error("需要 --prompt 说明要评审什么")

    try:
        base, key = load_endpoint()
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 2
    content = [{"type": "input_text", "text": a.prompt}]
    for path in a.image:
        p, mime, b64, n, sha = load_image(path)
        print(f"送审 {p} · {mime} · {n} B · sha256 {sha}", file=sys.stderr)
        content.append({"type": "input_image", "image_url": data_url(mime, b64)})

    sent = sum(1 for c in content if c["type"] == "input_image")
    if sent != len(a.image):
        print(f"❌ 载荷里图片数 {sent} != 声明数 {len(a.image)}，拒绝发送")
        return 1

    try:
        resp = post(base + "/responses", key,
                    {"model": a.model, "input": [{"role": "user", "content": content}],
                     # 与 copilot 正式 REVIEW 同一能力边界：不带 tools，显式关闭工具选择与存储。
                     "tool_choice": "none", "store": False, "stream": False},
                    a.timeout)
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}：{e.read()[:300].decode('utf-8', 'replace')}")
        return 1
    except Exception as e:
        # 超时与连接中断属于请求结果未知：可能已被上游接收并计费。
        # 明确提示不得自动换入口重发，避免同一份证据被重复付费评审。
        print(f"❌ {type(e).__name__}：{str(e)[:200]}")
        print("   请求结果未知（可能已被上游接收并计费）：不要自动重试或改用其他入口重发，"
              "确认后再发起。", file=sys.stderr)
        return 1

    problem = response_problem(resp)
    if problem:
        print(f"❌ 响应不可作为评审结论：{problem}")
        return 1
    txt = text_of(resp)
    if not txt:
        print("❌ 模型没有返回评审文本")
        return 1
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
