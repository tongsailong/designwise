#!/usr/bin/env python3
"""review_packet.py 的契约测试。

锁三件事：
1. 交接包必须带真实像素的 sha256/尺寸与屏幕/状态/缩放，顺序与提交一致；
2. 同一文件或同一像素换个名字重复提交会被拒绝（防一张图充多屏）；
3. 包内明确「咨询材料、不构成批准」，九问默认可覆盖。
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

import review_packet as RP  # noqa: E402

from PIL import Image  # noqa: E402


def make_png(path: Path, color=(200, 180, 160), size=(60, 120)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.first = make_png(self.dir / "p1.png")
        self.second = make_png(self.dir / "p2.png", color=(90, 120, 160))

    def spec(self, **overrides) -> dict:
        spec = {
            "product": "稍后读工具",
            "goal": "地铁碎片时间读完长文",
            "audience": "通勤族",
            "direction": "采用方向 B：纸面阅读",
            "dna": "暖白底 / 近黑正文 / 单一进度刻度",
            "device": "Android 460dp",
            "changes_since_last": "首次评审",
            "images": [
                {"path": self.first.name, "screen": "P1", "state": "默认",
                 "scale": "1.0", "note": "首屏"},
                {"path": self.second.name, "screen": "P2", "state": "空态"},
            ],
        }
        spec.update(overrides)
        return spec

    def write_spec(self, spec: dict) -> Path:
        path = self.dir / "review-packet.json"
        path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        return path

    def test_packet_carries_real_image_facts_in_order(self):
        spec = self.spec()
        rows = RP.image_rows(spec, self.dir)
        text = RP.render(spec, rows)
        self.assertIn("P1", text)
        self.assertIn("P2", text)
        self.assertIn("60x120", text)
        self.assertEqual(len(rows[0]["sha256"]), 64)
        self.assertEqual(rows[0]["screen"], "P1")
        self.assertEqual(rows[1]["state"], "空态")
        self.assertEqual(rows[1]["scale"], "1.0")
        # 九问默认全部出现
        for question in RP.QUESTIONS:
            self.assertIn(question, text)
        self.assertIn("不构成设计批准", text)

    def test_relative_paths_resolve_against_spec_dir(self):
        spec_path = self.write_spec(self.spec())
        spec = RP.load_spec(spec_path)
        rows = RP.image_rows(spec, spec_path.parent)
        self.assertTrue(Path(rows[0]["path"]).is_file())

    def test_duplicate_file_is_rejected(self):
        spec = self.spec(images=[
            {"path": self.first.name, "screen": "P1", "state": "默认"},
            {"path": self.first.name, "screen": "P2", "state": "默认"},
        ])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                RP.image_rows(spec, self.dir)
        self.assertEqual(ctx.exception.code, 2)

    def test_same_pixels_different_name_is_rejected(self):
        copy = self.dir / "copy-of-p1.png"
        copy.write_bytes(self.first.read_bytes())
        spec = self.spec(images=[
            {"path": self.first.name, "screen": "P1", "state": "默认"},
            {"path": copy.name, "screen": "P2", "state": "默认"},
        ])
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                RP.image_rows(spec, self.dir)
        self.assertEqual(ctx.exception.code, 2)

    def test_missing_screen_or_state_is_rejected(self):
        for bad in ({"path": self.first.name, "state": "默认"},
                    {"path": self.first.name, "screen": "P1"}):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    RP.image_rows(self.spec(images=[bad]), self.dir)
            self.assertEqual(ctx.exception.code, 2)

    def test_missing_required_field_is_rejected(self):
        spec = self.spec()
        del spec["goal"]
        path = self.write_spec(spec)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                RP.load_spec(path)
        self.assertEqual(ctx.exception.code, 2)

    def test_custom_questions_replace_defaults(self):
        spec = self.spec(questions=["这一版的第一眼对象对不对？"])
        text = RP.render(spec, RP.image_rows(spec, self.dir))
        self.assertIn("这一版的第一眼对象对不对？", text)
        self.assertNotIn(RP.QUESTIONS[0], text)

    def test_cli_writes_packet_and_json_summary(self):
        spec_path = self.write_spec(self.spec())
        out = self.dir / "packet.md"
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "review_packet.py"),
             "--spec", str(spec_path), "--out", str(out), "--json"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = out.read_text(encoding="utf-8")
        self.assertIn("# 设计评审交接包", text)
        summary = json.loads(proc.stdout[proc.stdout.index("{"):])
        self.assertEqual(summary["schema"], RP.SCHEMA)
        self.assertEqual(summary["image_count"], 2)
        self.assertEqual(summary["images"][0]["name"], "p1.png")
        self.assertNotIn("path", summary["images"][0])


if __name__ == "__main__":
    unittest.main()
