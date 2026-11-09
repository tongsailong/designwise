#!/usr/bin/env python3
"""App UI 单一标准流程的文档契约测试。

守的是「流程真的只有一条、三方向与 Copilot 裁决真的不可跳过、范围真的只剩 App UI」：

1. **单一流程**：`SKILL.md` 只有 0–7 八个阶段，没有任务分层，阶段表与阶段细则一一对应。
2. **三方向**：恰好 3 个、结构性差异、一方向一 prompt、同比例同尺寸同模型、真实生图、
   不得用 HTML/SVG/占位图冒充、单张失败只重出该方向。
3. **Copilot 裁决**：三张图全部进入请求、`CONSULT` 而非正式 REVIEW、失败关闭五条件、
   `direction-approved.md` 字段齐全、裁决前不得创建该文件。
4. **流程分支**：局部迭代复用既有记录不重跑方向；实质变化重走 0–7。
5. **范围**：只做 App UI；已下线的载体文档与脚本不得再被引用。
6. **产品原则**：四层顺序、游戏化可选、专业密度正当、自主感三视角不是功能清单。
7. **质量与证据**：真实证据、dp/sp 与 48dp、业务断言独立、三态结论、真机装包入口。
8. **角色边界**：本 skill 是方法与质量规范，ZCode 原生 Agent 是执行主体。

这些是文档契约测试：读真实文件、检查真实规则内容与跨文档一致性，不执行渲染、不调模型。
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
        for stale in ("不替代 G4", "不声称 G4"):
            self.assertNotIn(stale, self.skill, "Gate 编号残留：%s" % stale)
        for path in doc_paths():
            text = read(path)
            for stale in ("不替代 G4", "不声称 G4", "design-demos/concepts/"):
                self.assertNotIn(stale, text, "%s 残留：%s" % (path, stale))

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

    def test_10_blind_copilot_is_blocked_not_substituted(self):
        block = section(self.skill, "8. 失败处理与降级", level=2)
        self.assertIn("不自行替代裁决、不伪造", block)
        self.assertIn("BLOCKED", block)

    def test_11_adapters_describe_the_channel(self):
        self.assertIn("bridge_evidence.py", self.adapters)
        self.assertIn("call_gpt.py", self.adapters)
        self.assertIn("不能降级的能力", self.adapters)
        self.assertIn("阶段 3 Copilot 基于真实图像裁决", self.adapters)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
