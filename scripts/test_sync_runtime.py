#!/usr/bin/env python3
"""test_sync_runtime.py — sync_runtime.py 的检查/写入/prune 行为测试。

运行：python3 scripts/test_sync_runtime.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "sync_runtime.py")


class SyncRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sync_runtime_test_")
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "src")
        self.dst = os.path.join(self.tmp.name, "dst")
        os.makedirs(os.path.join(self.src, "scripts"))
        os.makedirs(self.dst)
        shutil.copyfile(SCRIPT, os.path.join(self.src, "scripts", "sync_runtime.py"))
        self.write(self.src, "SKILL.md", "source\n")
        self.write(self.src, "references/a.md", "ref\n")
        self.write(self.src, ".env", "SECRET=1\n")
        self.write(self.src, ".env.local", "LOCAL_SECRET=1\n")
        self.write(self.src, ".env.example", "PLACEHOLDER=1\n")
        self.write(self.src, "assets/personal-asset-index.json", '{"real":"data"}\n')
        self.write(self.src, "design-demos/x.html", "ignored\n")
        self.write(self.src, "scripts/__pycache__/x.pyc", "ignored\n")

    def write(self, root, rel, text):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_sync(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(self.src, "scripts", "sync_runtime.py"),
             "--to", self.dst, "--force"] + list(args),
            text=True, capture_output=True, timeout=30,
        )

    def test_unrelated_target_is_refused_without_force(self):
        r = subprocess.run(
            [sys.executable, os.path.join(self.src, "scripts", "sync_runtime.py"),
             "--to", self.dst, "--check"],
            text=True, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("不像 DesignWise skill", r.stdout)

    def test_prune_without_apply_is_rejected(self):
        r = self.run_sync("--prune")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--prune 只能与 --apply", r.stdout)

    def test_check_reports_missing_then_apply_copies(self):
        r = self.run_sync("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("SKILL.md", r.stdout)
        r = self.run_sync("--apply")
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(os.path.join(self.dst, "SKILL.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "source\n")
        self.assertTrue(os.path.isfile(os.path.join(self.dst, "references/a.md")))
        self.assertFalse(os.path.exists(os.path.join(self.dst, ".env")),
                         ".env 必须排除")
        self.assertFalse(os.path.exists(os.path.join(self.dst, ".env.local")),
                         ".env.local 必须排除")
        self.assertFalse(os.path.exists(
            os.path.join(self.dst, "assets/personal-asset-index.json")),
            "个人素材索引必须排除")
        self.assertTrue(os.path.exists(os.path.join(self.dst, ".env.example")),
                        ".env.example 模板应同步")
        self.assertFalse(os.path.exists(os.path.join(self.dst, "design-demos")),
                         "design-demos 必须排除")

    def test_changed_file_is_detected_and_replaced(self):
        self.run_sync("--apply")
        self.write(self.dst, "SKILL.md", "drifted\n")
        r = self.run_sync("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("~ SKILL.md", r.stdout)
        self.assertEqual(self.run_sync("--apply").returncode, 0)
        with open(os.path.join(self.dst, "SKILL.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "source\n")

    def test_extra_files_need_prune(self):
        self.run_sync("--apply")
        self.write(self.dst, "runtime-only.md", "extra\n")
        r = self.run_sync("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("- runtime-only.md", r.stdout)
        self.assertEqual(self.run_sync("--apply").returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.dst, "runtime-only.md")),
                        "默认不删除目标多出文件")
        self.assertEqual(self.run_sync("--apply", "--prune").returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.dst, "runtime-only.md")))

    def test_identical_tree_is_clean(self):
        self.run_sync("--apply")
        r = self.run_sync("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("一致", r.stdout)

    def test_missing_target_is_refused(self):
        r = subprocess.run(
            [sys.executable, os.path.join(self.src, "scripts", "sync_runtime.py"),
             "--to", os.path.join(self.tmp.name, "nope"), "--check"],
            text=True, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 2)

    def test_same_source_and_target_is_refused(self):
        r = subprocess.run(
            [sys.executable, os.path.join(self.src, "scripts", "sync_runtime.py"),
             "--to", self.src, "--check"],
            text=True, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 2)

    def test_ancestor_and_descendant_targets_are_refused(self):
        for target in (self.tmp.name, os.path.join(self.src, "scripts")):
            r = subprocess.run(
                [sys.executable, os.path.join(self.src, "scripts", "sync_runtime.py"),
                 "--to", target, "--check"],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(r.returncode, 2, target)
            self.assertIn("互为祖先/后代", r.stdout)

    def test_prune_does_not_delete_excluded_runtime_secrets(self):
        self.run_sync("--apply")
        self.write(self.dst, ".env.local", "RUNTIME_SECRET=1\n")
        self.write(self.dst, "assets/personal-asset-index.json", '{"real":"data"}\n')
        self.assertEqual(self.run_sync("--check").returncode, 0,
                         "--check 不应把排除文件算作漂移")
        self.assertEqual(self.run_sync("--apply", "--prune").returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.dst, ".env.local")))
        self.assertTrue(os.path.exists(
            os.path.join(self.dst, "assets/personal-asset-index.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
