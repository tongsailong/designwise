#!/usr/bin/env python3
"""test_prompts_contract.py — test-prompts.json（人工验收清单）的口径契约测试。

这份清单是人工/会话内逐条执行的断言集，没有运行期执行器，因此结构或口径漂移
不会自己报错。本文件只校验「它能被解析、字段完整、ID 唯一、不残留已废止的旧流程
表述、阶段引用与文件引用可解析、核心验收场景仍在」，防止清单随流程演进静默过期。

它锁结构与字面，不判断语义；措辞是否仍准确表达新流程由人工验收与独立复核确认。

运行：python3 scripts/test_prompts_contract.py
"""

import json
import os
import re
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROMPTS = os.path.join(ROOT, "test-prompts.json")
SKILL = os.path.join(ROOT, "SKILL.md")

KEYS = {"id", "prompt", "expected", "tests"}

# 已废止的旧体系表述：任务分层、默认单一方案、已删除的文档与脚本。
DEPRECATED = (
    "L1 四步",
    "L2",
    "L3",
    "单一最佳方案",
    "gpt-visual-workflow.md",
    "direction-gpt-path.md",
    "materials.md",
    "ui-demo-animation.md",
    "storyboard-basics.md",
    "launch-film-director-notes.md",
    "check-assets.py",
    "design-gate",
    "hyperframes",
    "deck_index",
    "render-video.js",
    "export_deck",
    "html2pptx",
)

# 核心场景必须仍被覆盖：用该场景特有的判据短语，且必须出现在**某一条目自身的
# expected** 里，避免用泛词在别处蹭到。
REQUIRED_COVERAGE = {
    "三方向结构性差异": "恰好 3 个方向",
    "Copilot 基于真实像素裁决": "三张真实图片",
    "失败关闭": "失败关闭五条件",
    "局部迭代不重跑方向": "不重新探索三个方向",
    "实质变化重新探索": "实质变化",
    "先复用再生成": "先复用再生成",
    "素材清单": "asset-manifest.json",
    "临时素材拦截": "status=temp",
    "生图不可用时诚实暂停": "拒绝 SVG 冒充",
    "原生 dp 与触控": "48dp",
    "真机装包入口": "adb-auto-install.sh",
    "验收三态": "PARTIAL",
    "范围边界": "只做 App UI",
    "产品原则顺序": "有用 → 好懂 → 舒服 → 有意义",
    "游戏化可选": "游戏化是可选手段",
    "设计自由度": "设计自由度",
    "品牌资产不猜": "不猜品牌色",
    "复杂度转嫁评审": "复杂度转嫁",
}

# 阶段编号：新流程只有 0–7 八个阶段，SKILL.md 的流程表是唯一权威。
STAGES = {"0", "1", "2", "3", "4", "5", "6", "7"}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_prompts():
    with open(PROMPTS, encoding="utf-8") as fh:
        return json.load(fh)


def stage_numbers_in_skill(skill):
    """从 SKILL.md 的流程表取阶段编号，作为引用的落点。"""
    return set(re.findall(r"^\| \*\*(\d) ", skill, re.M))


class PromptsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = load_prompts()
        cls.skill = read(SKILL)

    def test_01_schema_is_unchanged(self):
        self.assertIsInstance(self.entries, list)
        self.assertGreaterEqual(len(self.entries), 20, "验收场景数量不足")
        for entry in self.entries:
            self.assertEqual(set(entry), KEYS, "id=%s 字段集变化" % entry.get("id"))
            for key in ("prompt", "expected", "tests"):
                self.assertIsInstance(entry[key], str)
                self.assertTrue(entry[key].strip(), "id=%s %s 为空" % (entry["id"], key))
            self.assertGreaterEqual(len(entry["expected"]), 60,
                                    "id=%s expected 过短" % entry["id"])
            self.assertGreaterEqual(len(entry["tests"]), 20,
                                    "id=%s tests 过短" % entry["id"])

    def test_02_ids_unique_and_contiguous(self):
        ids = [entry["id"] for entry in self.entries]
        self.assertTrue(all(isinstance(i, int) for i in ids), "id 必须是整数")
        self.assertEqual(len(set(ids)), len(ids), "id 重复：%s" % ids)
        self.assertEqual(ids, list(range(1, len(ids) + 1)), "id 应从 1 连续编号")

    def test_03_no_deprecated_flow_wording(self):
        # 只扫 expected + tests；prompt 是对抗性提问或反例，允许出现旧词。
        for entry in self.entries:
            blob = entry["expected"] + " " + entry["tests"]
            for phrase in DEPRECATED:
                self.assertNotIn(phrase, blob,
                                 "id=%s 残留废止表述《%s》" % (entry["id"], phrase))

    def test_04_three_directions_are_mandatory_not_optional(self):
        blob = " ".join(e["expected"] + " " + e["tests"] for e in self.entries)
        blocks = re.findall(r"[^。；\n]*3 个方向[^。；\n]*", blob)
        self.assertTrue(blocks, "清单里没有任何条目要求 3 个方向")
        for block in blocks:
            # 「3 个方向」不得被写成可选 / 按需 / 默认不做
            for weak in ("可以不做", "可选", "按需生成方向", "不强制"):
                self.assertNotIn(weak, block, "3 个方向被写成可选：%r" % block)

    def test_05_stage_references_resolve(self):
        defined = stage_numbers_in_skill(self.skill)
        self.assertEqual(defined, STAGES,
                         "SKILL.md 流程表阶段编号不是 0–7：%s" % sorted(defined))
        blob = " ".join(e["expected"] + " " + e["tests"] for e in self.entries)
        for ref in sorted(set(re.findall(r"阶段\s*(\d)", blob))):
            self.assertIn(ref, STAGES, "引用了不存在的阶段「阶段 %s」" % ref)

    def test_06_file_references_resolve(self):
        blob = " ".join(e["expected"] + " " + e["tests"] for e in self.entries)
        pattern = r"(?:references|assets|scripts)/[\w./-]+\.(?:md|jsx|py|mjs)"
        refs = set(re.findall(pattern, blob))
        self.assertTrue(refs, "清单没有引用任何实际文件")
        for rel in sorted(refs):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)),
                            "引用了不存在的文件：%s" % rel)

    def test_07_required_scenarios_still_covered(self):
        for name, phrase in REQUIRED_COVERAGE.items():
            self.assertTrue(
                any(phrase in e["expected"] for e in self.entries),
                "缺少验收场景：%s（找不到判据短语「%s」）" % (name, phrase),
            )

    def test_08_lists_out_of_scope_without_building_it(self):
        entry = next(e for e in self.entries if "幻灯片" in e["prompt"])
        self.assertIn("不在范围内", entry["expected"])
        self.assertIn("视频", entry["expected"])
        self.assertIn("生产级 Web App", entry["expected"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
