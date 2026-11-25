#!/usr/bin/env python3
"""design_measure.py 的契约测试。

锁三件事：
1. 输出的是客观事实（背景占比、重心、冷暖、色板），不是好坏结论；
2. 合成图的结构变化能在指标上体现（重心、留白、冷暖、对称）；
3. 非法输入直接失败（退出码 2），不写占位结果。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import design_measure as DM  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402


def make_image(path: Path, size=(120, 200), bg=(250, 248, 244),
               block=None, block_color=(20, 20, 20)) -> Path:
    im = Image.new("RGB", size, bg)
    if block:
        ImageDraw.Draw(im).rectangle(block, fill=block_color)
    im.save(path)
    return path


class MeasureFactsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_centered_mass_has_centered_centroid(self):
        path = make_image(self.dir / "center.png", block=(40, 80, 80, 120))
        facts = DM.analyze(path)
        self.assertAlmostEqual(facts["centroid"]["x"], 0.5, delta=0.08)
        self.assertAlmostEqual(facts["centroid"]["y"], 0.5, delta=0.08)
        self.assertGreater(facts["background_ratio"], 0.5)
        self.assertGreater(facts["concentration"], 0.5)

    def test_top_left_mass_moves_centroid(self):
        path = make_image(self.dir / "topleft.png", block=(4, 4, 40, 44))
        facts = DM.analyze(path)
        self.assertLess(facts["centroid"]["x"], 0.35)
        self.assertLess(facts["centroid"]["y"], 0.35)

    def test_warm_and_cool_are_distinguished(self):
        warm = make_image(self.dir / "warm.png", bg=(240, 200, 160))
        cool = make_image(self.dir / "cool.png", bg=(160, 200, 240))
        self.assertEqual(DM.analyze(warm)["temperature"], "warm")
        self.assertEqual(DM.analyze(cool)["temperature"], "cool")

    def test_symmetric_layout_scores_high(self):
        path = make_image(self.dir / "sym.png", block=(40, 80, 80, 120))
        self.assertGreater(DM.analyze(path)["symmetry"], 0.95)

    def test_palette_ratios_are_normalized_and_hex_valid(self):
        path = make_image(self.dir / "palette.png", block=(0, 0, 60, 100),
                          block_color=(160, 80, 40))
        facts = DM.analyze(path)
        total = sum(c["ratio"] for c in facts["palette_top"])
        self.assertLessEqual(total, 1.0001)
        self.assertTrue(all(c["hex"].startswith("#") and len(c["hex"]) == 7
                            for c in facts["palette_top"]))
        self.assertIn("warm", (facts["temperature"],))

    def test_consistency_reports_facts_not_verdicts(self):
        a = DM.analyze(make_image(self.dir / "a.png", block=(40, 80, 80, 120)))
        b = DM.analyze(make_image(self.dir / "b.png", block=(30, 70, 90, 130)))
        c = DM.analyze(make_image(self.dir / "c.png", bg=(160, 200, 240),
                                  block=(10, 10, 30, 30), block_color=(10, 40, 160)))
        same = DM.consistency([a, b])
        mixed = DM.consistency([a, c])
        self.assertGreater(max(same["pair_palette_overlap"]),
                           max(mixed["pair_palette_overlap"]))
        self.assertTrue(mixed["temperature_consistent"] is False)
        blob = json.dumps(mixed, ensure_ascii=False)
        for verdict in ("pass", "fail", "好", "差", "score"):
            self.assertNotIn(verdict, blob)

    def test_ink_ratio_follows_background_polarity(self):
        """深色主题的暗底是背景，不是"墨"；浅色主题反过来。"""
        light = make_image(self.dir / "light.png", block=(40, 80, 80, 120),
                           block_color=(20, 20, 20))
        dark = make_image(self.dir / "dark.png", bg=(20, 20, 20),
                          block=(40, 80, 80, 120), block_color=(240, 238, 232))
        light_facts = DM.analyze(light)
        dark_facts = DM.analyze(dark)
        self.assertEqual(light_facts["theme"], "light")
        self.assertEqual(dark_facts["theme"], "dark")
        self.assertLess(dark_facts["background_luma"], 0.2)
        # 同一块内容在亮/暗两种底色下应给出接近的内容占比
        self.assertAlmostEqual(light_facts["ink_ratio"], dark_facts["ink_ratio"],
                               delta=0.03)
        self.assertLess(light_facts["ink_ratio"], 0.35)
        self.assertLess(dark_facts["ink_ratio"], 0.35)

    def test_dark_screen_is_not_counted_as_ink(self):
        """纯深色底 + 少量亮内容：背景算背景，不能整屏算成墨。"""
        path = make_image(self.dir / "darktext.png", bg=(18, 18, 16),
                          block=(10, 10, 30, 14), block_color=(235, 232, 224))
        facts = DM.analyze(path)
        self.assertEqual(facts["theme"], "dark")
        self.assertLess(facts["ink_ratio"], 0.02)
        self.assertGreater(facts["background_ratio"], 0.9)

    def test_missing_file_fails_closed(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                DM.analyze(self.dir / "nope.png")
        self.assertEqual(ctx.exception.code, 2)

    def test_tiny_image_fails_closed(self):
        path = make_image(self.dir / "tiny.png", size=(4, 4))
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                DM.analyze(path)
        self.assertEqual(ctx.exception.code, 2)


class MeasureCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_cli_writes_json_without_judgement(self):
        first = make_image(self.dir / "a.png")
        second = make_image(self.dir / "b.png", block=(40, 80, 80, 120))
        out = self.dir / "measure.json"
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "design_measure.py"),
             "--image", str(first), "--image", str(second), "--out", str(out)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], DM.SCHEMA)
        self.assertEqual(len(payload["images"]), 2)
        self.assertTrue(payload["consistency"])
        self.assertIn("不判断设计好坏", payload["note"])
        for key in ("background_ratio", "centroid", "thirds_energy",
                    "edge_density", "symmetry", "sha256"):
            self.assertIn(key, payload["images"][0])


if __name__ == "__main__":
    unittest.main()
