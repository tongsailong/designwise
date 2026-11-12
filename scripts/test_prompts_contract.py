#!/usr/bin/env python3
"""test_prompts_contract.py — test-prompts.json（人工验收清单）的口径契约测试。

这份清单是人工/会话内逐条执行的断言集，没有运行期执行器，因此结构或口径漂移
不会自己报错。本文件只校验「它能被解析、字段完整、ID 唯一、不残留已废止的旧流程
表述、阶段与文件引用可解析、V3 核心验收场景仍在」，防止清单随流程演进静默过期。

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

# 已废止的旧体系表述：任务分层、固定三方向、远程裁决通道、已删除的文档与脚本。
DEPRECATED = (
    "L1 四步",
    "L2",
    "L3",
    "单一最佳方案",
    "恰好 3 个方向",
    "三张真实图片",
    "失败关闭六条件",
    "不重新探索三个方向",
    "生图前预审",
    "预审不选方向",
    "Copilot 裁决",
    "CONSULT",
    "call_gpt",
    "bridge_evidence",
    "阶段 7",
    "0–7",
    "G7",
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
    "页面-状态地图": "页面-状态地图",
    "稳定 id 与三类对象": "稳定 id",
    "出处到 file:line": "file:line",
    "文档规则与 UI 冲突待决": "文档规则 ≠ UI 路径",
    "产品三问": "产品三问",
    "原生可行性前置": "原生可行性前置检查",
    "范围冻结": "范围冻结",
    "方向数按分歧决定": "按实质分歧决定",
    "单方向最优": "1 个最优方向",
    "两到三方向": "2–3 个",
    "全部拒绝并重做": "全部拒绝",
    "不为展示造 A/B/C": "不为展示选项制造 A/B/C",
    "差异在结构层": "结构层",
    "方向卡 form 归属": "form 来自产品的哪里",
    "产品独有结构隐喻": "产品独有的结构隐喻",
    "提示词任务块": "任务块",
    "原则转译块": "原则转译块",
    "共用块逐字相同": "逐字相同",
    "差异实测脚本": "direction_divergence.py",
    "脚本只给事实": "脚本只给事实",
    "失败关闭": "失败关闭",
    "失败不进原型": "不得进入原型",
    "ZCode 设计决策主体": "ZCode 原生 Agent",
    "不把设计裁决外置": "不把设计裁决外置",
    "三出口": "采用 / 融合 / 全部拒绝",
    "记录机会成本": "机会成本",
    "局部迭代": "局部迭代",
    "实质变化重走": "实质变化",
    "融合统一逻辑": "统一信息层级",
    "拼图不是融合": "拼图不是融合",
    "概念图不是 UI 真相": "概念图不是 UI 真相",
    "交互真实": "交互与状态必须真实",
    "延迟到原生": "deferred-native",
    "覆盖不静默消失": "不得静默消失",
    "覆盖 id 集合": "coverage.json",
    "缩放矩阵": "1.0/1.3/1.6/2.0",
    "浏览器 zoom 不算": "浏览器 zoom",
    "真实素材": "真实素材",
    "先复用再生成": "先复用再生成",
    "素材三态": "素材三态",
    "临时素材拦截": "status=temp",
    "cover 不等于 CENTER_CROP": "CENTER_CROP",
    "触控 48dp": "48dp",
    "生图不可用时诚实暂停": "不得用 HTML/CSS/SVG",
    "组件等价映射": "组件等价",
    "禁用替代": "禁用替代",
    "绘制层级": "绘制层级",
    "滚动与可达": "滚动与可达",
    "业务规则出处": "业务规则出处",
    "token 换肤不算落地": "token 换肤",
    "三方对照": "三方对照",
    "真机装包入口": "adb-auto-install.sh",
    "验收四态": "NOT TESTED",
    "工程与设计双验收": "两项都达标才算整体通过",
    "测试能力边界": "测试能力边界",
    "范围边界": "只做 App UI",
    "产品原则顺序": "有用 → 好懂 → 舒服 → 有意义",
    "游戏化可选": "游戏化是手段不是目标",
    "设计自由度": "设计自由度",
    "品牌资产不猜": "不猜品牌色",
    "复杂度转嫁评审": "复杂度转嫁",
    "六维评审": "六维",
    "App 三项附加检查": "App 三项附加检查",
    "打磨环": "打磨环",
    "一轮三处": "最伤的三处",
    "机械通过不等于设计通过": "机械通过不等于设计通过",
}

# 阶段编号：V3 只有 0–6 七个阶段，SKILL.md 的流程表是唯一权威。
STAGES = {"0", "1", "2", "3", "4", "5", "6"}

# coverage.json 枚举必须在清单、SKILL.md 与校验脚本三处一致。
COVERAGE_PROTOTYPE = ("rendered", "deferred-native", "not-applicable")
COVERAGE_DEVICE = ("pass", "fail", "not-tested", "not-applicable")


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
        cls.blob = " ".join(e["expected"] + " " + e["tests"] for e in cls.entries)

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

    def test_04_direction_count_is_divergence_driven(self):
        # V3 方向数是设计判断，不得写回「固定 3 个」；同时必须保留自适应与拒绝出口。
        self.assertTrue("按实质分歧决定" in self.blob, "缺少方向数自适应判据")
        self.assertTrue("不为展示选项制造 A/B/C" in self.blob, "缺少反凑数判据")
        self.assertTrue("全部拒绝" in self.blob, "缺少全部拒绝出口")
        blocks = re.findall(r"[^。；\n]*\d+ 个方向[^。；\n]*", self.blob)
        for block in blocks:
            self.assertNotIn("恰好", block, "方向数量被写死：%r" % block)
            for weak in ("可以不做", "可选", "按需生成方向", "不强制"):
                self.assertNotIn(weak, block, "方向被写成可选：%r" % block)

    def test_05_stage_references_resolve(self):
        defined = stage_numbers_in_skill(self.skill)
        self.assertEqual(defined, STAGES,
                         "SKILL.md 流程表阶段编号不是 0–6：%s" % sorted(defined))
        for ref in sorted(set(re.findall(r"阶段\s*(\d)", self.blob))):
            self.assertIn(ref, STAGES, "引用了不存在的阶段「阶段 %s」" % ref)

    def test_06_file_references_resolve(self):
        pattern = r"(?:references|assets|scripts)/[\w./-]+\.(?:md|jsx|py|mjs)"
        refs = set(re.findall(pattern, self.blob))
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

    def test_09_coverage_vocabulary_matches_skill(self):
        # 清单、SKILL.md、校验脚本的 coverage 枚举必须一致，否则覆盖判据会各说各话。
        # 清单里验收状态写成大写/空格形式（PASS / NOT TESTED），比对前统一成枚举拼写。
        blob = (self.blob.lower()
                .replace("not tested", "not-tested")
                .replace("not applicable", "not-applicable"))
        for value in COVERAGE_PROTOTYPE + COVERAGE_DEVICE:
            self.assertIn(value, self.skill, "SKILL.md 缺少 coverage 枚举 %s" % value)
            self.assertIn(value, blob, "验收清单缺少 coverage 枚举 %s" % value)
        self.assertIn("designwise-coverage/v1", self.skill, "SKILL.md 缺少 schema 标识")

    def test_10_decision_is_not_outsourced(self):
        # 设计裁决不得外置；治理层只做状态与证据。
        self.assertIn("只做任务治理", self.blob)
        self.assertIn("不把设计裁决外置", self.blob)
        for entry in self.entries:
            for phrase in ("由 Copilot 决定", "等待远程模型", "SOL 裁决"):
                self.assertNotIn(phrase, entry["expected"] + entry["tests"],
                                 "id=%s 把设计裁决外置" % entry["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
