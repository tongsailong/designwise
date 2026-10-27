#!/usr/bin/env python3
"""test_check_assets.py — check-assets.py 的目录/文件缺失行为测试。

重点回归：assets/images/ 有位图但 img-prompts/ 整个目录缺失时，旧实现会
「跳过检查」并误报成功；现在必须失败。
运行：python3 scripts/test_check_assets.py
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-assets.py")


class CheckAssetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="check_assets_test_")
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def write(self, rel, text=""):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def image(self, rel="assets/images/foo.png"):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\nfake")
        return path

    def run_check(self):
        return subprocess.run(
            [sys.executable, SCRIPT, self.root],
            text=True, capture_output=True, timeout=30,
        )

    def test_missing_assets_md_exits_2(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 2)
        self.assertIn("找不到 assets.md", r.stdout)

    def test_reference_to_missing_image_fails(self):
        self.write("handoff/assets.md", "| assets/images/ghost.png |\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("清单引用了不存在的文件", r.stdout)

    def test_unregistered_image_fails(self):
        self.image()
        self.write("handoff/assets.md", "no images here\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("未登记", r.stdout)

    def test_missing_prompts_directory_fails_for_each_image(self):
        self.image()
        self.write("handoff/assets.md", "| assets/images/foo.png |\n")
        # 不创建 assets/img-prompts/ —— 旧实现会静默跳过
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("一图一档", r.stdout)
        self.assertIn("img-prompts/foo.md", r.stdout)

    def test_missing_prompt_file_fails(self):
        self.image()
        self.write("handoff/assets.md", "| assets/images/foo.png |\n")
        self.write("assets/img-prompts/other.md", "prompt\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("img-prompts/foo.md", r.stdout)

    def test_complete_assets_pass(self):
        self.image()
        self.write("handoff/assets.md", "| assets/images/foo.png |\n")
        self.write("assets/img-prompts/foo.md", "prompt\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("通过", r.stdout)

    def test_no_bitmaps_is_not_a_failure(self):
        self.write("handoff/assets.md", "no bitmap assets\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("无位图", r.stdout)

    def test_assets_md_at_project_root_is_supported(self):
        self.image()
        self.write("assets.md", "| assets/images/foo.png |\n")
        self.write("assets/img-prompts/foo.md", "prompt\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_nested_image_with_nested_prompt_passes(self):
        self.image("assets/images/icons/foo.png")
        self.write("handoff/assets.md", "| assets/images/icons/foo.png |\n")
        self.write("assets/img-prompts/icons/foo.md", "prompt\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_nested_image_without_nested_prompt_fails(self):
        self.image("assets/images/icons/foo.png")
        self.write("handoff/assets.md", "| assets/images/icons/foo.png |\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("img-prompts/icons/foo.md", r.stdout)

    def test_nested_and_flat_same_name_are_not_confused(self):
        self.image("assets/images/foo.png")
        self.image("assets/images/icons/foo.png")
        self.write("handoff/assets.md", "| assets/images/icons/foo.png |\n")
        self.write("assets/img-prompts/foo.md", "prompt\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("assets/images/foo.png 未登记", r.stdout)
        self.assertIn("img-prompts/icons/foo.md", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
