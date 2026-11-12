#!/usr/bin/env python3
"""check-deliverables.py 的离线回归：只验机械一致性，不验设计判断。

fixture 用临时目录 + 最小 PNG（只改尾部字节制造不同指纹），不读仓库真实任务。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-deliverables.py"

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


class CheckDeliverablesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dw-deliv-")
        self.root = Path(self.tmp.name)
        self.task = self.root / "design-demos" / "t1"
        (self.task / "concepts" / "prompts").mkdir(parents=True)
        (self.task / "design-brief.md").write_text("# brief\n", encoding="utf-8")
        (self.task / "concept-prompts.md").write_text("# prompts\n", encoding="utf-8")
        self.concepts = {}
        for i, tag in enumerate(("A", "B", "C")):
            data = PNG_1PX + bytes([i + 1])
            path = self.task / "concepts" / f"{tag}.png"
            path.write_bytes(data)
            (self.task / "concepts" / "prompts" / f"{tag}.md").write_text(
                f"# {tag}\n", encoding="utf-8")
            self.concepts[tag] = data

    def tearDown(self):
        self.tmp.cleanup()

    # --- fixtures ---
    def sha(self, tag):
        import hashlib
        return hashlib.sha256(self.concepts[tag]).hexdigest()

    def write_concept_index(self, mutate=None, tags=("A", "B", "C")):
        data = {
            "task": "t1",
            "requested_size": "1x1",
            "concepts": [
                {
                    "id": tag,
                    "name": f"方向{tag}",
                    "file": f"design-demos/t1/concepts/{tag}.png",
                    "sha256": self.sha(tag),
                    "width": 1,
                    "height": 1,
                    "prompt_file": f"design-demos/t1/concepts/prompts/{tag}.md",
                }
                for tag in tags
            ],
        }
        if mutate:
            mutate(data)
        (self.task / "concept-index.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def write_direction(self, status="实施基线", exit_line="采用", extra="", tags=("A", "B", "C")):
        rows = "\n".join(
            f"| {tag} | design-demos/t1/concepts/{tag}.png | {self.sha(tag)} | 方向{tag} | 结构 |"
            for tag in tags
        )
        body = (
            "# 方向确认 · t1\n\n## 状态\n"
            f"- 状态：{status}\n"
            "- 生效范围：本任务阶段 2 起以此文件为目标方案依据\n"
            "- 被取代关系：无\n\n"
            "## 候选\n| id | 文件 | sha256 | 方向名 | 结构定位 |\n|---|---|---|---|---|\n"
            f"{rows}\n\n## 决策记录\n"
            f"- 决策出口：{exit_line}\n- 采用方向：A\n"
            + extra
        )
        (self.task / "direction-approved.md").write_text(body, encoding="utf-8")

    def write_brief(self, ids=("P1", "X6")):
        rows = "\n".join(f"| {i} | 页面 |" for i in ids)
        (self.task / "design-brief.md").write_text(
            "# brief\n\n| id | 标题 |\n|---|---|\n" + rows + "\n", encoding="utf-8")

    @staticmethod
    def coverage_items():
        return [
            {"id": "P1", "kind": "page", "title": "今日", "prototype": "rendered",
             "screens": ["p1-today"], "scales_rendered": ["1.0", "1.6"],
             "native": "done", "device": {"1.0": "pass", "1.6": "not-tested"},
             "notes": "1.6 未测：设备只有 1.0/1.45/1.6，待补"},
            {"id": "X6", "kind": "state", "title": "激励视频不可用",
             "prototype": "deferred-native", "screens": [],
             "defer_reason": "HTML 无法模拟广告 SDK 回调，原生用假配额驱动",
             "native_verify": True, "native": "todo", "device": {}},
        ]

    def write_coverage(self, items=None, mutate=None, schema="designwise-coverage/v1"):
        data = {
            "schema": schema,
            "scales": ["1.0", "1.3", "1.6", "2.0"],
            "items": items if items is not None else self.coverage_items(),
        }
        if mutate:
            mutate(data)
        (self.task / "coverage.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def run_check(self, *extra, stage="1", task=None):
        cmd = [sys.executable, str(SCRIPT), "--root", str(self.root),
               "--task-dir", str(task or self.task), "--stage", stage, "--json", *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc, json.loads(proc.stdout)

    def codes(self, data):
        return [e["code"] for e in data["errors"]] + [w["code"] for w in data["warnings"]]

    # --- cases ---
    def test_consistent_task_passes(self):
        self.write_concept_index()
        self.write_direction()
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["errors"], [])

    def test_sha_mismatch_is_reported(self):
        def mutate(data):
            data["concepts"][0]["sha256"] = "0" * 64
        self.write_concept_index(mutate)
        self.write_direction()
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("concept-sha-mismatch", self.codes(data))

    def test_missing_stage_artifact_is_reported(self):
        self.write_concept_index()
        self.write_direction()
        proc, data = self.run_check(stage="4")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing-artifact", self.codes(data))
    def test_duplicate_concepts_are_reported(self):
        # B 的图被换成与 A 逐字节相同：两个方向其实是一张图（声明的 sha 也随之改）
        (self.task / "concepts" / "B.png").write_bytes(self.concepts["A"])
        self.concepts["B"] = self.concepts["A"]
        self.write_concept_index()
        self.write_direction()
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("concept-duplicate", self.codes(data))

    def test_missing_status_is_warning_unless_strict(self):
        self.write_concept_index()
        self.write_direction(status="")
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertIn("direction-status-missing", self.codes(data))
        strict, strict_data = self.run_check("--strict")
        self.assertEqual(strict.returncode, 1)
        self.assertFalse(strict_data["ok"])

    def test_two_baselines_in_same_task_are_reported(self):
        """同一任务内的两条实施基线（含嵌套实验记录）互斥。"""
        self.write_concept_index()
        self.write_direction()
        nested = self.task / "experiments" / "r2"
        nested.mkdir(parents=True)
        (nested / "direction-approved.md").write_text(
            "# 方向确认 · t1/r2\n\n## 状态\n- 状态：实施基线\n", encoding="utf-8")
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("multiple-baselines", self.codes(data))

    def test_baselines_in_separate_tasks_do_not_conflict(self):
        """不同任务各自有实施基线是合法状态，不跨任务计数。"""
        self.write_concept_index()
        self.write_direction()
        other = self.root / "design-demos" / "t2"
        other.mkdir()
        (other / "direction-approved.md").write_text(
            "# 方向确认 · t2\n\n## 状态\n- 状态：实施基线\n", encoding="utf-8")
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertNotIn("multiple-baselines", self.codes(data))

    def test_fusion_without_integration_image_warns(self):
        self.write_concept_index()
        self.write_direction(exit_line="融合")
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertIn("direction-fusion-unverified", self.codes(data))

    def test_manifest_verification_is_delegated(self):
        self.write_concept_index()
        self.write_direction()
        (self.task / "asset-manifest.json").write_text("{}", encoding="utf-8")
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("manifest-verify-failed", self.codes(data))

    def test_manifest_is_optional_without_assets(self):
        """asset-manifest.json 是「有素材才必需」，没有素材不算缺项。"""
        self.write_concept_index()
        self.write_direction()
        (self.task / "prototype").mkdir()
        (self.task / "prototype" / "index.html").write_text("<html></html>", encoding="utf-8")
        (self.task / "prototype-notes.md").write_text("# notes\n", encoding="utf-8")
        proc, data = self.run_check(stage="3")
        self.assertEqual(proc.returncode, 0, data)
        self.assertNotIn("missing-artifact", self.codes(data))

    def test_skip_artifacts_allows_iteration_tasks(self):
        """局部迭代任务可以只校验已存在记录的绑定，不要求完整流程的全部产物。"""
        self.write_direction()
        proc, data = self.run_check("--skip-artifacts")
        self.assertEqual(proc.returncode, 0, data)
        self.assertNotIn("missing-artifact", self.codes(data))

    # --- 自适应方向数（V3：1-3 个，按分歧决定） ---
    def test_single_direction_is_accepted(self):
        self.write_concept_index(tags=("A",))
        self.write_direction(tags=("A",))
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertNotIn("concept-count", self.codes(data))

    # --- coverage.json（SKILL.md §6.3 / references/state-map.md §7） ---
    def test_valid_coverage_passes(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()
        self.write_coverage()
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertEqual(data["errors"], [])

    def test_coverage_schema_and_enums_are_checked(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()

        def mutate(data):
            data["schema"] = "coverage/v0"
            data["items"][0]["kind"] = "screen"
            data["items"][0]["prototype"] = "html"
            data["items"][0]["native"] = "wip"

        self.write_coverage(mutate=mutate)
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        codes = self.codes(data)
        for code in ("coverage-schema", "coverage-kind-invalid",
                     "coverage-prototype-invalid", "coverage-native-invalid"):
            self.assertIn(code, codes)

    def test_coverage_device_state_and_notes_are_checked(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()

        def mutate(data):
            data["items"][0]["device"] = {"1.0": "fail", "1.6": "maybe"}
            data["items"][0].pop("notes")

        self.write_coverage(mutate=mutate)
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        codes = self.codes(data)
        self.assertIn("coverage-device-invalid", codes)   # maybe 不是合法四态
        self.assertIn("coverage-notes-missing", codes)    # fail 必须有 notes

    def test_coverage_fail_notes_satisfied(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()

        def mutate(data):
            data["items"][0]["device"] = {"1.0": "fail"}
            data["items"][0]["notes"] = "1.0 下步数卡溢出：已开缺陷，待修后复验"

        self.write_coverage(mutate=mutate)
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertNotIn("coverage-notes-missing", self.codes(data))

    def test_deferred_native_requires_reason_and_verify(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()

        def mutate(data):
            item = data["items"][1]
            item.pop("defer_reason")
            item.pop("native_verify")

        self.write_coverage(mutate=mutate)
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        codes = self.codes(data)
        self.assertIn("coverage-defer-reason-missing", codes)
        self.assertIn("coverage-defer-verify-missing", codes)

    def test_coverage_id_set_must_match_map(self):
        self.write_brief(("P1", "P2"))
        self.write_concept_index()
        self.write_direction()
        self.write_coverage()                       # 含 P1、X6
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        codes = self.codes(data)
        self.assertIn("coverage-id-missing", codes)   # P2 在地图里消失
        self.assertIn("coverage-id-unmapped", codes)  # X6 不在 map 里

    def test_rendered_requires_screen_names(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()

        def mutate(data):
            data["items"][0]["screens"] = []

        self.write_coverage(mutate=mutate)
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("coverage-screens-missing", self.codes(data))

    def test_coverage_missing_is_warning_when_map_exists(self):
        """地图有 id 但无 coverage.json：整机/多页面必需，但局部迭代可忽略 → warning。"""
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertIn("coverage-missing", self.codes(data))

    def test_unknown_scale_only_warns(self):
        self.write_brief(("P1", "X6"))
        self.write_concept_index()
        self.write_direction()

        def mutate(data):
            data["items"][0]["device"]["1.45"] = "pass"

        self.write_coverage(mutate=mutate)
        proc, data = self.run_check()
        self.assertEqual(proc.returncode, 0, data)
        self.assertIn("coverage-scale-unknown", self.codes(data))


if __name__ == "__main__":
    unittest.main()
