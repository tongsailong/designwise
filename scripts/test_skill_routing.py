#!/usr/bin/env python3
"""App UI 单一标准流程的文档契约测试（V3）。

守的是「流程只有一条、方向数按分歧决定、设计判断不外置、设计与实现之间的契约不被删弱」：

1. **单一流程**：`SKILL.md` 只有 0–6 七个阶段、G0–G6 七个门，没有任务分层，阶段表与细则一一对应。
2. **自适应方向**：方向数按实质分歧决定（1..N），共用任务块与原则转译块逐字相同，差异实测不靠目测，
   失败关闭，三出口（采用/融合/全部拒绝），决策记录可追溯。
3. **决策主体**：ZCode 原生 Agent 做设计判断；Copilot 只做治理；远程裁决通道已退役。
4. **原型与覆盖**：真实交互与状态、`P*`/`S*`/`X*` 覆盖闭合、缩放矩阵、真实素材。
5. **评审**：六维原版判据 + App 三项附加检查 + 严重度 + 打磨环；打分不替代缺陷清单。
6. **交接**：七件套 + 四类等价契约 + 语义 token + 允许偏差 vs 缺陷。
7. **验收**：四态矩阵 + 工程/设计双结论 + 三方对照 + 真实证据。
8. **范围与角色**：只做 App UI；已下线载体与远程裁决路径不得复活。

这些是文档契约测试：读真实文件、检查规则内容与跨文档一致性，不执行渲染、不调模型。
**绿色只能证明规则被写下、关键依赖没被删掉，不能证明真实设计质量**——设计是否真的变好，
只能由真实概念图、真实截图评审、真实三方对照与真机证据判断。
"""
import importlib.util
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

STAGES = {
    "0": "产品理解与设计目标",
    "1": "概念方向",
    "2": "HTML 原型与覆盖",
    "3": "设计评审与完善",
    "4": "原生交接",
    "5": "原生实现",
    "6": "真机验收与收口",
}

# 已下线的载体与工具：文档里不得再出现路径级引用，磁盘上不应再存在。
RETIRED_PATHS = (
    "gpt-visual-workflow.md",
    "direction-gpt-path.md",
    "materials.md",
    "slide-decks.md",
    "editable-pptx.md",
    "pptx-from-rendered-html.md",
    "ui-demo-animation.md",
    "storyboard-basics.md",
    "camera-language.md",
    "cinematic-patterns.md",
    "launch-film-director-notes.md",
    "voiceover-pipeline.md",
    "audio-design-rules.md",
    "sfx-library.md",
    "video-export.md",
    "ai-video-review.md",
    "scene-templates.md",
    "animation-best-practices.md",
    "animation-pitfalls.md",
    "gsap-recipes.md",
    "hyperframes-backend.md",
    "apple-gallery-showcase.md",
    "hero-animation-case-study.md",
    "render-video.js",
    "render-narration.sh",
    "mix-voiceover.sh",
    "add-music.sh",
    "convert-formats.sh",
    "sfx-cues.sh",
    "export_deck_pdf.mjs",
    "export_deck_pptx.mjs",
    "export_deck_stage_pdf.mjs",
    "gen_deck_thumbs.mjs",
    "html2pptx.js",
    "narrate-pipeline.mjs",
    "pptx_from_rendered.py",
    "verify-video.sh",
    "design-gate-check.js",
    "design-gate-hook.sh",
    "design-gate-hook-hyperframes.sh",
    "check-assets.py",
    "assets/animations.jsx",
    "assets/deck_stage.js",
    "assets/deck_index.html",
    "assets/cursor.jsx",
    "assets/macos_window.jsx",
    "assets/browser_window.jsx",
    "assets/showcases",
    "assets/bgm-",
    "scripts/cloud/",
)

HANDOFF_FILES = (
    "README.md",
    "structure.md",
    "design-tokens.md",
    "states-interactions.md",
    "copy-data.md",
    "assets.md",
    "adaptation-a11y.md",
)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def section(text, heading, level=3):
    """Return the text from a markdown heading up to the next same-or-higher one."""
    lines = text.splitlines()
    marker = "#" * level + " " + heading
    start = next((i for i, line in enumerate(lines) if line.startswith(marker)), None)
    if start is None:
        raise AssertionError("section not found: %r" % heading)
    end = len(lines)
    pattern = re.compile(r"^#{1,%d} " % level)
    for i in range(start + 1, len(lines)):
        if pattern.match(lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def doc_paths():
    """All shipped markdown that states rules: SKILL.md, READMEs, SECURITY, references/."""
    paths = ["SKILL.md", "README.md", "README.en.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md"]
    folder = os.path.join(ROOT, "references")
    paths += [os.path.join("references", name) for name in sorted(os.listdir(folder))
              if name.endswith(".md")]
    return paths


def stage_block(skill, num):
    """Text of one stage detail block in SKILL.md, ending at the next stage or section."""
    lines = skill.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.startswith("**阶段 %d · " % num)), None)
    if start is None:
        raise AssertionError("stage detail block missing: %d" % num)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("**阶段 ") or lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[start:end])


def stage_table_rows(skill):
    """Stage rows of the flow table in §2."""
    body = skill[skill.index("## 2. 唯一标准流程"):skill.index("### 2.1")]
    return [line for line in body.splitlines()
            if line.startswith("|") and "---" not in line and "| 阶段 |" not in line]


def load_checker():
    path = os.path.join(HERE, "check-deliverables.py")
    spec = importlib.util.spec_from_file_location("check_deliverables", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SingleFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")

    def test_01_no_task_tiers(self):
        self.assertIn("**没有任务分层。**", self.skill)

    def test_02_stage_table_is_the_single_authority(self):
        rows = stage_table_rows(self.skill)
        self.assertEqual(len(rows), len(STAGES), "阶段表行数不是 7：%s" % len(rows))
        for num, name in STAGES.items():
            self.assertTrue(any(line.startswith("| **%s %s** |" % (num, name)) for line in rows),
                            "阶段表缺少「%s %s」" % (num, name))

    def test_03_stage_details_match_the_table(self):
        rows = stage_table_rows(self.skill)
        for num, name in STAGES.items():
            block = stage_block(self.skill, int(num))
            self.assertTrue(block.startswith("**阶段 %s · %s**" % (num, name)),
                            "阶段 %s 细则标题与阶段表不一致" % num)
            self.assertTrue(any(line.startswith("| **%s %s** |" % (num, name)) for line in rows),
                            "阶段 %s 细则在阶段表中没有对应行" % num)

    def test_04_gate_ids_are_defined_and_consistent(self):
        self.assertIn("**Gate 编号以本表为准：G0–G6。**", self.skill)
        rows = stage_table_rows(self.skill)
        for num in STAGES:
            matches = [line for line in rows if "**G%s**" % num in line]
            self.assertEqual(len(matches), 1, "G%s 未在阶段表中唯一出现" % num)
        self.assertNotIn("| **7 ", self.skill, "阶段表仍残留阶段 7")

    def test_05_entry_is_decided_by_artifacts(self):
        entry = section(self.skill, "2.1 从哪进入（按产物成熟度，不按仪式）")
        for phrase in ("阶段 0", "阶段 1", "阶段 2", "阶段 3", "阶段 5",
                       "不触发本流程", "判不准按更高阶段处理"):
            self.assertIn(phrase, entry)

    def test_06_local_iteration_reuses_records(self):
        entry = section(self.skill, "2.1 从哪进入（按产物成熟度，不按仪式）")
        self.assertIn("当前版本原型，只需局部改动", entry)
        self.assertIn("阶段 3（只改受影响屏）", entry)
        self.assertIn("复评受影响项", entry)

    def test_07_html_is_prototype_not_product(self):
        self.assertIn("**HTML 是原型，不是产品**", self.skill)
        self.assertIn("不得把原型 HTML 塞进 App", self.skill)
        self.assertIn("禁止把 HTML 嵌入 App", self.skill)

    def test_08_html_is_the_design_target(self):
        self.assertIn("**HTML 是设计目标，不是配色参考**", self.skill)
        self.assertIn("「最小改动」「旧代码可复用」不是设计理由", self.skill)


class DirectionContractTests(unittest.TestCase):
    """V3 方向：数量按分歧、差异靠实测、决策不外置。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 1)
        cls.strategy = read("references/direction-strategy.md")

    def test_01_direction_count_is_divergence_driven(self):
        self.assertIn("**方向数量按实质分歧决定**", self.stage)
        for phrase in ("**1 个最优方向**", "**2–3 个**", "先出候选再融合", "**全部拒绝并重做**"):
            self.assertIn(phrase, self.stage)
        self.assertIn("**不为展示选项制造 A/B/C。**", self.stage)

    def test_02_strategy_table_matches_the_rule(self):
        for phrase in ("按实质分歧决定", "同骨架换皮", "先拒绝，再重出"):
            self.assertIn(phrase, self.strategy)

    def test_03_direction_card_has_six_columns(self):
        for phrase in ("逻辑与来源", "借用的是什么", "主角信息与素材",
                       "结构骨架", "差异点", "form 来自产品的哪里"):
            self.assertIn(phrase, self.stage)
            self.assertIn(phrase, self.strategy)

    def test_04_three_legitimate_sources(self):
        for phrase in ("现有体系推导", "同品类真实参照", "产品独有的结构隐喻"):
            self.assertIn(phrase, self.strategy)

    def test_05_shared_blocks_are_byte_identical(self):
        self.assertIn("**任务块**与**原则转译块**逐字相同，只在**方向块**不同", self.stage)
        self.assertIn("**共用块不得被用来制造差异**", self.strategy)
        self.assertIn("**共用块也不得过度锁死解法**", self.strategy)

    def test_06_prompt_has_nine_required_inputs(self):
        for phrase in ("产品定位", "用户场景", "页面任务", "真实业务规则与数据口径",
                       "信息层级与优先级", "视觉方向", "组件与布局约束",
                       "设备适配约束", "**不可迁移声明**"):
            self.assertIn(phrase, self.stage)

    def test_07_principle_translation_is_checkable(self):
        self.assertIn("4–6 条本页可检查的要求", self.stage)
        self.assertIn("不写原则名称或口号", self.stage)

    def test_08_divergence_is_measured(self):
        self.assertIn("scripts/direction_divergence.py", self.stage)
        self.assertIn("不得用", self.stage)
        self.assertIn("看起来不一样", self.stage)
        self.assertIn("替代实测", self.stage)
        self.assertIn("脚本只给事实", self.stage)
        self.assertIn("直方图距离", self.strategy)
        self.assertIn("骨架相关性", self.strategy)

    def test_09_no_fake_concept_images(self):
        self.assertIn("**不得用 HTML/CSS/SVG/占位图或文字描述冒充概念图。**", self.stage)
        self.assertIn("不用灰块/色块/手画 SVG 顶替",
                      read("references/app-visual-workflow.md"))

    def test_10_fail_closed(self):
        self.assertIn("**失败关闭**", self.stage)
        self.assertIn("不得进入原型", self.stage)
        for reason in ("图片缺失/不可解码/重复", "共用块被改写", "差异实测不通过"):
            self.assertIn(reason, self.stage)

    def test_11_three_exits_and_fusion_logic(self):
        self.assertIn("**采用**一个合格方向", self.stage)
        self.assertIn("**融合**：写明取用哪些、舍弃哪些、融合后的统一层级与交互逻辑", self.stage)
        self.assertIn("**全部拒绝**：给可执行修正项，只重出受影响方向", self.stage)
        self.assertIn("**改变主要骨架时必须补一张真实整合图**", self.stage)
        self.assertIn("融合＝把两版的部件拼在一起", self.strategy)

    def test_12_decision_record_is_traceable(self):
        for phrase in ("方向数及依据", "id+sha256", "差异实测值", "机会成本",
                       "**与 `P*`/`S*` 的对应**", "**状态字段（实施基线 / 实验推荐）——唯一实施基线**"):
            self.assertIn(phrase, self.skill if phrase.startswith("**状态") else self.stage)

    def test_13_concept_image_is_not_ui_truth(self):
        self.assertIn("**概念图不是 UI 真相**", self.skill)
        self.assertIn("**概念图不是交付物**", self.skill)

    def test_14_evidence_boundary_is_stated(self):
        self.assertIn("**证据边界**", self.stage)
        self.assertIn("图片只能证明可见设计表达", self.stage)

    def test_15_no_decision_before_decision_file(self):
        self.assertIn("**`direction-approved.md` 在决策形成前不得创建**", self.skill)
        self.assertIn("旧任务的该文件不构成新任务的授权", self.skill)


class DecisionOwnershipContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")

    def test_01_zcode_is_the_decision_subject(self):
        self.assertIn("**ZCode 原生 Agent 是唯一的工程执行与技术决策主体**", self.skill)
        self.assertIn("也是**设计判断主体**", self.skill)

    def test_02_copilot_governs_only(self):
        self.assertIn("**不做设计裁决**；不调远程模型；不是普通开发前置门", self.skill)
        self.assertIn("Copilot v6", self.skill)
        self.assertIn("只做任务治理", self.skill)

    def test_03_remote_channel_is_retired(self):
        self.assertIn("**设计判断不外置**", self.skill)
        self.assertIn("**禁止**：用 `call_gpt.py` / 远程 `CONSULT` / SOL", self.skill)
        self.assertIn("**`call_gpt.py` / `bridge_evidence.py --image` 的设计裁决用途已退役，不得使用。**",
                      self.skill)

    def test_04_reviewer_is_read_only(self):
        self.assertIn("只读、不改文件、不发布", self.skill)
        self.assertIn("复核是补充证据，不是审批节点", self.skill)

    def test_05_no_remote_decision_in_references(self):
        for rel in doc_paths():
            text = read(rel)
            self.assertNotIn("等待 SOL", text, "%s 仍把决策交给远程模型" % rel)
            self.assertNotIn("SOL 批准", text, "%s 仍要求远程批准" % rel)


class StateMapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 0)
        cls.mapdoc = read("references/state-map.md")

    def test_01_page_state_map_is_required(self):
        self.assertIn("**页面-状态地图", self.stage)
        self.assertIn("`P*`", self.stage)
        self.assertIn("`S*`", self.stage)
        self.assertIn("`X*`", self.stage)

    def test_02_map_has_per_item_judgement_fields(self):
        for phrase in ("用户目标", "入口与出口", "主要功能", "状态集合", "平台约束",
                       "当前问题", "值得保留的成熟体验", "确认要重构的部分"):
            self.assertIn(phrase, self.stage)

    def test_03_provenance_is_mandatory(self):
        self.assertIn("**出处规则**", self.stage)
        self.assertIn("`file:line`", self.stage)
        self.assertIn("**列为待决**", self.stage)
        self.assertIn("不静默采用", self.stage)

    def test_04_depth_follows_risk(self):
        self.assertIn("**深度按风险**", self.stage)
        self.assertIn("整机/多页面 → 全量地图", self.stage)
        self.assertIn("只改 token → 不建地图", self.stage)

    def test_05_gate_zero_rejects_count_as_understanding(self):
        self.assertIn("**数量与截图不能证明理解**", self.skill)
        self.assertIn("数量或截图代替每页判断", self.stage)

    def test_06_stage_zero_prechecks_native_feasibility(self):
        self.assertIn("**原生可行性前置检查**", self.stage)
        self.assertIn("不得推迟到阶段 4", self.stage)

    def test_07_state_map_doc_expands_without_claiming_semantic_proof(self):
        self.assertIn("覆盖", self.mapdoc)
        self.assertIn("结构合法不等于覆盖合理", self.mapdoc)


class PrototypeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 2)
        cls.proto = read("references/app-prototype.md")

    def test_01_interaction_and_state_are_real(self):
        self.assertIn("**交互与状态必须真实**", self.stage)
        self.assertIn("**假控件、只展示静态画面、点不动的按钮都不合格。**", self.stage)

    def test_02_coverage_matrix_is_closed(self):
        self.assertIn("**覆盖矩阵闭合**", self.stage)
        self.assertIn("**页面地图有而原型没有的项不得静默消失。**", self.stage)
        for value in ("`rendered`", "`deferred-native`", "`not-applicable`"):
            self.assertIn(value, self.stage)

    def test_03_scale_matrix_is_rendered(self):
        self.assertIn("默认 `1.0 / 1.3 / 1.6 / 2.0`", self.stage)
        self.assertIn("**多列布局、label+value 同行、固定高度弹层/卡片必须在最大档渲染**", self.stage)
        self.assertIn("`?fs=`", self.stage)

    def test_04_single_page_inline_react(self):
        self.assertIn("**单页 inline React**", self.stage)
        self.assertIn("`file://` 双击可开", self.stage)

    def test_05_device_frames_are_not_handdrawn(self):
        self.assertIn("`assets/ios_frame.jsx`", self.stage)
        self.assertIn("`assets/android_frame.jsx`", self.stage)
        self.assertIn("**禁止手写 Dynamic Island", self.stage)

    def test_06_real_assets_not_grey_blocks(self):
        self.assertIn("不得用灰块/色块/手画 SVG 顶替", self.stage)
        self.assertIn("**真实素材优先**", self.skill)

    def test_07_css_px_is_not_dp(self):
        self.assertIn("**CSS px 不能证明 Android dp。**", self.stage)
        self.assertIn("48dp", self.skill)
        self.assertIn("44pt", self.skill)

    def test_08_prototype_doc_carries_state_reachability(self):
        self.assertIn("deferred-native", self.proto)
        self.assertIn("状态", self.proto)


class ReviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 3)
        cls.critique = read("references/critique-guide.md")
        cls.polish = read("references/polish-loop.md")

    def test_01_six_dimensions_preserved(self):
        for phrase in ("**0 概念/立意**", "1 哲学一致性", "2 视觉层级",
                       "3 细节执行", "4 功能性", "5 创新性"):
            self.assertIn(phrase, self.skill)

    def test_02_original_criteria_are_not_rewritten(self):
        for phrase in ("≤5 分", "封顶 6.0", "≥2.5 倍", "≤2 字体族"):
            self.assertIn(phrase, self.skill)
        self.assertIn("上游原版判据，不改写数值", self.skill)

    def test_03_app_three_checks(self):
        self.assertIn("**App UI 三项附加检查**", self.skill)
        for phrase in ("状态完整性", "交互真实性", "原生可实现性与适配风险"):
            self.assertIn(phrase, self.skill)

    def test_04_severity_and_clearance(self):
        self.assertIn("**严重度**：致命 / 重要 / 打磨", self.skill)
        self.assertIn("**致命项清零**", self.skill)

    def test_05_polish_loop(self):
        self.assertIn("一轮只改最伤的三处", self.stage)
        self.assertIn("通常 3–5 轮", self.stage)
        self.assertIn("≥5 轮仍在改结构", self.stage)
        self.assertIn("停止判据", self.polish)

    def test_06_review_based_on_current_screenshots(self):
        self.assertIn("**评审基于当前版本真实截图**", self.stage)
        self.assertIn("不得用文字描述、HTML 源码或概念图代替", self.stage)

    def test_07_scores_do_not_replace_defects(self):
        self.assertIn("**打分不能替代缺陷清单**", self.skill)
        self.assertIn("不用分数趋势代替证据", self.skill)

    def test_08_optional_readonly_reviewer(self):
        self.assertIn("**可选独立复核**", self.stage)
        self.assertIn("复核不替代主 Agent 判断", self.stage)

    def test_09_critique_guide_expands_the_same_checks(self):
        for phrase in ("三项附加检查", "致命", "重要", "打磨"):
            self.assertIn(phrase, self.critique)


class HandoffContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 4)
        cls.handoff = read("references/design-handoff.md")

    def test_01_seven_piece_package(self):
        self.assertIn("`handoff/` 七件套", self.stage)
        for name in HANDOFF_FILES:
            self.assertIn("`%s`" % name, self.stage, "缺少交接文件 %s" % name)
            self.assertIn(name, self.handoff, "design-handoff.md 未展开 %s" % name)

    def test_02_four_equivalence_contracts(self):
        self.assertIn("**四类等价契约（缺一不得进入实现）**", self.stage)
        for phrase in ("**组件等价 + 禁用替代**", "**绘制层级与命中优先级**",
                       "**滚动与可达**", "**业务规则出处**"):
            self.assertIn(phrase, self.stage)

    def test_03_banned_substitution_is_named(self):
        self.assertIn("分段 gauge 不得替换为 `ProgressBar`", self.stage)
        self.assertIn("**不做降级替换**", self.skill)
        self.assertIn("出现即为缺陷", self.skill)

    def test_04_semantic_tokens(self):
        self.assertIn("**token 语义化**", self.stage)
        self.assertIn("不得把 `white`/`black` 这类绝对色当语义色", self.stage)

    def test_05_allowed_deviation_vs_defect(self):
        self.assertIn("**允许偏差 vs 缺陷**", self.stage)
        self.assertIn("信息层级、布局意图、关键状态、业务数据错误属缺陷", self.stage)

    def test_06_legacy_resource_cleanup(self):
        self.assertIn("**旧资源清理清单**", self.stage)
        self.assertIn("防止残留", self.stage)

    def test_07_scroll_and_zorder_are_explicit(self):
        self.assertIn("z-order", self.stage)
        self.assertIn("命中测试顺序", self.stage)
        self.assertIn("滚动容器与关闭路径", self.stage)

    def test_08_handoff_doc_is_implementable(self):
        self.assertIn("组件等价", self.handoff)
        self.assertIn("禁用替代", self.handoff)


class ImplementationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 5)

    def test_01_implementation_follows_handoff_not_diff_size(self):
        self.assertIn("**按交接实现**", self.stage)
        self.assertIn("不得用「最小 diff」", self.stage)

    def test_02_component_substitution_diff(self):
        self.assertIn("**组件替换 diff（pre-device 自检，必做）**", self.stage)
        self.assertIn("**这一步是 D2 类缺陷的唯一拦截点。**", self.stage)

    def test_03_landing_map(self):
        self.assertIn("**落地映射**", self.stage)
        self.assertIn("原有问题或保留依据", self.stage)
        self.assertIn("HTML 目标意图", self.stage)
        self.assertIn("原生实现方式", self.stage)

    def test_04_three_way_comparison_starts_here(self):
        self.assertIn("**首批三方对照**", self.stage)
        self.assertIn("旧版 App ↔ HTML 目标 ↔ 新版真机", self.stage)

    def test_05_token_swap_is_not_landing(self):
        self.assertIn("**构建成功、token 替换、全局换圆角都不能替代这张表。**", self.stage)
        self.assertIn("**不以最小改动代替设计目标**", self.skill)

    def test_06_no_old_baseline_theft(self):
        self.assertIn("不得为补基线擅自降级安装、清数据或恢复旧包", self.stage)


class AcceptanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.stage = stage_block(cls.skill, 6)
        cls.verify = read("references/verification.md")

    def test_01_two_acceptances_one_report(self):
        self.assertIn("**同一份报告分别给两条结论，两项都达标才算整体通过**", self.stage)
        self.assertIn("**工程验收**", self.stage)
        self.assertIn("**设计验收**", self.stage)

    def test_02_matrix_is_four_state(self):
        self.assertIn("每项只能是 PASS / FAIL / NOT TESTED / N/A", self.stage)
        self.assertIn("**未测试项必须写 `NOT TESTED` 并说明缺什么条件**", self.stage)

    def test_03_matrix_covers_core_dimensions(self):
        for phrase in ("方向一致性", "布局与信息层级", "字体与排版", "色彩与对比度",
                       "状态", "真实业务数据", "触控与交互", "平台规范",
                       "设计意图落地", "旧版对照与改善"):
            self.assertIn(phrase, self.stage)

    def test_04_scales_and_contrast(self):
        self.assertIn("`1.0/1.3/1.6/2.0` 各档不截断不重叠", self.stage)
        self.assertIn("正文 ≥4.5:1、重要图标/图形 ≥3:1", self.stage)

    def test_05_no_vanity_metrics(self):
        self.assertIn("**不得用代码修改量、视觉变化百分比、页面改动数量、测试数量替代设计成功。**",
                      self.stage)

    def test_06_verdicts(self):
        for phrase in ("**PASS**", "**PARTIAL**", "**BLOCKED**"):
            self.assertIn(phrase, self.stage)
        self.assertIn("不得把没验的场景写进 PASS", self.stage)

    def test_07_device_install_uses_authorised_entry(self):
        self.assertIn("`~/.zcode/skills/app-testing/runtime/mi6-verify/adb-auto-install.sh`",
                      self.skill)
        self.assertIn("**禁止裸 `adb install`**", self.skill)
        self.assertIn("多台设备在线即停止", self.skill)

    def test_08_verification_doc_keeps_four_states(self):
        for phrase in ("PASS", "FAIL", "NOT TESTED", "N/A"):
            self.assertIn(phrase, self.verify)


class CoverageSourceContractTests(unittest.TestCase):
    """coverage.json 是覆盖单一事实源，schema 与校验脚本必须一致。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.checker = load_checker()
        body = section(cls.skill, "6.3 覆盖与验证事实源（`coverage.json`）")
        match = re.search(r"```json\n(.*?)\n```", body, re.S)
        assert match, "SKILL.md §6.3 缺少 coverage.json 示例"
        cls.sample = json.loads(match.group(1))
        cls.section = body

    def test_01_sample_is_valid_json_with_schema(self):
        self.assertEqual(self.sample["schema"], self.checker.COVERAGE_SCHEMA)
        self.assertEqual(self.sample["schema"], "designwise-coverage/v1")
        self.assertTrue(self.sample["items"])

    def test_02_enums_match_the_checker(self):
        self.assertEqual(tuple(self.checker.COVERAGE_KINDS), ("page", "overlay", "state"))
        self.assertEqual(tuple(self.checker.COVERAGE_PROTOTYPE),
                         ("rendered", "deferred-native", "not-applicable"))
        self.assertEqual(tuple(self.checker.COVERAGE_NATIVE),
                         ("todo", "done", "not-applicable"))
        self.assertEqual(tuple(self.checker.COVERAGE_DEVICE),
                         ("pass", "fail", "not-tested", "not-applicable"))
        for value in self.checker.COVERAGE_PROTOTYPE + self.checker.COVERAGE_DEVICE:
            self.assertIn(value, self.section, "SKILL.md §6.3 未写枚举 %s" % value)

    def test_03_deferred_native_needs_reason_and_verification(self):
        self.assertIn("`deferred-native` 必须有 `defer_reason` 且 `native_verify: true`",
                      self.section)

    def test_04_id_set_must_match_the_map(self):
        self.assertIn("**不得出现地图里没有的 id，也不得让地图里的 id 消失**", self.section)
        self.assertIn("`scripts/check-deliverables.py` 会校验", self.section)

    def test_05_checker_is_read_only_and_semantics_stay_human(self):
        doc = read("scripts/check-deliverables.py")
        self.assertIn("不判断覆盖去向是否合理", doc)


class FailureHandlingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.table = section(cls.skill, "9. 失败处理与降级", level=2)

    def test_01_image_unavailable(self):
        self.assertIn("生图接口不可用", self.table)
        self.assertIn("不得用 HTML/SVG/占位图冒充概念图", self.table)

    def test_02_reskin_is_rejected(self):
        self.assertIn("多方向差异实测判为换皮/同骨架", self.table)
        self.assertIn("不是换颜色", self.table)

    def test_03_all_directions_rejected(self):
        self.assertIn("全部方向不合格", self.table)
        self.assertIn("不自行降低产品原则", self.table)

    def test_04_collage_is_not_fusion(self):
        self.assertIn("融合后是拼图式堆叠", self.table)

    def test_05_coverage_not_closed(self):
        self.assertIn("原型覆盖不闭合", self.table)
        self.assertIn("原生验证义务", self.table)

    def test_06_max_font_breaks_structure(self):
        self.assertIn("最大字号下结构崩", self.table)

    def test_07_review_unavailable(self):
        self.assertIn("评审不可用（无截图/无渲染）", self.table)
        self.assertIn("不得声称 G3 通过", self.table)

    def test_08_token_swap_and_degraded_substitution(self):
        self.assertIn("原生只换了皮", self.table)
        self.assertIn("组件被降级替换", self.table)

    def test_09_missing_baseline_and_no_device(self):
        self.assertIn("旧版基线缺失", self.table)
        self.assertIn("原生工具链/真机不可用", self.table)
        self.assertIn("`PARTIAL` / `BLOCKED`", self.table)


class ProductPrincipleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.value = read("references/product-value.md")

    def test_01_principle_order(self):
        self.assertIn("**顺序：有用 → 好懂 → 舒服 → 有意义。**", self.skill)

    def test_02_gamification_is_optional(self):
        self.assertIn("**游戏化是手段不是目标**", self.skill)
        for phrase in ("不强制积分/勋章/排行榜/签到/任务体系", "损失焦虑", "虚假稀缺"):
            self.assertIn(phrase, self.skill)

    def test_03_density_is_legitimate(self):
        self.assertIn("**专业信息密度**", self.skill)
        self.assertIn("每处信息都要有内容价值", self.skill)

    def test_04_principles_must_be_translated(self):
        self.assertIn("**原则必须转译成本页可检查的要求**", self.skill)

    def test_05_project_principles_outrank_skill(self):
        self.assertIn("项目规则定义产品原则时**项目优先**", self.skill)
        self.assertIn("只在项目未定义时作为默认方法", self.skill)

    def test_06_product_value_doc_does_not_claim_fixed_three(self):
        self.assertNotIn("恰好 3 个方向", self.value)
        self.assertIn("不固定三方向", self.value)


class ScopeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.scope = cls.skill[cls.skill.index("## 0. 定位与边界"):cls.skill.index("## 1. ")]

    def test_01_app_only_scope_table(self):
        self.assertIn("**只做 App UI**", self.scope)
        for phrase in ("幻灯片 / PPT / deck", "视频 / 动画成片 / 宣传片",
                       "信息图 / 海报 / 封面等静态平面载体", "生产级 Web App"):
            self.assertIn(phrase, self.scope)

    def test_02_retired_carriers_are_not_referenced(self):
        for rel in doc_paths():
            text = read(rel)
            for retired in RETIRED_PATHS:
                self.assertNotIn(retired, text, "%s 仍引用已下线的 %s" % (rel, retired))

    def test_03_retired_files_are_gone(self):
        for retired in RETIRED_PATHS:
            self.assertFalse(os.path.exists(os.path.join(ROOT, retired)),
                             "已下线文件仍在仓库：%s" % retired)

    def test_04_no_upstream_runtime_dependency(self):
        readme = read("README.md")
        self.assertIn("独立", readme)
        self.assertNotIn("上游运行时", readme)

    def test_05_licence_not_excluded(self):
        sync = read("scripts/sync_runtime.py")
        self.assertIn("LICENSE", sync)


class DocConsistencyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.routing = read("references/routing-table.md")
        cls.readme = read("README.md")

    def test_01_every_reference_linked_from_skill_exists(self):
        for rel in sorted(set(re.findall(r"references/[\w.-]+\.md", self.skill))):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)),
                            "SKILL.md 引用了不存在的文件：%s" % rel)

    def test_02_entry_list_is_complete(self):
        for name in sorted(os.listdir(os.path.join(ROOT, "references"))):
            if name.endswith(".md"):
                self.assertIn(name, self.skill, "SKILL.md §10 未登记 references/%s" % name)

    def test_03_workflow_expands_all_seven_stages(self):
        for num, name in STAGES.items():
            self.assertIn("## %s. 阶段 %s · %s" % (int(num) + 1, num, name), self.workflow)

    def test_04_expansion_defers_to_skill(self):
        for rel in ("references/app-visual-workflow.md", "references/routing-table.md",
                    "references/workflow.md"):
            self.assertIn("以 `SKILL.md` 为准", read(rel), "%s 未声明权威来源" % rel)

    def test_05_routing_has_no_old_stage_numbers(self):
        for text, label in ((self.routing, "routing-table"), (self.workflow, "app-visual-workflow")):
            for ref in sorted(set(re.findall(r"阶段\s*(\d)", text))):
                self.assertIn(ref, STAGES, "%s 引用不存在的阶段 %s" % (label, ref))

    def test_06_readme_states_one_flow(self):
        self.assertIn("重走 0–6", self.readme)
        self.assertIn("按实质分歧", self.readme)
        self.assertNotIn("阶段 0–7", self.readme)

    def test_07_check_skill_lists_v3_files(self):
        check = read("scripts/check-skill.py")
        self.assertIn("state-map.md", check)
        self.assertIn("direction-strategy.md", check)
        self.assertIn("polish-loop.md", check)
        self.assertIn("direction_divergence.py", check)
        self.assertIn("check-deliverables.py", check)

    def test_08_readmes_agree_on_handoff(self):
        en = read("README.en.md")
        for phrase in ("handoff", "coverage.json", "0–6"):
            self.assertIn(phrase, en)


class ForbiddenSubstitutionContractTests(unittest.TestCase):
    """防止用便宜指标冒充设计完成；本类只是文档断言，不执行真实设计。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")

    def test_01_page_count_cannot_prove_understanding(self):
        self.assertIn("**数量与截图不能证明理解**", self.skill)

    def test_02_green_render_cannot_prove_design(self):
        self.assertIn("**渲染成功不算通过**", self.skill)
        self.assertIn("**渲染成功不是设计完成**", self.skill)

    def test_03_token_swap_cannot_prove_landing(self):
        self.assertIn("**不以最小改动代替设计目标**", self.skill)

    def test_04_test_count_cannot_prove_design_success(self):
        self.assertIn("测试数量替代设计成功", self.skill)

    def test_05_narrative_cannot_prove_coverage(self):
        self.assertIn("**不用叙述证明覆盖**", self.skill)

    def test_06_these_tests_carry_their_own_limit(self):
        doc = read("scripts/test_skill_routing.py")
        self.assertIn("不能证明真实设计质量", doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
