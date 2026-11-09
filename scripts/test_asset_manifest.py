#!/usr/bin/env python3
"""test_asset_manifest.py — asset_manifest.py 的行为测试（纯本地，无网络）。

覆盖：登记（含 sha256 / 变体 / 消费者）、缺文件拒绝、重复 id 更新而非追加、
verify 的通过 / hash 不符 / 缺字段 / 缺文件 / 缺变体 / temp 拦截 / 消费者告警与
严格模式、list 过滤、用法错误退出码。

运行：python3 scripts/test_asset_manifest.py
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import asset_manifest as am  # noqa: E402

# 最小合法 PNG（1x1 透明），不依赖 Pillow。
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class ManifestTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.manifest = os.path.join(self.root, "asset-manifest.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, data=PNG_1PX):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = am.main(list(argv))
            except SystemExit as exc:
                # 与 Python 语义一致：字符串参数打印到 stderr 并以 1 退出。
                if isinstance(exc.code, str):
                    err.write(exc.code + "\n")
                    code = 1
                else:
                    code = exc.code if isinstance(exc.code, int) else 2
        return code, out.getvalue(), err.getvalue()

    def register(self, *extra, **kw):
        argv = ["register", "--manifest", self.manifest]
        argv += ["--file", kw.pop("file", "assets/images/hero.png"),
                 "--id", kw.pop("id", "hero-home"),
                 "--type", kw.pop("type", "illustration"),
                 "--source", kw.pop("source", "generated"),
                 "--license", kw.pop("license", "project-owned")]
        for key, value in kw.items():
            flag = "--" + key.replace("_", "-")
            if isinstance(value, list):
                for item in value:
                    argv += [flag, item]
            elif value is not None:
                argv += [flag, str(value)]
        return self.run_cli(*(argv + list(extra)))

    def load(self):
        with open(self.manifest, encoding="utf-8") as fh:
            return json.load(fh)


class RegisterTests(ManifestTestBase):
    def test_01_register_computes_sha256_and_metadata(self):
        path = self.write("assets/images/hero.png")
        self.write("assets/images/hero@2x.png")
        code, out, _ = self.register(
            consumer=["prototype/index.html", "android:home"],
            variant=["assets/images/hero@2x.png"],
            model="gpt-image-2.5",
            prompt_file="concept-prompts.md",
            task="homepage redesign",
        )
        self.assertEqual(code, 0, out)
        self.assertIn("registered hero-home", out)
        data = self.load()
        self.assertEqual(data["task"], "homepage redesign")
        entry = data["assets"][0]
        self.assertEqual(entry["id"], "hero-home")
        self.assertEqual(entry["status"], "final")
        self.assertEqual(entry["consumers"], ["prototype/index.html", "android:home"])
        self.assertEqual(entry["provenance"]["model"], "gpt-image-2.5")
        self.assertEqual(entry["provenance"]["prompt_file"], "concept-prompts.md")
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertEqual(entry["variants"][0]["file"], "assets/images/hero@2x.png")
        self.assertEqual(len(entry["variants"][0]["sha256"]), 64)
        self.assertTrue(os.path.isfile(path))

    def test_02_register_rejects_missing_file(self):
        code, _, err = self.register(file="assets/images/missing.png")
        self.assertEqual(code, 1)
        self.assertIn("file not found", err)
        self.assertFalse(os.path.exists(self.manifest))

    def test_03_register_rejects_missing_variant(self):
        self.write("assets/images/hero.png")
        code, _, err = self.register(variant=["assets/images/hero@2x.png"])
        self.assertEqual(code, 1)
        self.assertIn("variant not found", err)

    def test_04_same_id_updates_instead_of_appending(self):
        self.write("assets/images/hero.png")
        self.assertEqual(self.register()[0], 0)
        self.write("assets/images/hero.png", PNG_1PX + b"\x00")
        code, out, _ = self.register(model="gpt-image-2.5")
        self.assertEqual(code, 0)
        self.assertIn("updated hero-home", out)
        self.assertEqual(len(self.load()["assets"]), 1)

    def test_05_second_asset_is_added(self):
        self.write("assets/images/hero.png")
        self.write("assets/images/empty.png")
        self.assertEqual(self.register()[0], 0)
        self.assertEqual(self.register(id="empty-state", file="assets/images/empty.png")[0], 0)
        ids = [a["id"] for a in self.load()["assets"]]
        self.assertEqual(sorted(ids), ["empty-state", "hero-home"])


class VerifyTests(ManifestTestBase):
    def test_01_clean_manifest_passes(self):
        self.write("assets/images/hero.png")
        self.write("prototype/index.html", b"<html></html>")
        self.register(consumer=["prototype/index.html"])
        code, out, err = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 0, out + err)
        self.assertIn('"hashes_checked": 1', out)
        self.assertIn("OK:", err)

    def test_02_hash_mismatch_fails(self):
        path = self.write("assets/images/hero.png")
        self.register()
        with open(path, "wb") as fh:
            fh.write(PNG_1PX + b"tampered")
        code, out, err = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("sha256 mismatch", out)
        self.assertIn("FAIL:", err)

    def test_03_missing_file_fails(self):
        self.write("assets/images/hero.png")
        self.register()
        os.remove(os.path.join(self.root, "assets/images/hero.png"))
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("file missing", out)

    def test_04_missing_variant_fails(self):
        self.write("assets/images/hero.png")
        self.write("assets/images/hero@2x.png")
        self.register(variant=["assets/images/hero@2x.png"])
        os.remove(os.path.join(self.root, "assets/images/hero@2x.png"))
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("variant missing", out)

    def test_05_temp_status_blocks_unless_allowed(self):
        self.write("assets/images/hero.png")
        self.register(status="temp")
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("status=temp cannot ship", out)

        code, out, err = self.run_cli("verify", "--manifest", self.manifest, "--allow-temp")
        self.assertEqual(code, 0, out + err)

    def test_06_missing_required_field_fails(self):
        self.write("assets/images/hero.png")
        self.register()
        data = self.load()
        data["assets"][0]["license"] = ""
        with open(self.manifest, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("missing fields license", out)

    def test_07_duplicate_id_fails(self):
        self.write("assets/images/hero.png")
        self.register()
        data = self.load()
        data["assets"].append(dict(data["assets"][0]))
        with open(self.manifest, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("duplicate id", out)

    def test_08_invalid_status_fails(self):
        self.write("assets/images/hero.png")
        self.register()
        data = self.load()
        data["assets"][0]["status"] = "draft"
        with open(self.manifest, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("invalid status", out)

    def test_09_missing_consumer_is_warning_by_default(self):
        self.write("assets/images/hero.png")
        self.register(consumer=["prototype/gone.html"])
        code, out, err = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 0, out + err)
        self.assertIn("consumer not found", out)
        self.assertIn("OK:", err)

    def test_10_strict_consumers_makes_it_an_error(self):
        self.write("assets/images/hero.png")
        self.register(consumer=["prototype/gone.html"])
        code, out, _ = self.run_cli("verify", "--manifest", self.manifest, "--strict-consumers")
        self.assertEqual(code, 1)
        self.assertIn("consumer not found", out)

    def test_11_platform_consumer_scheme_is_not_a_path(self):
        self.write("assets/images/hero.png")
        self.register(consumer=["android:home", "ios:HomeView", "web:landing", "native:card"])
        code, out, err = self.run_cli("verify", "--manifest", self.manifest,
                                      "--strict-consumers")
        self.assertEqual(code, 0, out + err)

    def test_12_missing_manifest_fails(self):
        code, _, err = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("manifest not found", err)

    def test_13_empty_manifest_passes(self):
        with open(self.manifest, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "task": "", "updated_at": "", "assets": []}, fh)
        code, out, err = self.run_cli("verify", "--manifest", self.manifest)
        self.assertEqual(code, 0, out + err)
        self.assertIn('"assets": 0', out)


class ListTests(ManifestTestBase):
    def setUp(self):
        super().setUp()
        self.write("assets/images/hero.png")
        self.write("assets/icons/mark.png")
        self.register()
        self.register(id="brand-mark", file="assets/icons/mark.png", type="icon",
                      source="vector", consumer=["android:home"])

    def test_01_list_all(self):
        code, out, _ = self.run_cli("list", "--manifest", self.manifest)
        self.assertEqual(code, 0)
        self.assertIn("hero-home", out)
        self.assertIn("brand-mark", out)

    def test_02_filter_by_type(self):
        code, out, _ = self.run_cli("list", "--manifest", self.manifest, "--type", "icon")
        self.assertEqual(code, 0)
        self.assertIn("brand-mark", out)
        self.assertNotIn("hero-home", out)

    def test_03_filter_by_consumer(self):
        code, out, _ = self.run_cli("list", "--manifest", self.manifest,
                                    "--consumer", "android:home")
        self.assertEqual(code, 0)
        self.assertIn("brand-mark", out)
        self.assertNotIn("hero-home", out)

    def test_04_json_output(self):
        code, out, _ = self.run_cli("list", "--manifest", self.manifest, "--json")
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], "hero-home")


class UsageTests(ManifestTestBase):
    def test_01_missing_subcommand_is_usage_error(self):
        code, _, err = self.run_cli()
        self.assertEqual(code, 2)

    def test_02_invalid_manifest_shape_is_rejected(self):
        with open(self.manifest, "w", encoding="utf-8") as fh:
            json.dump(["not", "an", "object"], fh)
        code, _, err = self.run_cli("list", "--manifest", self.manifest)
        self.assertEqual(code, 1)
        self.assertIn("invalid manifest", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
