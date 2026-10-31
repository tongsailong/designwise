#!/usr/bin/env python3
"""ref_board.py 的离线回归：只测不依赖浏览器的部分，绝不伪造截图成功。

覆盖：看板 HTML 生成与转义、空白检测、缺 Chrome 时的明确报错、部分失败仍出板。
截图本身依赖本机 Chrome，属人工验收范围，不在单元测试里假装通过。
"""
import json
import os
import shutil
import tempfile
import unittest

import ref_board


def _has_pil():
    return ref_board.Image is not None


class BoardHtmlTest(unittest.TestCase):
    def test_board_contains_entries_and_is_self_contained(self):
        entries = [
            {
                "kind": "url",
                "source": "https://example.com/a",
                "label": "示例 <页>",
                "rel_shot": "shots/url-01.png",
                "title": "Example",
                "blockers": ["横向溢出"],
                "blank": False,
            },
            {
                "kind": "image",
                "source": "./ref/noise.png",
                "label": "noise.png",
                "rel_shot": "shots/local-01.png",
                "blank": True,
                "blank_reason": "近乎单一颜色（疑似空白/未渲染）",
            },
        ]
        html = ref_board.build_board_html(entries, "参考板 <测试>", "2026-10-31 10:00")
        self.assertIn("shots/url-01.png", html)
        self.assertIn("shots/local-01.png", html)
        # 标签与标题必须转义，不能把外来文本当 HTML 执行
        self.assertIn("示例 &lt;页&gt;", html)
        self.assertIn("参考板 &lt;测试&gt;", html)
        self.assertNotIn("<页>", html)
        # 截图只引本地相对路径，不联网加载图片
        self.assertNotIn('<img src="http', html)
        # 空白与采集提示都要露出来，不能静默吞掉
        self.assertIn("疑似空白", html)
        self.assertIn("横向溢出", html)
        self.assertIn("2 个来源", html)

    def test_empty_board_says_so(self):
        html = ref_board.build_board_html([], "空板", "2026-10-31 10:00")
        self.assertIn("还没有来源", html)
        self.assertIn("0 个来源", html)


class BlankDetectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dw-ref-board-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipUnless(_has_pil(), "需要 Pillow 才能生成/检测图片")
    def test_solid_image_is_flagged_and_noise_is_not(self):
        from PIL import Image

        solid = os.path.join(self.tmp, "solid.png")
        Image.new("RGB", (320, 200), (240, 240, 240)).save(solid)
        info = ref_board.detect_blank(solid)
        self.assertTrue(info["blank"], info)
        self.assertLess(info["stddev"], 2.0)

        noise = os.path.join(self.tmp, "noise.png")
        img = Image.new("RGB", (320, 200))
        px = img.load()
        for y in range(200):
            for x in range(320):
                px[x, y] = ((x * 7) % 256, (y * 11) % 256, ((x + y) * 5) % 256)
        img.save(noise)
        info = ref_board.detect_blank(noise)
        self.assertFalse(info["blank"], info)

    def test_missing_file_reports_reason_not_crash(self):
        info = ref_board.detect_blank(os.path.join(self.tmp, "nope.png"))
        self.assertIsNone(info["blank"])
        self.assertTrue(info["reason"])


class CaptureEnvTest(unittest.TestCase):
    def test_missing_chrome_raises_explicit_error(self):
        with self.assertRaises(ref_board.RefBoardError) as ctx:
            ref_board.capture_url(
                "http://127.0.0.1:1/x", "/tmp/dw-never-written.png",
                "/nonexistent/chrome-binary", 800, 600,
            )
        self.assertIn("chrome", str(ctx.exception).lower())
        self.assertFalse(os.path.exists("/tmp/dw-never-written.png"))

    def test_explicit_chrome_path_must_exist(self):
        self.assertIsNone(ref_board.find_chrome("/nonexistent/chrome-binary"))


class MainFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dw-ref-board-main-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _png(self, name):
        path = os.path.join(self.tmp, name)
        if _has_pil():
            from PIL import Image
            Image.new("RGB", (64, 64), (30, 30, 30)).save(path)
        else:  # 没有 Pillow 时造一个最小 PNG 头，够 copyfile 与路径检查
            with open(path, "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n")
        return path

    def test_local_images_build_board_without_chrome(self):
        img = self._png("one.png")
        out = os.path.join(self.tmp, "board")
        code = ref_board.main(["--out", out, "--image", img, "--no-capture"])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(out, "board.html")))
        with open(os.path.join(out, "board.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(len(manifest["entries"]), 1)
        self.assertEqual(manifest["entries"][0]["kind"], "image")
        self.assertEqual(manifest["errors"], [])
        self.assertTrue(os.path.isfile(os.path.join(out, "shots", "local-01.png")))

    def test_url_without_chrome_fails_loudly(self):
        out = os.path.join(self.tmp, "board2")
        code = ref_board.main([
            "--out", out, "--url", "http://127.0.0.1:1/x",
            "--chrome", "/nonexistent/chrome-binary",
        ])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.isfile(os.path.join(out, "board.html")))

    def test_partial_failure_still_builds_board_and_exits_1(self):
        good = self._png("good.png")
        out = os.path.join(self.tmp, "board3")
        code = ref_board.main([
            "--out", out,
            "--image", good,
            "--image", os.path.join(self.tmp, "missing.png"),
            "--no-capture",
        ])
        self.assertEqual(code, 1)
        self.assertTrue(os.path.isfile(os.path.join(out, "board.html")))
        with open(os.path.join(out, "board.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(len(manifest["entries"]), 1)
        self.assertTrue(manifest["errors"])


if __name__ == "__main__":
    unittest.main()
