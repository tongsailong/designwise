#!/usr/bin/env python3
"""App UI 单一标准流程的文档契约测试。

守的是「流程真的只有一条、三方向与 Copilot 裁决真的不可跳过、范围真的只剩 App UI」：

1. **单一流程**：`SKILL.md` 只有 0–7 八个阶段，没有任务分层，阶段表与阶段细则一一对应。
2. **三方向**：恰好 3 个、结构性差异、共用任务块与原则转译块（差异只在方向块）、一方向一 prompt、
   同比例同尺寸同模型、真实生图、不得用 HTML/SVG/占位图冒充、单张失败只重出该方向。
3. **Copilot 裁决**：三张图全部进入请求、`CONSULT` 而非正式 REVIEW、先判逐方向合格性再比较、
   允许全部拒绝并重出受影响方向、失败关闭六条件、`direction-approved.md` 字段齐全、裁决前不得创建该文件。
4. **流程分支**：局部迭代复用既有记录不重跑方向；实质变化重走 0–7。
5. **范围**：只做 App UI；已下线的载体文档与脚本不得再被引用。
6. **产品原则**：四层顺序、游戏化可选、专业密度正当、自主感三视角不是功能清单。
7. **质量与证据**：真实证据、dp/sp 与 48dp、业务断言独立、三态结论、真机装包入口。
8. **角色边界**：本 skill 是方法与质量规范，ZCode 原生 Agent 是执行主体。
9. **V2 六项升级**：整机页面地图（数量与截图不算理解）、生图前提示词预审、方向三出口与融合逻辑、
   原型真实截图设计评审、原生落地映射与旧版↔HTML↔新版三方对照、工程/设计双验收。

这些是文档契约测试：读真实文件、检查真实规则内容与跨文档一致性，不执行渲染、不调模型。
**它们只能证明规则被写下、关键依赖没有被删掉，不能证明真实设计质量**——设计是否真的变好，
只能由真实概念图、真实截图评审、真实三方对照与真机证据判断，不能拿本文件的绿色当设计效果验证。
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

STAGES = {
    "0": "任务受理与产品理解",
    "1": "设计目标与假设",
    "2": "GPT 三方向概念图",
    "3": "Copilot 方向选择",
    "4": "HTML 高保真原型",
    "5": "设计完善与素材生成",
    "6": "App 原生实现",
    "7": "真机验收与收口",
}

STAGE_DETAILS_HEADING = (
    "2.2 阶段细则（只写不可省略的部分，完整展开见 `references/app-visual-workflow.md`）"
)

# 已下线的载体与工具：文档里不得再出现路径级引用。
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
    start = next(i for i, line in enumerate(lines) if line.startswith("**阶段 %d " % num))
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


class SingleFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.routing = read("references/routing-table.md")
        cls.readme_zh = read("README.md")
        cls.readme_en = read("README.en.md")

    def test_01_no_task_tiers(self):
        self.assertIn("**没有 L1/L2/L3 分层。**", self.skill)
        self.assertIn("没有 L1/L2/L3 分层", self.routing)
        self.assertNotIn("任务分层", self.skill)
        for tier in ("**L1", "**L2", "**L3", "| L1 ", "| L2 ", "| L3 "):
            self.assertNotIn(tier, self.skill, "残留旧任务分层：%r" % tier)

    def test_02_stage_table_is_the_single_authority(self):
        rows = stage_table_rows(self.skill)
        self.assertEqual(len(rows), 8, "流程表必须有 8 个阶段行：%r" % rows)
        for num, name in STAGES.items():
            row = next((r for r in rows if r.startswith("| **%s " % num)), None)
            self.assertIsNotNone(row, "流程表缺少阶段 %s" % num)
            self.assertIn(name, row, "阶段 %s 名称不一致" % num)

    def test_03_stage_details_match_the_table(self):
        for num, name in STAGES.items():
            marker = "**阶段 %s · %s**" % (num, name)
            self.assertIn(marker, self.skill, "阶段细则缺少：%s" % marker)

    def test_04_every_stage_has_an_evidence_gate(self):
        rows = stage_table_rows(self.skill)
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            self.assertEqual(len(cells), 5, "流程表应为 5 列：%r" % row)
            self.assertTrue(cells[4], "阶段缺少证据门：%r" % row)
            self.assertNotIn("待定", cells[4])

    def test_04b_gate_ids_are_defined_and_consistent(self):
        rows = stage_table_rows(self.skill)
        for idx, row in enumerate(rows):
            self.assertIn("**G%d**" % idx, row, "阶段表缺少 Gate 编号 G%d：%r" % (idx, row))
        self.assertIn("Gate 编号（G0–G7）以本表为准", self.skill)
        workflow = read("references/app-visual-workflow.md")
        self.assertIn("| G3 方向 |", workflow)
        self.assertIn("| G4 原型 |", workflow)
        # G4 现在是原型设计评审门，「不得声称 G4 通过」是正确用法；旧编号残留只查路径级引用。
        self.assertIn("**不得声称 G4 通过**", self.skill)
        for path in doc_paths():
            text = read(path)
            self.assertNotIn("design-demos/concepts/", text, "%s 残留旧产物路径" % path)

    def test_05_new_task_cannot_skip_stage_2_or_3(self):
        block = section(self.skill, "2.1 完整流程 vs 局部迭代")
        self.assertIn("不得跳过阶段 2 的三方向概念图", block)
        self.assertIn("不得跳过阶段 3 的 Copilot 方向选择", block)
        self.assertIn("任何「继续/开工/赶时间」都不豁免阶段 2 的三方向与阶段 3 的 Copilot 选择",
                      self.skill)

    def test_06_local_iteration_reuses_direction_record(self):
        block = section(self.skill, "2.1 完整流程 vs 局部迭代")
        self.assertIn("复用 `design-brief.md` + 三图记录 + `direction-approved.md`", block)
        self.assertIn("不重新探索三方向", block)
        self.assertIn("判不准时按「实质变化」处理", block)

    def test_07_html_is_prototype_not_product(self):
        self.assertIn("**HTML 是原型，不是产品**", self.skill)
        self.assertIn("不得把原型 HTML 塞进 App 充当实现", self.skill)
        self.assertIn("不得把原型 HTML 嵌入 App", read("references/design-handoff.md"))

    def test_08_readmes_describe_one_flow(self):
        for text, needles in (
            (self.readme_zh, ("唯一标准流程", "没有 L1/L2/L3 分层", "三个方向", "Copilot 方向选择",
                              "真机验收", "只做 App UI")),
            (self.readme_en, ("one standard flow", "no L1/L2/L3 tiers", "three real concept directions",
                              "Copilot direction selection", "on-device acceptance", "App UI only")),
        ):
            for needle in needles:
                self.assertIn(needle, text)


class ThreeDirectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.gen = read("references/image-generation.md")
        cls.assets = read("references/image-assets.md")
        cls.workflow = read("references/app-visual-workflow.md")

    def stage2(self):
        lines = self.skill.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("**阶段 2 "))
        end = next(i for i, line in enumerate(lines) if line.startswith("**阶段 3 "))
        return "\n".join(lines[start:end])

    def test_01_exactly_three_directions(self):
        self.assertIn("**恰好 3 个方向**", self.skill)
        self.assertIn("实质不同的三个方向", self.workflow)

    def test_01b_product_value_does_not_contradict_three(self):
        text = read("references/product-value.md")
        self.assertIn("恰好 3 个方向", text)
        self.assertNotIn("默认单一最佳方案", text)
        self.assertNotIn("2–3 个方向", text)
        self.assertNotIn("2-3 个方向", text)

    def test_02_structural_difference_not_styling(self):
        self.assertIn("布局骨架 / 信息组织 / 视觉母题", self.skill)
        self.assertIn("只换配色、间距或圆角不算方向", self.skill)

    def test_03_one_prompt_per_direction(self):
        self.assertIn("**每个方向 = 一个 prompt = 一个 job**", self.skill)
        self.assertIn("不得在一个 prompt 里塞三个方向", self.skill)

    def test_04_comparability_of_the_three_images(self):
        self.assertIn("同比例、同尺寸请求、同模型、同质量档", self.skill)
        self.assertIn("App 默认竖版 `1024x1536`", self.skill)

    def test_05_prompt_must_carry_structure(self):
        block = self.stage2()
        for needle in ("载体与比例", "方向名与真实锚点", "结构骨架", "不可迁移声明", "图内文字语言"):
            self.assertIn(needle, block, "阶段 2 prompt 要求缺少：%s" % needle)

    def test_06_no_fake_concept_images(self):
        self.assertIn("不得用 HTML/CSS/SVG 静态图、占位图或文字描述冒充概念图", self.skill)
        self.assertIn("不静默改用 HTML/SVG 绘图冒充概念图", read("README.md"))

    def test_07_failed_direction_is_redone_not_padded(self):
        block = section(self.skill, "8. 失败处理与降级", level=2)
        self.assertIn("只重出该方向", block)
        self.assertIn("不拿两张凑三张", block)
        self.assertIn("不复制同一张当不同方向", block)

    def test_08_concept_index_records_provenance(self):
        block = self.stage2()
        for needle in ("`concept-index.json`", "sha256", "prompt", "模型", "请求尺寸", "实际尺寸"):
            self.assertIn(needle, block)
        self.assertIn("不记录秘密", block)

    def test_09_generation_rules_are_documented(self):
        for needle in ("--health", "gpt-image-2.5", "--ref", "--size", "--fit", "--n"):
            self.assertIn(needle, self.skill + self.gen)
        self.assertIn("串行生成", self.skill)
        self.assertIn("先探测再生成", self.skill)

    def test_10_assets_have_three_states(self):
        for needle in ("参考图", "概念图", "正式素材"):
            self.assertIn(needle, self.skill)
        self.assertIn("素材三态", self.assets)
        self.assertIn("概念图不得直接当生产素材", self.skill)

    def test_11_prompt_carries_shared_task_and_translation_blocks(self):
        block = self.stage2()
        for needle in ("共用任务块与原则转译块", "**任务块**", "**原则转译块**", "只在方向块不同",
                       "不得只写原则名称或口号", "本页核心问题"):
            self.assertIn(needle, block, "阶段 2 缺少共用块要求：%s" % needle)
        self.assertIn("差异只允许出现在方向块", self.workflow)
        self.assertIn("共用块不得改写", self.workflow)
        self.assertIn("**共用块逐字一致**", self.gen)

    def test_12_history_styles_are_not_fixed_defaults(self):
        self.assertIn("不把历史任务的风格", self.stage2())
        self.assertIn("不构成以后任务的默认三方向", self.workflow)
        styles = read("references/design-styles.md")
        self.assertIn("温度不是配方", styles)
        self.assertNotIn("C 强制注入大胆款", styles)
        self.assertIn("不把任何历史案例固化成以后任务的默认三方向", styles)

    def test_13_prompt_selfcheck_covers_shared_blocks_and_fake_data(self):
        self.assertIn("任务块与原则转译块在三张 prompt 中逐字一致", self.workflow)
        self.assertIn("没有「有用 / 好懂」单独成句", self.workflow)
        self.assertIn("没有编造计数", self.workflow)
        self.assertIn("转译块不要复述「有用/好懂/舒服/有意义」四个词本身", self.gen)

    def test_14_prompt_template_has_five_parts(self):
        for needle in ("任务块（三方向逐字共用）", "原则转译块（三方向逐字共用",
                       "载体与比例", "方向块", "不出现外文 nameplate"):
            self.assertIn(needle, self.gen, "生图模板缺少：%s" % needle)

    def test_15_placement_requirements_are_structural(self):
        # 2026-11-10 实测：只给纵向百分比，模型会把主按钮上提；用底部固定操作区才稳定。
        self.assertIn("位置类要求用结构表达", self.workflow)
        self.assertIn("固定在底部的操作区", self.workflow)
        self.assertIn("以可见像素为准", self.workflow)


class CopilotSelectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.routing = read("references/routing-table.md")
        cls.adapters = read("references/runtime-adapters.md")

    def stage3(self):
        lines = self.skill.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("**阶段 3 "))
        end = next(i for i, line in enumerate(lines) if line.startswith("**阶段 4 "))
        return "\n".join(lines[start:end])

    def test_01_copilot_decides_from_real_pixels(self):
        text = self.stage3()
        self.assertIn("必须由 Copilot 基于三张真实图片选择", text)
        self.assertIn("不得由执行 agent 自选后伪称 Copilot 裁决", text)
        self.assertIn("不得用文字总结替代像素", text)

    def test_02_uses_existing_copilot_scripts(self):
        text = self.stage3()
        self.assertIn("bridge_evidence.py", text)
        self.assertIn("call_gpt.py --mode CONSULT", text)
        self.assertIn("--goal-file", text)
        self.assertIn("--image design-demos/<task>/concepts/A.png", text)
        self.assertIn("--out .designwise/evidence-direction.md", text)
        self.assertIn("--audit-log", text)

    def test_03_all_three_images_in_request(self):
        text = self.stage3()
        self.assertIn("三张图都必须在请求内", text)
        self.assertIn("3 张图在请求内", self.skill)

    def test_04_request_specifies_expected_answer(self):
        text = self.stage3()
        for needle in ("产品背景", "目标用户与场景", "硬约束", "成功标准",
                       "选哪个方向", "逐图差异", "选择理由", "机会成本", "主要风险"):
            self.assertIn(needle, text, "方向请求缺少：%s" % needle)

    def test_05_fail_closed_conditions(self):
        text = self.stage3()
        self.assertIn("**失败关闭**", text)
        for needle in ("图片缺失", "不可解码", "未真正进入请求", "模型身份核验失败",
                       "看不到图", "只有泛泛评价没有明确推荐"):
            self.assertIn(needle, text, "失败关闭缺少：%s" % needle)
        self.assertIn("不得伪造结论", text)

    def test_06_direction_record_fields(self):
        text = self.stage3()
        for needle in ("`direction-approved.md`", "三张图 id+sha256", "模型身份核验结果",
                       "调用 id 与回复 sha256", "放弃成本", "风险", "采用方向", "修正项"):
            self.assertIn(needle, text, "方向落档缺少：%s" % needle)

    def test_07_not_a_formal_review(self):
        self.assertIn("不是正式 REVIEW，也不替代 G3 或用户决策", self.skill)
        self.assertIn("方向选择用 `CONSULT`，**不是正式 REVIEW**", self.skill)
        self.assertIn("不写 REVIEW 台账", self.skill)
        self.assertIn("不是正式 REVIEW", self.routing)

    def test_08_user_can_override(self):
        self.assertIn("用户仍可否决 Copilot 的选择", self.skill)
        self.assertIn("不把 Copilot 推荐写成用户选择", self.skill)
        self.assertIn("记录原话", self.skill)

    def test_09_gate_file_does_not_precede_verdict(self):
        self.assertIn("**`direction-approved.md` 在 Copilot 裁决前不得创建**", self.skill)
        self.assertIn("旧任务的该文件不构成新任务的授权", self.skill)

    def test_09b_single_implementation_baseline(self):
        """同一任务内只能有一个实施基线：实验推荐不得并列或自动晋升；跨任务不互斥。"""
        self.assertIn("同一任务同一时刻只有一个实施基线", self.skill)
        self.assertIn("实验推荐", self.skill)
        self.assertIn("不得并列成第二个基线", self.skill)
        self.assertIn("不因「更新」自动晋升", self.skill)
        self.assertIn("不同任务各自有基线互不排斥", self.skill)

    def test_09c_image_batch_limit_is_declared(self):
        """CONSULT 单次图片上限与分批覆盖要求必须写在接口规则里。"""
        self.assertIn("单次送审图片默认上限 8 张", self.skill)
        self.assertIn("--max-images", self.skill)
        self.assertIn("不得默认全页已审", self.skill)

    def test_09d_partial_failure_does_not_force_three_green(self):
        """允许淘汰不合格方向，但不得把「三张全绿」当目标，也不得只剩一个就免于重出。"""
        self.assertIn("已有至少 2 个合格方向可比时", self.skill)
        self.assertIn("不必为「三张全绿」继续生成", self.skill)
        self.assertIn("只剩 1 个合格方向时仍须按修正建议重出受影响方向", self.skill)

    def test_10_blind_copilot_is_blocked_not_substituted(self):
        block = section(self.skill, "8. 失败处理与降级", level=2)
        self.assertIn("不自行替代裁决、不伪造", block)
        self.assertIn("BLOCKED", block)

    def test_11_adapters_describe_the_channel(self):
        self.assertIn("bridge_evidence.py", self.adapters)
        self.assertIn("call_gpt.py", self.adapters)
        self.assertIn("不能降级的能力", self.adapters)
        self.assertIn("阶段 3 Copilot 基于真实图像裁决", self.adapters)

    def test_12_eligibility_before_comparison(self):
        text = self.stage3()
        for needle in ("**先判合格性**", "**只在合格方向里比较**", "**允许全部拒绝**",
                       "不得选「最不差」", "合格 / 不合格 + 具体依据"):
            self.assertIn(needle, text, "阶段 3 缺少合格性判断要求：%s" % needle)

    def test_13_all_rejected_has_a_next_step(self):
        text = self.stage3()
        self.assertIn("只重出受影响方向", text)
        self.assertIn("不设固定重试轮次", text)
        block = section(self.skill, "8. 失败处理与降级", level=2)
        self.assertIn("三个方向全部不合格（Copilot 拒绝）", block)
        self.assertIn("不重复无信息增量的生成", block)

    def test_14_image_evidence_boundary(self):
        text = self.stage3()
        self.assertIn("**证据边界**", text)
        self.assertIn("图片只能证明可见的设计表达", text)
        self.assertIn("不因静态图无法证明运行时行为就无条件否决全部方向", text)

    def test_15_request_and_record_carry_translated_constraints(self):
        text = self.stage3()
        self.assertIn("与三张 prompt 共用的**任务块**与**原则转译块**", text)
        self.assertIn("未做合格性判断就直接挑「最不差」", text)
        self.assertIn("逐方向合格性结论", text)
        self.assertIn("需在 HTML/原生阶段验证的项", text)
        workflow = read("references/app-visual-workflow.md")
        self.assertIn("## 本页设计目标", workflow)
        self.assertIn("转译块一致性", workflow)
        self.assertIn("未做合格性判断、直接挑「最不差」", workflow)


class ProductPrincipleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.pv = read("references/product-value.md")
        cls.critique = read("references/critique-guide.md")

    def test_01_four_layers_in_order(self):
        self.assertIn("**顺序：有用 → 好懂 → 舒服 → 有意义。**", self.skill)
        block = section(self.skill, "3. 产品原则（三个方向都必须遵守）", level=2)
        for needle in ("有用", "好懂", "舒服", "有意义"):
            self.assertIn(needle, block)
        self.assertIn("有用 → 好懂 → 舒服 → 有意义", self.pv)

    def test_02_gamification_is_optional(self):
        self.assertIn("**游戏化是手段不是目标**", self.skill)
        for needle in ("损失焦虑", "虚假稀缺", "惩罚性连续", "过度竞争", "短期活跃"):
            self.assertIn(needle, self.skill)
        self.assertIn("游戏化是可选手段，不是产品目标", self.pv)

    def test_03_three_lenses_are_not_a_checklist(self):
        self.assertIn("自主感、掌控感、成长感是判断视角，**不是功能清单**", self.skill)
        self.assertIn("不是功能清单", self.pv)

    def test_04_density_is_legitimate(self):
        self.assertIn("专业信息密度", self.skill)
        self.assertIn("装饰性 icon", self.skill)
        self.assertIn("允许合理提高信息密度", self.pv)

    def test_05_direction_tied_to_product_positioning(self):
        self.assertIn("方向必须与产品定位/场景/用户绑定", self.skill)
        self.assertIn("不是风格抽签", self.skill)

    def test_06_critique_keeps_four_questions_without_new_gates(self):
        self.assertIn("复杂度转嫁", self.critique)
        self.assertIn("不新增评分维度、不新增 Gate", self.critique)
        self.assertIn("视觉噪音与干扰", self.critique)

    def test_07_project_principles_outrank_skill_preferences(self):
        self.assertIn("项目规则定义产品原则时，**项目优先**", self.skill)
        self.assertIn("**产品原则的权威在项目**", self.skill)
        self.assertIn("不得被项目规则或本 skill 放宽", self.skill)


class ScopeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.docs = {rel: read(rel) for rel in doc_paths()}

    def test_01_app_only_scope_table(self):
        block = section(self.skill, "0. 定位与边界", level=2)
        self.assertIn("**只做 App UI**", block)
        for needle in ("幻灯片 / PPT / deck", "视频 / 动画成片 / 宣传片", "配音 / 音频 / 音乐 / SFX",
                       "信息图 / 海报 / 封面等静态平面载体", "生产级 Web App"):
            self.assertIn(needle, block, "范围表缺少排除项：%s" % needle)

    def test_02_retired_carriers_are_not_referenced(self):
        for rel, text in self.docs.items():
            for needle in RETIRED_PATHS:
                self.assertNotIn(needle, text, "%s 仍引用已下线资产：%s" % (rel, needle))

    def test_03_retired_files_are_gone(self):
        for rel in ("references/gpt-visual-workflow.md", "references/materials.md",
                    "references/slide-decks.md", "references/editable-pptx.md",
                    "references/ui-demo-animation.md", "references/video-export.md",
                    "assets/animations.jsx", "assets/deck_stage.js",
                    "scripts/render-video.js", "scripts/html2pptx.js",
                    "scripts/design-gate-check.js", "scripts/check-assets.py"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, rel)),
                             "已下线的文件仍在仓库：%s" % rel)

    def test_04_components_are_app_only(self):
        comp = read("references/components-and-output.md")
        for needle in ("ios_frame.jsx", "android_frame.jsx", "design_canvas.jsx"):
            self.assertIn(needle, comp)
        for gone in ("deck_stage", "macos_window", "browser_window", "cursor.jsx",
                     "animations.jsx"):
            self.assertNotIn(gone, comp)
        self.assertIn("本 skill 只服务 App UI", comp)

    def test_05_no_upstream_sync_dependency(self):
        host = read("references/zcode-host.md")
        self.assertIn("不依赖其他 skill", host)
        self.assertIn("无同步、无继承、无运行时关联", host)
        comp = read("references/components-and-output.md")
        self.assertIn("不做上游版本对比", comp)
        self.assertIn("独立维护", comp)

    def test_06_gpt_image_capability_is_absorbed(self):
        gen = read("references/image-generation.md")
        assets = read("references/image-assets.md")
        for text, needles in (
            (gen, ("提示词", "构图", "风格", "参考图", "--size", "批量", "失败")),
            (assets, ("复用", "清单", "sha256", "溯源", "裁切")),
        ):
            for needle in needles:
                self.assertIn(needle, text)
        self.assertIn("huashu-gpt-image", read("THIRD_PARTY_NOTICES.md"))
        self.assertIn("huashu-gpt-image", read("README.md"))


class QualityGateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.verification = read("references/verification.md")
        cls.handoff = read("references/design-handoff.md")

    def test_01_real_evidence_red_line(self):
        self.assertIn("**真实证据**：方向判断看真实图片，原型看真实渲染，原生看真机", self.skill)
        self.assertIn("**不伪造结论**", self.skill)
        self.assertIn("CSS px 不能直接证明 Android 48dp", self.verification)

    def test_02_dp_and_touch_targets(self):
        self.assertIn("dp/sp 不照抄 CSS px", self.skill)
        self.assertIn("48×48dp", self.verification)
        self.assertIn("48dp", self.handoff)

    def test_03_business_assertions_are_independent(self):
        self.assertIn("业务断言必须独立推导", self.verification)
        self.assertIn("不得复制 UI 里手写的顺序/数值/文案", self.verification)

    def test_04_states_are_mandatory(self):
        self.assertIn("状态必须完整：默认 / 加载 / 空 / 错误 / 数据不足", self.skill)
        self.assertIn("至少覆盖：默认、加载、空、错误、数据不足", self.verification)

    def test_05_verdict_has_three_states(self):
        self.assertIn("**PASS**", self.skill)
        self.assertIn("**PARTIAL**", self.skill)
        self.assertIn("**BLOCKED**", self.skill)
        self.assertIn("**未验证项不得写成通过。**", self.skill)

    def test_06_device_install_goes_through_authorised_entry(self):
        self.assertIn("~/.zcode/skills/app-testing/runtime/mi6-verify/adb-auto-install.sh",
                      self.skill)
        self.assertIn("**禁止裸 `adb install`**", self.skill)
        self.assertIn("多台设备在线即停止", self.skill)
        self.assertIn("adb-auto-install.sh", self.verification)

    def test_07_acceptance_matrix_covers_ten_dimensions(self):
        start = self.skill.index("**阶段 7 · 真机验收与收口**")
        block = self.skill[start:self.skill.index("产物：`verification-report.md`", start)]
        for needle in ("方向一致性", "布局与信息层级", "字体与排版", "色彩与对比度", "素材",
                       "状态", "真实业务数据", "触控与交互", "平台规范", "性能与稳定性"):
            self.assertIn(needle, block, "验收矩阵缺少：%s" % needle)

    def test_08_contrast_thresholds(self):
        self.assertIn("正文 ≥4.5:1", self.skill)
        self.assertIn("重要图标/图形 ≥3:1", self.skill)


class RoleBoundaryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")

    def test_01_skill_is_method_not_executor(self):
        for needle in ("设计方法与质量规范，不是独立工程执行 Agent",
                       "**ZCode 原生 Agent** 是工程执行主体",
                       "本 skill 提供方法、流程与质量约束"):
            self.assertIn(needle, self.skill)

    def test_02_business_decisions_stay_upstream(self):
        self.assertIn("业务目标、优先级、重大取舍与产品层方案归他们", self.skill)
        self.assertIn("不代替其作重大业务决策", self.skill)

    def test_03_copilot_governance_and_sol_boundary(self):
        for needle in ("负责协作治理", "不实施代码", "不复制 Copilot 的任务状态机与审计机制",
                       "**SOL 不属于本 skill 的设计执行体系。**"):
            self.assertIn(needle, self.skill)

    def test_04_authorisation_surfaces_are_listed(self):
        block = section(self.skill, "5.4 授权与证据")
        self.assertIn("需另行授权", block)
        for needle in ("Git push", "新增 Provider", "改全局 Hook"):
            self.assertIn(needle, block)


class DocConsistencyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.routing = read("references/routing-table.md")
        cls.workflow = read("references/workflow.md")
        cls.adapters = read("references/runtime-adapters.md")
        cls.host = read("references/zcode-host.md")
        cls.manifest_doc = read("references/image-assets.md")

    def test_01_every_reference_linked_from_skill_exists(self):
        for rel in set(re.findall(r"`(references/[^`]+?\.md)`", self.skill)):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)),
                            "SKILL.md 指向不存在的文件：%s" % rel)

    def test_02_entry_list_is_complete(self):
        block = section(self.skill, "9. 参考入口", level=2)
        for rel in ("references/app-visual-workflow.md", "references/image-generation.md",
                    "references/image-assets.md", "references/design-handoff.md",
                    "references/routing-table.md", "references/runtime-adapters.md"):
            self.assertIn(rel, block, "参考入口缺少：%s" % rel)

    def test_03_routing_and_workflow_defer_to_skill(self):
        self.assertIn("以 `SKILL.md` 为准", self.routing)
        self.assertIn("以 `SKILL.md` 为准", self.workflow)
        self.assertIn("不另立流程", self.routing)

    def test_04_manifest_schema_matches_tool(self):
        for needle in ("asset-manifest.json", "sha256", "provenance", "consumers", "variants",
                       "status"):
            self.assertIn(needle, self.manifest_doc)
        self.assertIn("scripts/asset_manifest.py", self.manifest_doc)
        self.assertIn("asset_manifest.py", self.skill)

    def test_05_host_mapping_names_real_scripts(self):
        for needle in ("scripts/zcode_image.py", "scripts/verify.py", "asset_manifest.py",
                       "bridge_evidence.py", "adb-auto-install.sh"):
            self.assertIn(needle, self.adapters + self.host)

    def test_06_check_skill_required_lists_match_reality(self):
        checker = read("scripts/check-skill.py")
        for need in ("references/app-visual-workflow.md", "references/image-generation.md",
                     "references/image-assets.md", "THIRD_PARTY_NOTICES.md",
                     "scripts/asset_manifest.py", "scripts/extract_grid.py"):
            self.assertIn(need, checker, "check-skill 必检清单缺少：%s" % need)
        for gone in ("references/gpt-visual-workflow.md", "references/materials.md",
                     "scripts/render-video.js", "scripts/design-gate-check.js"):
            self.assertNotIn(gone, checker, "check-skill 仍要求已下线文件：%s" % gone)


class WholePageUnderstandingContractTests(unittest.TestCase):
    """整机重设计必须从全页面产品理解开始，数量与截图不构成理解。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.routing = read("references/routing-table.md")

    def test_01_whole_app_redesign_requires_page_map(self):
        block = stage_block(self.skill, 0)
        self.assertIn("**整机 / 多页面系统级重设计：先建页面地图，再谈方向**", block)
        self.assertIn("页面 `P1…`、弹层/状态 `S1…`", block)
        self.assertIn("范围内全部用户可见页面、弹窗、底部弹层、Widget/通知与重要交互状态", block)
        self.assertIn("**数量与截图不能单独证明理解完成**", block)

    def test_02_page_map_has_per_page_judgement_fields(self):
        block = stage_block(self.skill, 0)
        for needle in ("用户目标", "主要功能", "关键信息与数据口径", "业务规则",
                       "值得保留的成熟体验（附依据）", "确认要重构的部分",
                       "导航与信息架构、关键任务路径", "空 / 加载 / 错误 / 权限 / 大字体"):
            self.assertIn(needle, block, "页面地图缺少：%s" % needle)

    def test_03_missing_facts_are_graded(self):
        block = stage_block(self.skill, 0)
        self.assertIn("关键事实缺失为 `PARTIAL`", block)
        self.assertIn("无法取得且影响方向判断为 `BLOCKED`", block)

    def test_04_gate_zero_rejects_count_as_understanding(self):
        row = next(r for r in stage_table_rows(self.skill) if r.startswith("| **0 "))
        self.assertIn("数量与截图不能单独证明理解", row)

    def test_05_workflow_has_page_map_template(self):
        block = section(self.workflow, "1.4 页面地图（整机 / 多页面重设计必需）")
        self.assertIn("只有数量和截图不能证明理解完成", block)
        # 模板表格位于 fenced markdown 块内，标题行会提前截断 section()，因此全文匹配。
        self.assertIn("| id | 用户目标 | 主要功能 | 关键信息与数据口径 | 业务规则 | 适用状态 | 当前主要问题 | 值得保留（依据） | 要重构 |", self.workflow)

    def test_06_routing_sends_whole_app_designs_to_page_map(self):
        self.assertIn("整机 / 多页面系统级重设计", self.routing)
        self.assertIn("不得用页面数量与截图代替理解", self.routing)


class PromptPreReviewContractTests(unittest.TestCase):
    """阶段 2 的提示词预审是生图前硬前置，只审文本、不选方向。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.routing = read("references/routing-table.md")
        cls.adapters = read("references/runtime-adapters.md")

    def test_01_pre_review_is_mandatory_before_generation(self):
        block = stage_block(self.skill, 2)
        self.assertIn("**生图前必须先做提示词预审（阶段内动作顺序，不新增 Gate）**", block)

    def test_02_pre_review_uses_text_evidence_only(self):
        block = stage_block(self.skill, 2)
        self.assertIn("**不得伪造图片证据**", block)
        self.assertIn("bridge_evidence.py", block)
        self.assertIn("call_gpt.py --mode CONSULT", block)

    def test_03_pre_review_does_not_select_direction(self):
        block = stage_block(self.skill, 2)
        self.assertIn("**本步不选方向**", block)
        self.assertIn("不得要求 Copilot 在生图前定方向", block)

    def test_04_review_is_bound_to_generated_version(self):
        block = stage_block(self.skill, 2)
        self.assertIn("「预审版本 → 实际生成版本」", block)
        self.assertIn("**过度锁死解法**", block)
        row = next(r for r in stage_table_rows(self.skill) if r.startswith("| **2 "))
        self.assertIn("预审已发生且修订绑定生成版本", row)

    def test_05_unavailable_pre_review_pauses_generation(self):
        block = stage_block(self.skill, 2)
        self.assertIn("暂停本任务概念图生成并报 `BLOCKED`", block)
        self.assertIn("已预审", block)
        self.assertIn("阶段 2 提示词预审", self.adapters)
        self.assertIn("预审不可用则暂停生成", self.adapters)

    def test_06_generating_before_review_is_forbidden(self):
        block = section(self.workflow, "3.4 生图前 CONSULT 预审（硬前置）")
        self.assertIn("**不允许先出图再补审**", block)
        self.assertIn("不新增 Gate", block)

    def test_07_review_line_is_not_formal_review(self):
        review_section = self.routing.split("## 4. 评审线")[1]
        self.assertIn("提示词预审", review_section)
        self.assertIn("不是正式 REVIEW", review_section)


class DirectionExitContractTests(unittest.TestCase):
    """方向决策支持采用 / 融合 / 全部拒绝，融合必须有统一逻辑与补图条件。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.adapters = read("references/runtime-adapters.md")

    def test_01_three_exits_are_explicit(self):
        block = stage_block(self.skill, 3)
        self.assertIn("三种出口", block)
        for needle in ("**直接采用**", "**融合**", "**全部拒绝**", "**单一目标方案**"):
            self.assertIn(needle, block)

    def test_02_fusion_states_kept_dropped_and_unified_logic(self):
        block = stage_block(self.skill, 3)
        for needle in ("说明取用哪些元素、舍弃哪些", "融合后的层级与交互逻辑",
                       "**保留 / 舍弃 / 整体逻辑**"):
            self.assertIn(needle, block)

    def test_03_structural_fusion_requires_real_merged_image(self):
        block = stage_block(self.skill, 3)
        self.assertIn("**融合的补图条件**", block)
        self.assertIn("**必须补一张真实整合概念图并再次送检**", block)
        self.assertIn("不为仪式强制重出图", block)

    def test_04_collage_is_not_fusion(self):
        self.assertIn("拼图式堆叠", self.skill)
        self.assertIn("视为方向未定", self.skill)
        self.assertIn("不允许把三个方向的元素拼成无逻辑的拼图", self.workflow)
        self.assertIn("不得把拼图当融合", self.adapters)
        self.assertIn("拼图不算融合", read("references/workflow.md"))


class PrototypeDesignReviewContractTests(unittest.TestCase):
    """阶段 4 的设计质量评审必须基于真实截图，渲染成功不等于通过。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.critique = read("references/critique-guide.md")

    def test_01_design_review_is_required_after_render(self):
        block = stage_block(self.skill, 4)
        self.assertIn("**设计质量评审（渲染之后、交付之前，CONSULT）**", block)
        self.assertIn("机械校验通过不等于设计完成", block)

    def test_02_review_checks_expression_hierarchy_and_completeness(self):
        block = stage_block(self.skill, 4)
        for needle in ("产品功能是否正确表达", "信息架构、视觉层级与核心操作",
                       "关键页面、状态、组件是否完整", "是否遵循已定目标方案"):
            self.assertIn(needle, block)

    def test_03_review_catches_pretty_but_impractical(self):
        block = stage_block(self.skill, 4)
        for needle in ("漂亮但不实用", "信息被过度隐藏", "无价值的装饰"):
            self.assertIn(needle, block)

    def test_04_render_success_is_not_gate_pass(self):
        block = stage_block(self.skill, 4)
        self.assertIn("不得声称 G4 通过", block)
        row = next(r for r in stage_table_rows(self.skill) if r.startswith("| **4 "))
        self.assertIn("渲染成功本身不算通过", row)

    def test_05_no_fixed_rounds_and_review_is_recorded(self):
        block = stage_block(self.skill, 4)
        self.assertIn("不设固定轮次", block)
        self.assertIn("送入截图清单与 sha256", block)

    def test_06_workflow_and_critique_expand_the_review(self):
        block = section(self.workflow, "5.7 设计质量评审（CONSULT，渲染之后）")
        self.assertIn("真实渲染截图", block)
        self.assertIn("机械校验", block)
        review = section(self.critique, "原型设计评审（阶段 4 · CONSULT）", level=2)
        self.assertIn("真实渲染截图", review)
        section(self.critique, "三方落地对照（阶段 6–7）", level=2)


class NativeLandingContractTests(unittest.TestCase):
    """HTML 是设计目标，不是配色参考；落地要有映射与三方真实对照。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.handoff = read("references/design-handoff.md")
        cls.verification = read("references/verification.md")
        cls.routing = read("references/routing-table.md")

    def test_01_html_is_the_design_target_not_a_colour_reference(self):
        block = stage_block(self.skill, 6)
        self.assertIn("**设计落地不是换皮**", block)
        self.assertIn("不是配色参考", block)
        for needle in ("最小代码改动", "旧页面现成可复用", "契约测试锁住了"):
            self.assertIn(needle, block)

    def test_02_landing_map_is_per_page_or_shared_structure(self):
        block = stage_block(self.skill, 6)
        self.assertIn("**落地映射（逐页 / 逐公共结构）**", block)
        self.assertIn("**构建成功、token 替换、全局换圆角或底色都不能替代这张表。**", block)
        row = next(r for r in stage_table_rows(self.skill) if r.startswith("| **6 "))
        self.assertIn("token 替换与构建成功不能替代落地证明", row)

    def test_03_three_way_comparison_is_mandatory(self):
        block = stage_block(self.skill, 6)
        self.assertIn("**三方真实视觉对照（旧版 App ↔ HTML 目标原型 ↔ 新版真机 App）**", block)
        self.assertIn("不得只看首页就推断次级页已落地", block)
        self.assertIn("不得为补基线擅自降级安装、清数据或恢复旧包", block)

    def test_04_retention_needs_real_grounds(self):
        block = stage_block(self.skill, 6)
        self.assertIn("保留必须有依据（用户任务、可读性、平台惯例、成熟体验）", block)

    def test_05_workflow_has_the_landing_table(self):
        block = section(self.workflow, "7.2 设计落地映射（不是 token 替换）")
        self.assertIn("| 页面/状态或公共结构 | 原有问题或保留依据 | HTML 目标意图 | 原生实现/保留/平台适配 | 旧/HTML/新证据引用 | 结果、偏差与修复 |", block)
        self.assertIn("token", block)

    def test_06_handoff_and_routing_carry_the_landing_rule(self):
        self.assertIn("**落地不是换皮**", self.routing)
        section(self.handoff, "3.4 设计目标 vs 实现自由")
        three = section(self.handoff, "6.2 三方真实对照（旧版 App ↔ HTML 目标原型 ↔ 新版真机 App）")
        self.assertIn("旧版", three)
        self.assertIn("构建/安装/启动成功不等于设计落地", self.verification)


class DualAcceptanceContractTests(unittest.TestCase):
    """验收分工程与设计两条线，两项都达标才 PASS。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.verification = read("references/verification.md")
        cls.readme_zh = read("README.md")
        cls.readme_en = read("README.en.md")

    def test_01_two_verdicts_in_one_report(self):
        block = stage_block(self.skill, 7)
        self.assertIn("**同一份报告分别给两条结论，两项都达标才算整体通过**", block)
        self.assertIn("**工程验收**", block)
        self.assertIn("**设计验收**", block)

    def test_02_design_acceptance_has_product_criteria(self):
        block = stage_block(self.skill, 7)
        for needle in ("产品目标达成", "页面与状态覆盖完整", "四原则落实",
                       "原型设计意图正确实现", "真机体验达到目标"):
            self.assertIn(needle, block)

    def test_03_vanity_metrics_are_forbidden(self):
        block = stage_block(self.skill, 7)
        self.assertIn(
            "**不得用代码修改量、视觉变化百分比、页面改动数量、测试数量替代设计成功**", block)

    def test_04_matrix_adds_intent_and_old_comparison(self):
        block = stage_block(self.skill, 7)
        self.assertIn("| 设计意图落地 |", block)
        self.assertIn("| 旧版对照与改善 |", block)

    def test_05_workflow_and_verification_split_acceptance(self):
        block = section(self.workflow, "8.1 工程与设计双验收")
        self.assertIn("工程验收", block)
        self.assertIn("设计验收", block)
        v = section(self.verification, "5.1 工程验收与设计验收分开")
        self.assertIn("两项都达标", v)

    def test_06_readmes_state_the_split(self):
        self.assertIn("工程验收", self.readme_zh)
        self.assertIn("设计验收", self.readme_zh)
        self.assertIn("Engineering acceptance", self.readme_en)
        self.assertIn("design acceptance", self.readme_en)


class ForbiddenSubstitutionContractTests(unittest.TestCase):
    """六条负向规则：每种「廉价替代物冒充完成」都必须在文档里被显式写死。"""

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/app-visual-workflow.md")
        cls.routing = read("references/routing-table.md")

    def test_01_page_count_cannot_prove_understanding(self):
        self.assertIn("数量与截图不能单独证明理解", self.skill)

    def test_02_review_cannot_come_after_generation(self):
        self.assertIn("**不允许先出图再补审**", self.workflow)

    def test_03_collage_cannot_stand_in_for_fusion(self):
        self.assertIn("不允许把三个方向的元素拼成无逻辑的拼图", self.workflow)

    def test_04_green_render_cannot_stand_in_for_design_review(self):
        self.assertIn("渲染成功本身不算通过", self.skill)
        self.assertIn("机械校验通过不等于设计完成", self.skill)

    def test_05_token_swap_cannot_stand_in_for_landing(self):
        self.assertIn("token 替换与构建成功不能替代落地证明", self.skill)
        self.assertIn("构建成功、token 替换不算落地", self.routing)

    def test_06_test_count_cannot_stand_in_for_design_success(self):
        self.assertIn("测试数量替代设计成功", self.skill)

    def test_07_these_tests_carry_their_own_limit(self):
        # 只证明规则被写下；设计效果必须由真实概念图/截图/真机证据判断。
        text = read("scripts/test_skill_routing.py")
        self.assertIn("只能证明规则被写下", text)
        self.assertIn("不能证明真实设计质量", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
