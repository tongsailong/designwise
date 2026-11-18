#!/usr/bin/env python3
"""test_zcode_image.py — zcode_image.py 的零费用行为测试（不请求上游接口）。

覆盖：批量全部成功、批量部分失败不落半批文件、旧输出保护、坏 base64/缺
b64_json、数量不足、尺寸适配成功与失败、env provider 覆盖、退出码。
全部使用本地合成图片与 mock 响应；运行：python3 scripts/test_zcode_image.py
"""

import base64
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zcode_image as zi  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover - 本机依赖检查
    Image = None

# image_complete() 只做结构校验：PNG 末尾 12 字节含 IEND，JPEG 以 FFD9 结束。
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
BAD = b"not an image at all" + b"\x00" * 20


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def real_png(size=(20, 20)) -> bytes:
    if Image is None:
        raise unittest.SkipTest("Pillow 未安装，跳过尺寸适配测试")
    buf = io.BytesIO()
    Image.new("RGB", size, (255, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


def real_png_rgba(size=(32, 32)) -> bytes:
    if Image is None:
        raise unittest.SkipTest("Pillow 未安装")
    buf = io.BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 128)).save(buf, "PNG")
    return buf.getvalue()


class ImageBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="zcode_image_test_")
        self.addCleanup(self.tmpdir.cleanup)
        self.root = self.tmpdir.name
        self.out = os.path.join(self.root, "out.png")
        self.payloads = []
        self.orig_post = zi.post
        self.orig_endpoint = zi.load_endpoint
        zi.load_endpoint = lambda: ("http://127.0.0.1:1/v1", "dummy")
        self.addCleanup(self._restore)

    def _restore(self):
        zi.post = self.orig_post
        zi.load_endpoint = self.orig_endpoint

    def _run(self, response, *extra, post=None):
        def fake_post(url, key, payload, timeout):
            self.payloads.append(payload)
            return response

        zi.post = post or fake_post
        old = sys.argv
        sys.argv = ["zcode_image.py", "--prompt", "test", "--out", self.out] + list(extra)
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = zi.main()
        finally:
            sys.argv = old
        return code, out.getvalue(), err.getvalue()

    def _outputs(self):
        return sorted(os.listdir(self.root))

    def test_batch_success_writes_all(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}, {"b64_json": b64(PNG)}]}, "--n", "2")
        self.assertEqual(code, 0, out)
        self.assertEqual(self._outputs(), ["out-1.png", "out-2.png"])
        self.assertIn("out-1.png", out)
        self.assertIn("out-2.png", out)

    def test_partial_batch_leaves_no_half_written_outputs(self):
        first = os.path.join(self.root, "out-1.png")
        with open(first, "wb") as fh:
            fh.write(b"OLD-CONTENT")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}, {"b64_json": b64(BAD)}]}, "--n", "2")
        self.assertEqual(code, 1, out)
        with open(first, "rb") as fh:
            self.assertEqual(fh.read(), b"OLD-CONTENT", "既有输出不得被半批结果覆盖")
        self.assertFalse(os.path.exists(os.path.join(self.root, "out-2.png")))
        self.assertFalse([n for n in os.listdir(self.root)
                          if n.startswith(".zcode-image-")], "临时文件必须清理")

    def test_directory_target_is_preflighted_before_any_replace(self):
        first = os.path.join(self.root, "out-1.png")
        with open(first, "wb") as fh:
            fh.write(b"OLD-CONTENT")
        os.makedirs(os.path.join(self.root, "out-2.png"))
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}, {"b64_json": b64(PNG)}]}, "--n", "2")
        self.assertEqual(code, 1, out)
        self.assertIn("输出路径是目录", out)
        with open(first, "rb") as fh:
            self.assertEqual(fh.read(), b"OLD-CONTENT", "预检失败不得替换第一个文件")
        self.assertTrue(os.path.isdir(os.path.join(self.root, "out-2.png")))
        self.assertFalse([n for n in os.listdir(self.root)
                          if n.startswith((".zcode-image-", ".zcode-backup-"))])

    def test_short_batch_fails_closed(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]}, "--n", "2")
        self.assertEqual(code, 1, out)
        self.assertEqual(self._outputs(), [], "数量不足时不得留下任何输出")

    def test_missing_b64_json_fails_closed(self):
        code, out, _ = self._run({"data": [{"url": "https://example.invalid/x.png"}]})
        self.assertEqual(code, 1, out)
        self.assertEqual(self._outputs(), [])
        self.assertIn("b64_json", out)

    def test_invalid_base64_fails_closed(self):
        code, out, _ = self._run({"data": [{"b64_json": "!!!"}]})
        self.assertEqual(code, 1, out)
        self.assertEqual(self._outputs(), [])

    def test_non_object_response_fails_closed(self):
        code, out, _ = self._run(["not", "a", "dict"])
        self.assertEqual(code, 1, out)
        self.assertEqual(self._outputs(), [])

    def test_fit_failure_preserves_existing_output(self):
        with open(self.out, "wb") as fh:
            fh.write(b"OLD-CONTENT")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}]}, "--size", "10x10")
        self.assertEqual(code, 1, out)
        with open(self.out, "rb") as fh:
            self.assertEqual(fh.read(), b"OLD-CONTENT", "适配失败不得覆盖既有输出")
        self.assertFalse([n for n in os.listdir(self.root)
                          if n.startswith(".zcode-image-")])

    def test_fit_success_is_exact_and_atomic(self):
        if Image is None:
            self.skipTest("Pillow 未安装")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(real_png((32, 32)))}]}, "--size", "16x16")
        self.assertEqual(code, 0, out)
        with Image.open(self.out) as im:
            self.assertEqual(im.size, (16, 16))
        self.assertFalse([n for n in os.listdir(self.root)
                          if n.startswith(".zcode-image-")])

    def test_extra_items_are_ignored_for_n1(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}, {"b64_json": b64(BAD)}]})
        self.assertEqual(code, 0, out)
        self.assertEqual(self._outputs(), ["out.png"])

    def test_n_above_cap_warns_and_clamps(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)} for _ in range(4)]}, "--n", "5")
        self.assertEqual(code, 0, out)
        self.assertIn("--n 上限为 4", out)
        self.assertEqual(len(self._outputs()), 4)

    # ------------------------------------------------ GPT-Image-2.6 路由与参数契约

    def test_default_route_is_26_sunburst_high_high(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]})
        self.assertEqual(code, 0, out)
        payload = self.payloads[-1]
        self.assertEqual(payload["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(payload["complexity"], "high")
        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["output_format"], "png")
        self.assertNotIn("gpt-image-2.5", json.dumps(payload))

    def test_explore_profile_routes_flare_medium_medium(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--profile", "explore")
        self.assertEqual(code, 0, out)
        payload = self.payloads[-1]
        self.assertEqual(payload["model"], "gpt-image-2.6-flare")
        self.assertEqual(payload["complexity"], "medium")
        self.assertEqual(payload["quality"], "medium")

    def test_premium_profile_uses_xhigh(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--profile", "premium")
        self.assertEqual(code, 0, out)
        payload = self.payloads[-1]
        self.assertEqual(payload["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(payload["complexity"], "high")
        self.assertEqual(payload["quality"], "xhigh")

    def test_max_profile_uses_max_quality(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--profile", "max")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.payloads[-1]["quality"], "max")

    def test_explicit_model_and_parameters_override_profile(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}]},
            "--profile", "explore", "--model", "gpt-image-2.6-sunburst",
            "--complexity", "low", "--quality", "high")
        self.assertEqual(code, 0, out)
        payload = self.payloads[-1]
        self.assertEqual(payload["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(payload["complexity"], "low")
        self.assertEqual(payload["quality"], "high")

    def test_edit_request_carries_26_parameters(self):
        if Image is None:
            self.skipTest("Pillow 未安装")
        ref = os.path.join(self.root, "ref.png")
        with open(ref, "wb") as fh:
            fh.write(real_png((32, 32)))
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(real_png_rgba())}]},
            "--ref", ref, "--profile", "premium", "--background", "transparent")
        self.assertEqual(code, 0, out)
        payload = self.payloads[-1]
        self.assertIn("images", payload)
        self.assertEqual(payload["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(payload["complexity"], "high")
        self.assertEqual(payload["quality"], "xhigh")
        self.assertEqual(payload["background"], "transparent")

    def test_png_compression_is_rejected_before_request(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--compression", "80")
        self.assertEqual(code, 1, out)
        self.assertIn("PNG 不支持", out)
        self.assertEqual(self.payloads, [])

    def test_size_must_be_multiple_of_16(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--size", "1000x1536")
        self.assertEqual(code, 1, out)
        self.assertIn("16 的倍数", out)
        self.assertEqual(self.payloads, [])

    def test_size_ratio_must_be_within_1_to_3(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--size", "1024x4096")
        self.assertEqual(code, 1, out)
        self.assertIn("1:3", out)
        self.assertEqual(self.payloads, [])

    def test_output_extension_must_match_format(self):
        code, out, _ = self._run({"data": [{"b64_json": b64(PNG)}]},
                                 "--out", os.path.join(self.root, "x.webp"))
        self.assertEqual(code, 1, out)
        self.assertIn("不一致", out)
        self.assertEqual(self.payloads, [])

    def test_non_26_model_warns_and_omits_complexity(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}]},
            "--model", "gpt-image-2.5", "--complexity", "high")
        self.assertEqual(code, 0, out)
        self.assertIn("非 2.6 模型", out)
        self.assertNotIn("complexity", self.payloads[-1])

    def test_api_error_does_not_fallback_or_write(self):
        calls = []

        def failing_post(url, key, payload, timeout):
            calls.append(url)
            raise urllib.error.HTTPError(url, 503, "upstream", {}, io.BytesIO(b"down"))

        code, out, _ = self._run(None, post=failing_post)
        self.assertEqual(code, 1, out)
        self.assertEqual(len(calls), 1, "失败时不得重试或切换模型")
        self.assertIn("HTTP 503", out)
        self.assertEqual(self._outputs(), [])

    def test_webp_conversion_and_meta_contract(self):
        if Image is None:
            self.skipTest("Pillow 未安装")
        meta_path = os.path.join(self.root, "out.meta.json")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(real_png((64, 64)))},
                      {"size": "1536x1024", "output_format": "png",
                       "quality": "low", "usage": {"output_tokens": 10}}]},
            "--out", os.path.join(self.root, "hero.webp"),
            "--output-format", "webp", "--compression", "82",
            "--size", "32x32", "--meta-out", meta_path)
        self.assertEqual(code, 0, out)
        with Image.open(os.path.join(self.root, "hero.webp")) as im:
            self.assertEqual(im.format, "WEBP")
            self.assertEqual(im.size, (32, 32))
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertEqual(meta["schema"], "designwise-image-meta/v1")
        self.assertEqual(meta["request"]["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(meta["request"]["profile"], "final")
        self.assertEqual(meta["request"]["complexity"], "high")
        self.assertEqual(meta["request"]["quality"], "high")
        self.assertEqual(meta["request"]["output_format"], "webp")
        self.assertEqual(meta["request"]["compression"], 82)
        self.assertEqual(meta["assets"][0]["format"], "webp")
        self.assertEqual(meta["assets"][0]["width"], 32)
        self.assertEqual(len(meta["assets"][0]["sha256"]), 64)
        text = json.dumps(meta)
        self.assertNotIn("dummy", text)
        self.assertNotIn("Authorization", text)
        self.assertNotIn("api_key", text)

    def test_meta_out_is_not_written_when_generation_fails(self):
        meta_path = os.path.join(self.root, "out.meta.json")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(BAD)}]}, "--meta-out", meta_path)
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(meta_path))

    def test_quality_echo_mismatch_is_reported_but_not_silent(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}], "quality": "low", "size": "1024x1536"})
        self.assertEqual(code, 0, out)
        self.assertIn("quality=low 与请求 high 不一致", out)

    def test_quality_echo_is_recorded_in_meta(self):
        if Image is None:
            self.skipTest("Pillow 未安装")
        meta_path = os.path.join(self.root, "out.meta.json")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(real_png((32, 32)))}], "quality": "low"},
            "--meta-out", meta_path)
        self.assertEqual(code, 0, out)
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertTrue(meta["response"]["quality_echo_mismatch"])
        self.assertFalse(meta["response"]["complexity_echoed"])

    def test_transparent_background_without_alpha_fails_closed(self):
        if Image is None:
            self.skipTest("Pillow 未安装")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(real_png((32, 32)))}]},
            "--background", "transparent")
        self.assertEqual(code, 1, out)
        self.assertIn("alpha", out)
        self.assertEqual(self._outputs(), [])

    def test_transparent_background_with_alpha_passes(self):
        if Image is None:
            self.skipTest("Pillow 未安装")
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(real_png_rgba())}]},
            "--background", "transparent")
        self.assertEqual(code, 0, out)
        with Image.open(self.out) as im:
            self.assertIn(im.mode, ("RGBA", "LA", "PA"))

    def test_transparent_jpeg_is_rejected_before_request(self):
        code, out, _ = self._run(
            {"data": [{"b64_json": b64(PNG)}]},
            "--out", os.path.join(self.root, "x.jpg"),
            "--output-format", "jpeg", "--background", "transparent")
        self.assertEqual(code, 1, out)
        self.assertIn("JPEG 不支持透明", out)
        self.assertEqual(self.payloads, [])


class ConfigTests(unittest.TestCase):
    def test_env_endpoint_override_needs_no_local_config(self):
        with unittest.mock.patch.dict(
                os.environ,
                {"ZCODE_CPA_BASE_URL": "http://example.invalid/v1/",
                 "ZCODE_CPA_API_KEY": "test-key"}, clear=False):
            self.assertEqual(zi.load_endpoint(), ("http://example.invalid/v1", "test-key"))

    def test_missing_config_raises_config_error(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    zi, "CONFIG", "/nonexistent/provider-config.json"):
            with self.assertRaises(zi.ConfigError):
                zi.load_endpoint()

    def test_health_config_error_returns_2(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    zi, "CONFIG", "/nonexistent/provider-config.json"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(zi.health(), 2)

    def test_health_fails_closed_when_default_26_model_missing(self):
        with unittest.mock.patch.object(
                zi, "load_endpoint", return_value=("http://example.invalid/v1", "k")), \
                unittest.mock.patch.object(
                    zi, "get_models",
                    return_value=["gpt-image-2.5", "gpt-image-2.6-flare"]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(zi.health(), 2)
        self.assertIn("不会静默降级", out.getvalue())

    def test_health_passes_when_default_26_model_present(self):
        with unittest.mock.patch.object(
                zi, "load_endpoint", return_value=("http://example.invalid/v1", "k")), \
                unittest.mock.patch.object(
                    zi, "get_models",
                    return_value=["gpt-image-2.6-sunburst", "gpt-image-2.6-flare"]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(zi.health(), 0)
        self.assertIn("gpt-image-2.6-sunburst", out.getvalue())

    def test_main_config_error_returns_2_without_writing(self):
        out = os.path.join(tempfile.mkdtemp(prefix="zcode_image_cfg_"), "out.png")
        with unittest.mock.patch.dict(os.environ, {}, clear=True), \
                unittest.mock.patch.object(
                    zi, "CONFIG", "/nonexistent/provider-config.json"), \
                contextlib.redirect_stdout(io.StringIO()):
            old = sys.argv
            sys.argv = ["zcode_image.py", "--prompt", "x", "--out", out]
            try:
                code = zi.main()
            finally:
                sys.argv = old
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main(verbosity=2)
