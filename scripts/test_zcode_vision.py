#!/usr/bin/env python3
"""zcode_vision.py 降级视觉评审的离线测试：MIME 按魔数判定，data URL 与真实格式一致。

修复背景（2026-10-25 评审）：旧实现把所有图片统一标为 image/png，JPEG/WEBP/GIF 送审时
data URL MIME 与真实格式不符。本测试锁死：每种受支持格式的 data URL 前缀必须与魔数判定
结果一致；不支持或无法确认的格式明确失败。

不联网、不需要凭据；只调用本地纯函数（不触发 load_endpoint / post）。
运行：python3 ~/.zcode/skills/designwise/scripts/test_zcode_vision.py
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
import unittest.mock

import zcode_vision

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
GIF = b"GIF89a" + b"\x00" * 8
WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"VP8 " + b"\x00" * 8
BMP = b"BM" + b"\x00" * 8
FAKE_SIZE = 128  # > 64，绕过"太小"拒绝；本脚本只按魔数判定，不解码像素


def fake_image(head: bytes) -> str:
    """生成以 head 开头的伪图片文件；魔数之后的填充内容不影响判定。"""
    fd, path = tempfile.mkstemp(suffix=".bin")
    with os.fdopen(fd, "wb") as fh:
        fh.write(head)
        fh.write(b"\x00" * (FAKE_SIZE - len(head)))
    return path


SUPPORTED = ((PNG, "image/png"), (JPEG, "image/jpeg"),
             (GIF, "image/gif"), (WEBP, "image/webp"))


class SniffMimeTests(unittest.TestCase):
    def test_supported_formats_map_to_correct_mime(self):
        for head, mime in SUPPORTED:
            self.assertEqual(zcode_vision.sniff_image_mime(head), mime, head[:8])

    def test_unsupported_or_unknown_format_is_refused(self):
        self.assertIsNone(zcode_vision.sniff_image_mime(BMP))
        self.assertIsNone(zcode_vision.sniff_image_mime(b"not an image header......"))
        # RIFF 容器但不是 WEBP：不得按 webp 放行
        self.assertIsNone(zcode_vision.sniff_image_mime(b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 8))


class LoadImageTests(unittest.TestCase):
    def test_data_url_mime_matches_real_format(self):
        """核心回归：data URL 前缀必须与魔数判定的真实格式一致，不得统一写成 png。"""
        for head, mime in SUPPORTED:
            path = fake_image(head)
            try:
                p, got_mime, b64, n, sha = zcode_vision.load_image(path)
                self.assertEqual(got_mime, mime, path)
                url = zcode_vision.data_url(got_mime, b64)
                self.assertTrue(url.startswith(f"data:{mime};base64,"),
                                f"data URL 前缀与真实格式不一致：{url[:40]} ≠ data:{mime}")
                self.assertEqual(n, FAKE_SIZE)
                self.assertEqual(len(sha), 16)  # 展示用截断指纹（原实现即 16 位）
            finally:
                os.unlink(path)

    def test_unsupported_format_fails_closed(self):
        path = fake_image(BMP)
        try:
            with self.assertRaises(SystemExit) as ctx:
                zcode_vision.load_image(path)
            self.assertEqual(ctx.exception.code, 2,
                             "无法送图必须按文档返回退出码 2，而不是 1")
        finally:
            os.unlink(path)

    def test_missing_file_is_refused(self):
        with self.assertRaises(SystemExit):
            zcode_vision.load_image("/nonexistent/copilot-vision-test.png")


class ResponseValidationTests(unittest.TestCase):
    """降级入口也不能把「半句话」或错误响应当成评审结论（2026-10-25 自评审 F6）。

    旧实现只检查能否取到非空文本：status=incomplete 的截断回复、带 error 的响应、
    含 function_call 的响应都会以退出码 0 返回，被下游当作 Gate 结论。
    """

    def setUp(self):
        self.payloads = []
        self.orig_post = zcode_vision.post
        self.orig_endpoint = zcode_vision.load_endpoint
        zcode_vision.load_endpoint = lambda: ("http://127.0.0.1:1/v1", "dummy")
        self.addCleanup(self._restore)

    def _restore(self):
        zcode_vision.post = self.orig_post
        zcode_vision.load_endpoint = self.orig_endpoint

    def _run(self, response):
        def fake_post(url, key, payload, timeout):
            self.payloads.append(payload)
            return response

        zcode_vision.post = fake_post
        path = fake_image(PNG)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()):
                old = sys.argv
                sys.argv = ["zcode_vision.py", "--image", path, "--prompt", "评审"]
                try:
                    code = zcode_vision.main()
                finally:
                    sys.argv = old
            return code, out.getvalue()
        finally:
            os.unlink(path)

    def test_incomplete_response_is_refused_even_with_text(self):
        code, out = self._run({
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{"content": [{"type": "output_text", "text": "裁决：PASS（截断"}]}],
        })
        self.assertEqual(code, 1, "截断响应不得以成功退出")
        self.assertNotIn("裁决：PASS", out)

    def test_error_response_is_refused(self):
        code, _ = self._run({
            "status": "completed", "error": {"message": "boom"}, "output": []})
        self.assertEqual(code, 1)

    def test_unexpected_output_type_is_refused(self):
        code, _ = self._run({
            "status": "completed",
            "output": [{"type": "function_call", "name": "shell"}]})
        self.assertEqual(code, 1)

    def test_completed_text_response_succeeds(self):
        code, out = self._run({
            "status": "completed",
            "output": [
                {"type": "reasoning", "content": []},
                {"type": "message",
                 "content": [{"type": "output_text", "text": "方向 A 更好。"}]},
            ]})
        self.assertEqual(code, 0)
        self.assertIn("方向 A 更好", out)

    def test_missing_status_is_refused(self):
        code, _ = self._run({
            "output": [{"content": [{"type": "output_text", "text": "PASS"}]}]})
        self.assertEqual(code, 1, "缺少完成状态不得当成 PASS")

    def test_missing_output_is_refused(self):
        code, _ = self._run({"status": "completed"})
        self.assertEqual(code, 1, "缺少 output 不得当成 PASS")

    def test_non_object_response_is_refused(self):
        code, _ = self._run([])
        self.assertEqual(code, 1, "非对象响应不得当成 PASS")

    def test_empty_text_is_refused(self):
        code, _ = self._run({
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "text": "   "}]}]})
        self.assertEqual(code, 1, "空评审文本不得当成 PASS")

    def test_malformed_content_is_refused(self):
        code, _ = self._run({
            "status": "completed",
            "output": [{"content": "not-a-list"}]})
        self.assertEqual(code, 1, "畸形 content 结构不得当成 PASS")

    def test_payload_keeps_zero_tool_boundary(self):
        """降级通道同样显式关闭工具与存储，不是靠提示词自律。"""
        self._run({"status": "completed",
                   "output": [{"content": [{"type": "output_text", "text": "ok"}]}]})
        self.assertEqual(self.payloads[0]["tool_choice"], "none")
        self.assertIs(self.payloads[0]["store"], False)
        self.assertNotIn("tools", self.payloads[0])


class ConfigTests(unittest.TestCase):
    def test_env_endpoint_override_needs_no_local_config(self):
        with unittest.mock.patch.dict(
                os.environ,
                {"ZCODE_CPA_BASE_URL": "http://example.invalid/v1/",
                 "ZCODE_CPA_API_KEY": "test-key"},
                clear=False):
            self.assertEqual(zcode_vision.load_endpoint(),
                             ("http://example.invalid/v1", "test-key"))

    def test_missing_config_raises_config_error(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    zcode_vision, "CONFIG", "/nonexistent/provider-config.json"):
            with self.assertRaises(zcode_vision.ConfigError):
                zcode_vision.load_endpoint()

    def test_main_config_error_returns_2(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    zcode_vision, "CONFIG", "/nonexistent/provider-config.json"), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            old = sys.argv
            sys.argv = ["zcode_vision.py", "--image", "/nonexistent.png",
                        "--prompt", "评审"]
            try:
                code = zcode_vision.main()
            finally:
                sys.argv = old
        self.assertEqual(code, 2, "无 provider 配置必须按文档返回 2")


if __name__ == "__main__":
    unittest.main()
