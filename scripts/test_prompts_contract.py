#!/usr/bin/env python3
"""test_prompts_contract.py — test-prompts.json（人工验收清单）的口径契约测试。

这份清单是人工/会话内逐条执行的断言集，没有运行期执行器，因此结构或口径漂移不会自己报错。
本文件只校验「它能被解析、字段完整、ID 唯一、不残留已废止的方向规则与默认多方向写法、
章节引用可解析、核心验收场景仍在」，防止清单随规则演进而静默过期。
它锁结构与字面，不判断语义；措辞是否仍表达「默认一个最佳方案」由人工验收与复核确认。

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
WORKFLOW = os.path.join(ROOT, "references", "gpt-visual-workflow.md")
HANDOFF = os.path.join(ROOT, "references", "design-handoff.md")
SKILL = os.path.join(ROOT, "SKILL.md")

KEYS = {"id", "prompt", "expected", "tests"}

# 已废止的方向规则：生图前自动定向/自动融合、默认铺满 2~3 个方向、旧出图脚本名
DEPRECATED = (
    "自动决策",
    "自动单选",
    "自动定向",
    "自动融合",
    "三方向",
    "2~3 组候选方案卡",
    "生图前的评审与选择不停轮",
    "gen_via_cpa",
)

# 已废止的「默认多方向」写法（规范化去空格后逐条比对）。
# 这里刻意只锁字面：短语级语义判断在历次复核里反复把正当写法（「同一方向下交付
# 2–3 个页面」「不排除存在实质分歧时」）判成违规，误伤成本高于收益。语义层面的
# 「这句话是否把多方向当默认」由人工逐条验收与独立复核承担。
BANNED_DEFAULT = (
    "默认2–3个方向",
    "默认2~3个方向",
    "默认3个方向",
    "默认三个方向",
    "默认多方向",
    "默认生成2~3组",
    "默认给2–3个方向",
    "默认给3个方向",
    "默认出2~3个方向",
    "默认出3个方向",
    "每次都给3个方向",
    "每次都生成3个方向",
    "每次都出3个方向",
    "一律给2–3个方向",
    "一律给3个方向",
    "常规流程也备3个方向",
    "直接铺2–3个方向",
)

# 权威句式：默认口径必须与升级条件成对出现，缺一即判错。
DEFAULT_CLAUSE = ("默认", "1个方向")
ESCALATION = ("用户明确要求",)  # 另加「2–3 个」区间，连字符写法不限
ESCALATION_RANGE = re.compile(r"2[–~\-—]3个")

# 必须一直有验收场景覆盖的核心原则：每条用该场景特有的判据短语，
# 必须能在**某一条目自身的 expected** 里找到，避免用泛词在别处蹭到。
REQUIRED_COVERAGE = {
    "默认单一最佳方案": "不自动铺 2–3 个",
    "一个方向的完整多页交付": "方向数量与交付物数量无关",
    "多尺寸与组件变体": "同一个设计方向",
    "真实设计分歧": "真实设计分歧",
    "用户明确要求多方向": "按用户给的数量执行",
    "设计自由度": "不机械继承",
    "商业与变现边界": "不得更改商业机制本身",
    "真实视觉证据": "不得伪造截图",
}


def load_prompts():
    with open(PROMPTS, encoding="utf-8") as fh:
        return json.load(fh)


def squeeze(text):
    """去掉半角/全角空格，避免字面比对被排版差异左右。"""
    return re.sub(r"[ \u3000]+", "", text)


def numbered_sections(*paths):
    """收集多份文档的编号标题（清单里的 §x 可能指向 workflow 或 design-handoff）。"""
    sections = set()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # 同时收 §1.a 这类「数字.字母」编号（SKILL.md 的核心资产协议）
        sections |= set(
            re.findall(r"^#{2,4}\s+(?:\*\*)?(\d+(?:\.\d+)*(?:\.[a-z])?)", text, re.M)
        )
    return sections


class PromptsContractTests(unittest.TestCase):
    def setUp(self):
        self.entries = load_prompts()

    def test_01_schema_is_unchanged(self):
        self.assertIsInstance(self.entries, list)
        self.assertGreaterEqual(len(self.entries), 8, "验收场景数量不足")
        for entry in self.entries:
            self.assertEqual(set(entry), KEYS, f"id={entry.get('id')} 字段集变化")
            for key in ("prompt", "expected", "tests"):
                self.assertIsInstance(entry[key], str)
                self.assertTrue(entry[key].strip(), f"id={entry['id']} {key} 为空")
            # 判据与断言摘要都要有实质内容，避免空壳条目占位
            self.assertGreaterEqual(len(entry["expected"]), 60, f"id={entry['id']} expected 过短")
            self.assertGreaterEqual(len(entry["tests"]), 20, f"id={entry['id']} tests 过短")

    def test_02_ids_unique_and_contiguous(self):
        ids = [entry["id"] for entry in self.entries]
        self.assertTrue(all(isinstance(i, int) for i in ids), "id 必须是整数")
        self.assertEqual(len(set(ids)), len(ids), f"id 重复：{ids}")
        self.assertEqual(ids, list(range(1, len(ids) + 1)), "id 应从 1 连续编号")

    def test_03_no_deprecated_direction_rules(self):
        # 扫 expected + tests（判据与断言摘要都不许残留废止表述）；不扫 prompt，
        # 因为 prompt 本身就是对抗性提问或反例（如「能不能自动融合？」）。
        # 现状零命中属预期：这是防回归的守卫，不是对现存内容的体检。
        for entry in self.entries:
            blob = entry["expected"] + " " + entry["tests"]
            for phrase in DEPRECATED:
                self.assertNotIn(phrase, blob, f"id={entry['id']} 残留废止表述《{phrase}》")

    def test_04_default_is_single_scheme(self):
        """默认口径必须是「单一最佳方案」，且有权威句式锁定升级条件。

        两条确定性断言，不做语义推断：
        ① 不得出现已废止的「默认多方向」字面写法（BANNED_DEFAULT）；
        ② 必须有一条目在同一处同时给出「默认 + 1 个方向」与升级条件
           （用户明确要求 / 2–3 个），防止只留下「默认单一」而删掉例外口径。

        能力边界：本测试锁字面，不判断改写后的句子在语境里是否把多方向当默认；
        那部分由人工逐条验收与独立复核承担。
        """
        for entry in self.entries:
            blob = squeeze(entry["expected"] + entry["tests"])
            for phrase in BANNED_DEFAULT:
                self.assertNotIn(
                    squeeze(phrase), blob,
                    f"id={entry['id']} 残留默认多方向写法《{phrase}》",
                )
        self.assertTrue(
            any(
                all(squeeze(k) in squeeze(e["expected"]) for k in DEFAULT_CLAUSE)
                and all(k in e["expected"] for k in ESCALATION)
                and ESCALATION_RANGE.search(squeeze(e["expected"]))
                for e in self.entries
            ),
            "没有任何条目把「默认 1 个方向」与升级条件（用户明确要求 / 2–3 个）写在同一处",
        )

    def test_05_section_references_resolve(self):
        # §x.y 可能指向 gpt-visual-workflow.md、design-handoff.md 或 SKILL.md（§1.a）
        sections = numbered_sections(WORKFLOW, HANDOFF, SKILL)
        blob = " ".join(e["expected"] + " " + e["tests"] for e in self.entries)
        for ref in sorted(set(re.findall(r"§(\d+(?:\.\d+){0,2}(?:\.[a-z])?)", blob))):
            self.assertIn(ref, sections, f"引用了不存在的章节 §{ref}")

    def test_05b_cross_file_anchors_still_exist(self):
        # 并集校验不了目标文件，这里 ①按文件名锁具体章节；②把「design-handoff.md §N」
        # 这种点名引用逐个绑到 handoff 自己的编号标题上。
        anchors = [
            (HANDOFF, r"^## 3\. 交付形态"),
            (HANDOFF, r"^## 4\. 交付包自检"),
            (HANDOFF, r"^## 8\. 真实实现反馈闭环"),
            (SKILL, r"^#### 1\.a "),
        ]
        handoff_sections = numbered_sections(HANDOFF)
        for entry in self.entries:
            text = entry["expected"] + " " + entry["tests"]
            # 只在**同一分句**内绑定：窗口取到前一个 。； 换行为止，再取其中最近的
            # 文件名。这样「混写两家的 §N」不会被误绑，也不会像固定字符窗口那样
            # 漏掉「design-handoff.md 里的…章节（§3）」这种长桥接写法。
            for hit in re.finditer(r"§(\d+(?:\.\d+)*)", text):
                window = re.split(r"[。；\n]", text[: hit.start()])[-1]
                files = re.findall(r"([\w./-]+\.md)", window)
                if not files or os.path.basename(files[-1]) != "design-handoff.md":
                    continue
                self.assertIn(
                    hit.group(1), handoff_sections,
                    f"id={entry['id']} 引用了 design-handoff.md §{hit.group(1)}，但该章节不存在",
                )
        for path, pattern in anchors:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertRegex(
                text, re.compile(pattern, re.M), f"{os.path.basename(path)} 缺少被引用的章节：{pattern}"
            )

    def test_06_required_scenarios_still_covered(self):
        for name, phrase in REQUIRED_COVERAGE.items():
            self.assertTrue(
                any(phrase in e["expected"] for e in self.entries),
                f"缺少验收场景：{name}（找不到判据短语「{phrase}」）",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
