#!/usr/bin/env python3
"""test_sync_runtime.py — sync_runtime.py 的检查/写入/prune 行为测试。

运行：python3 scripts/test_sync_runtime.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "sync_runtime.py")


def load_sync_module():
    """加载真实实现（不是复刻判定逻辑），用于直接断言 skip_file / manifest。"""
    spec = importlib.util.spec_from_file_location("sync_runtime_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_file(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


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


class SyncExclusionContractTests(unittest.TestCase):
    """分发边界：开发资产不进入运行时副本；运行资产与 LICENSE 照常同步。"""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_sync_module()

    def run_sync(self, src, dst, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, "--to", dst, "--force"] + list(args),
            text=True, capture_output=True, timeout=30,
        )

    def test_root_agents_md_is_excluded(self):
        self.assertTrue(self.mod.skip_file("AGENTS.md"))

    def test_scripts_dev_tests_are_excluded(self):
        for rel in ("scripts/test_x.py", "scripts/test_sync_runtime.py",
                    "scripts/test_design_gate_hook_hyperframes.py"):
            self.assertTrue(self.mod.skip_file(rel), rel)

    def test_runtime_scripts_are_not_excluded(self):
        for rel in ("scripts/design-gate-check.js", "scripts/sync_runtime.py",
                    "scripts/verify.py", "scripts/check-skill.py",
                    "scripts/design-gate-hook-hyperframes.sh"):
            self.assertFalse(self.mod.skip_file(rel), rel)

    def test_license_and_docs_are_not_excluded(self):
        for rel in ("LICENSE", "SKILL.md", "README.md", "README.en.md",
                    "SECURITY.md", "references/verification.md"):
            self.assertFalse(self.mod.skip_file(rel), rel)

    def test_same_name_outside_the_two_paths_is_not_excluded(self):
        # 只排除根目录 AGENTS.md 与 scripts/ 直接子文件 test_*.py
        for rel in ("references/AGENTS.md", "scripts/cloud/test_x.py",
                    "demos/test_x.py", "assets/test_x.py", "scripts/test_x.js"):
            self.assertFalse(self.mod.skip_file(rel), rel)

    def test_manifest_omits_dev_assets_and_keeps_runtime_files(self):
        with tempfile.TemporaryDirectory(prefix="sync_manifest_") as tmp:
            src = os.path.join(tmp, "src")
            write_file(src, "SKILL.md", "---\nname: designwise\n---\n")
            write_file(src, "LICENSE", "MIT\n")
            write_file(src, "AGENTS.md", "rules\n")
            write_file(src, "scripts/verify.py", "print(1)\n")
            write_file(src, "scripts/test_verify_status.py", "pass\n")
            m = self.mod.manifest(src)
            self.assertNotIn("AGENTS.md", m)
            self.assertNotIn("scripts/test_verify_status.py", m)
            self.assertIn("LICENSE", m)
            self.assertIn("SKILL.md", m)
            self.assertIn("scripts/verify.py", m)

    def test_host_workspace_dir_is_excluded(self):
        """`.zcode/` 是宿主工作区（会话计划/命令/本地 skill），不得随分发。"""
        self.assertTrue(self.mod.skip_dir(".zcode"))
        with tempfile.TemporaryDirectory(prefix="sync_zcode_") as tmp:
            src = os.path.join(tmp, "src")
            write_file(src, "SKILL.md", "---\nname: designwise\n---\n")
            write_file(src, "scripts/verify.py", "print(1)\n")
            write_file(src, ".zcode/plans/plan-sess_123.md", "会话计划\n")
            write_file(src, ".zcode/settings.json", "{}\n")
            write_file(src, ".zcode/skills/local/SKILL.md", "local skill\n")
            m = self.mod.manifest(src)
            self.assertEqual([k for k in m if k.startswith(".zcode/")], [],
                             f".zcode/ 下的内容不得进入同步清单：{sorted(m)}")
            self.assertIn("SKILL.md", m)
            self.assertIn("scripts/verify.py", m)

    def test_apply_does_not_write_host_workspace_dir(self):
        with tempfile.TemporaryDirectory(prefix="sync_zcode_apply_") as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            write_file(src, "SKILL.md", "---\nname: designwise\n---\n")
            write_file(src, "scripts/verify.py", "print(1)\n")
            write_file(src, ".zcode/plans/plan-sess_123.md", "会话计划\n")
            os.makedirs(dst)
            r = self.run_sync(src, dst, "--apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertFalse(os.path.exists(os.path.join(dst, ".zcode")),
                             ".zcode/ 不得写入运行时副本")
            self.assertTrue(os.path.isfile(os.path.join(dst, "scripts", "verify.py")))
            self.assertEqual(self.run_sync(src, dst, "--check").returncode, 0)

    def test_legacy_dev_assets_in_target_are_invisible_and_survive_prune(self):
        """排除生效前已在副本里的开发资产：不报漂移、不被 --prune 删除（清理需单独授权）。"""
        with tempfile.TemporaryDirectory(prefix="sync_legacy_") as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            write_file(src, "SKILL.md", "---\nname: designwise\n---\n")
            write_file(src, "LICENSE", "MIT\n")
            write_file(src, "scripts/verify.py", "print(1)\n")
            write_file(src, "AGENTS.md", "rules\n")
            write_file(src, "scripts/test_a.py", "pass\n")
            os.makedirs(dst)
            write_file(dst, "AGENTS.md", "old rules\n")
            write_file(dst, "scripts/test_legacy.py", "pass\n")

            r = self.run_sync(src, dst, "--apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            # 目标里预置的 AGENTS.md 是"历史遗留"：同步不得写入、也不得覆盖它
            with open(os.path.join(dst, "AGENTS.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "old rules\n",
                                 "AGENTS.md 不得被源仓库版本覆盖")
            self.assertFalse(os.path.exists(os.path.join(dst, "scripts", "test_a.py")),
                             "开发测试文件不得写入副本")
            self.assertTrue(os.path.exists(os.path.join(dst, "LICENSE")),
                            "LICENSE 必须随分发")
            self.assertTrue(os.path.exists(os.path.join(dst, "scripts", "verify.py")),
                            "运行所需脚本必须照常同步")

            r = self.run_sync(src, dst, "--check")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("一致", r.stdout)

            r = self.run_sync(src, dst, "--apply", "--prune")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(os.path.exists(os.path.join(dst, "scripts", "test_legacy.py")),
                            "排除文件不得被 --prune 删除")
            self.assertTrue(os.path.exists(os.path.join(dst, "AGENTS.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
