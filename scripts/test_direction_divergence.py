#!/usr/bin/env python3
"""direction_divergence.py 的回归：差异度量、判定、退出码与输出结构。

用临时生成的图片做 fixture，不依赖仓库里的真实概念图。
缺少 Pillow 时跳过并说明原因，不伪造通过。
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "direction_divergence.py")

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None


W, H = 360, 640


def _base(color_bar, card, side_bar=False):
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    if side_bar:
        d.rectangle([0, 0, 110, H], fill=color_bar)
        for i in range(5):
            d.rectangle([130, 80 + i * 100, W - 20, 150 + i * 100], fill=card)
    else:
        d.rectangle([0, 0, W, 90], fill=color_bar)
        d.rectangle([30, 140, W - 30, 280], fill=card)
        for i in range(3):
            d.rectangle([30, 320 + i * 90, W - 30, 380 + i * 90], fill=card)
    return im


def _variant(im, dx=6, dy=0):
    """同骨架、同色板的轻微位移版本。"""
    return im.transform(im.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), fillcolor=(255, 255, 255))


@unittest.skipIf(Image is None, "未安装 Pillow：无法生成/读取图像 fixture")
class DirectionDivergenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.a = os.path.join(self.dir, "A.png")
        self.b = os.path.join(self.dir, "B.png")          # 同骨架、异色板
        self.c = os.path.join(self.dir, "C.png")          # 异骨架、同色板
        self.d = os.path.join(self.dir, "D.png")          # 完全不同的暗色构图
        self.a2 = os.path.join(self.dir, "A2.png")        # 同骨架、同色板的轻微位移

        base = _base((30, 90, 200), (225, 232, 245))
        base.save(self.a)
        _base((20, 140, 70), (250, 228, 195)).save(self.b)
        _base((30, 90, 200), (225, 232, 245), side_bar=True).save(self.c)
        dark = Image.new("RGB", (W, H), (12, 12, 12))
        ImageDraw.Draw(dark).ellipse([50, 180, W - 50, 520], fill=(200, 80, 40))
        dark.save(self.d)
        _variant(base).save(self.a2)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, images, extra=()):
        out = os.path.join(self.dir, "out.json")
        args = [sys.executable, SCRIPT]
        for p in images:
            args += ["--image", p]
        args += ["--out", out, *extra]
        proc = subprocess.run(args, capture_output=True, text=True)
        payload = None
        if os.path.isfile(out):
            with open(out, encoding="utf-8") as f:
                payload = json.load(f)
        return proc, payload

    def _pair(self, payload, a, b):
        for p in payload["pairs"]:
            if {p["a"], p["b"]} == {a, b}:
                return p
        self.fail(f"输出缺少 {a} ↔ {b} 的组合")

    def test_schema_and_fingerprints(self):
        proc, data = self._run([self.a, self.b])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(data["schema"], "designwise-divergence/v1")
        self.assertEqual(len(data["images"]), 2)
        for img in data["images"]:
            self.assertRegex(img["sha256"], r"^[0-9a-f]{64}$")
            with open(img["path"], "rb") as f:
                self.assertEqual(img["sha256"], hashlib.sha256(f.read()).hexdigest())
            self.assertEqual(img["size"], [W, H])
        self.assertEqual(len(data["pairs"]), 1)
        self.assertIn("palette_distance", data["pairs"][0])
        self.assertIn("skeleton_correlation", data["pairs"][0])

    def test_same_skeleton_different_palette(self):
        proc, data = self._run([self.a, self.b])
        pair = self._pair(data, "A.png", "B.png")
        self.assertGreater(pair["skeleton_correlation"], 0.55)
        self.assertGreaterEqual(pair["palette_distance"], 0.06)
        self.assertEqual(pair["verdict"], "same-skeleton")
        self.assertEqual(proc.returncode, 0)

    def test_different_skeleton(self):
        proc, data = self._run([self.a, self.c, self.d])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for other in ("C.png", "D.png"):
            pair = self._pair(data, "A.png", other)
            self.assertLessEqual(pair["skeleton_correlation"], 0.55, pair)
            self.assertNotIn(pair["verdict"], ("same-skeleton", "reskin"))

    def test_reskin_detected(self):
        proc, data = self._run([self.a, self.a2])
        pair = self._pair(data, "A.png", "A2.png")
        self.assertGreater(pair["skeleton_correlation"], 0.55)
        self.assertLess(pair["palette_distance"], 0.06)
        self.assertEqual(pair["verdict"], "reskin")

    def test_strict_exit_code(self):
        proc, _ = self._run([self.a, self.a2], extra=["--strict"])
        self.assertEqual(proc.returncode, 1)
        proc_ok, _ = self._run([self.a, self.d], extra=["--strict"])
        self.assertEqual(proc_ok.returncode, 0, proc_ok.stderr)

    def test_single_image_is_usage_error(self):
        proc, data = self._run([self.a])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("至少需要 2 个", proc.stderr)
        self.assertIsNone(data)

    def test_unreadable_image_is_error_not_placeholder(self):
        broken = os.path.join(self.dir, "broken.png")
        with open(broken, "wb") as f:
            f.write(b"not a png")
        proc, data = self._run([self.a, broken])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("无法解码", proc.stderr)
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()
