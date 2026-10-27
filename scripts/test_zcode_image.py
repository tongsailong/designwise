#!/usr/bin/env python3
"""test_zcode_image.py — zcode_image.py 的零费用行为测试（不请求上游接口）。

覆盖：批量全部成功、批量部分失败不落半批文件、旧输出保护、坏 base64/缺
b64_json、数量不足、尺寸适配成功与失败、env provider 覆盖、退出码。
全部使用本地合成图片与 mock 响应；运行：python3 scripts/test_zcode_image.py
"""

import base64
import contextlib
import io
import os
import sys
import tempfile
import unittest
import unittest.mock

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

    def _run(self, response, *extra):
        def fake_post(url, key, payload, timeout):
            self.payloads.append(payload)
            return response

        zi.post = fake_post
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
            {"data": [{"b64_json": b64(real_png((20, 20)))}]}, "--size", "10x10")
        self.assertEqual(code, 0, out)
        with Image.open(self.out) as im:
            self.assertEqual(im.size, (10, 10))
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
