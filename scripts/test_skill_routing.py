#!/usr/bin/env python3
"""路由优先级回归：L1 / L2 / L3 分流与硬门槛的文档契约。

这些测试保护的是「任务分层优先于通用流程」这一结构：
- L2 只有一个任务路由入口，默认 GPT 概念图通路；
- L1 不被通用 variations / 三方向 / Gate 1 规则反向覆盖；
- L3 保留自己的专业工作流；
- 授权、Gate、失败关闭、48dp 与业务断言等硬规则仍然存在。

它们是文档契约测试，不执行真实渲染，也不调用外部模型。
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


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


class RoutingPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/workflow.md")
        cls.routing = read("references/routing-table.md")
        cls.adapters = read("references/runtime-adapters.md")
        cls.product_value = read("references/product-value.md")

    def routing_rows(self):
        body = self.skill[
            self.skill.index("## 任务路由"):self.skill.index("### 任务分层")
        ]
        return [line for line in body.splitlines()
                if line.startswith("|") and "---" not in line]

    def test_l2_has_one_routing_entry(self):
        rows = [row for row in self.routing_rows()
                if re.search(r"\bL2\b",
                             row.strip().strip("|").split("|")[0])]
        self.assertEqual(len(rows), 1, "L2 必须只有一个任务路由入口: %r" % rows)
        row = rows[0]
        for needle in ("默认", "GPT", "Visual Brief", "每方向 1 张真实候选图",
                       "Gate 1", "停轮等用户选定", "收敛提示词", "正式概念图",
                       "visual-translation.md", "只对选定方向按需做一套 HTML",
                       "客观验证", "Gate 2", "HTML fallback", "三种例外",
                       "依据记入 `design-brief.md` 或 `direction-approved.md`"):
            self.assertIn(needle, row)
        self.assertNotIn("Fallback Phase 1-5", row)

    def test_l1_row_does_not_require_direction_gate(self):
        row = next(line for line in self.skill.splitlines()
                   if "**L1 · 既有体系内的局部优化**" in line)
        for needle in ("默认直接改现有 UI", "不做三方向", "Gate 1 不适用"):
            self.assertIn(needle, row)
        self.assertNotIn("direction-approved.md", row)

    def test_product_ui_row_defers_to_l1_l2(self):
        row = next(row for row in self.routing_rows()
                   if "产品界面 / 交互原型" in row)
        self.assertIn("先按「任务分层」判 L1/L2", row)
        self.assertIn("L1 直接改现有 UI", row)
        if "三方向" in row:
            self.assertIn("不强制三方向", row)

    def test_variation_rules_are_scoped(self):
        philosophy = section(
            self.skill, "3. 给variations（L2 / 用户明确要求），不给「最终答案」")
        for needle in ("L1", "L2", "L3", "默认直接改现有 UI"):
            self.assertIn(needle, philosophy)

        step6 = next(line for line in self.skill.splitlines()
                     if line.startswith("6. **Full pass**"))
        for needle in ("L1", "L2"):
            self.assertIn(needle, step6)

        question = next(line for line in self.skill.splitlines()
                        if "想要几种" in line and "variations" in line)
        for needle in ("L1", "L2"):
            self.assertIn(needle, question)

    def test_workflow_variations_are_scoped(self):
        variations = section(self.workflow, "2. Variations维度")
        for needle in ("L1", "L2"):
            self.assertIn(needle, variations)

        deep = section(self.workflow, "Variations的深度逻辑", level=2)
        self.assertIn("适用范围", deep)
        self.assertIn("L1", deep)

        refusal = next(line for line in self.workflow.splitlines()
                       if "拒答问题" in line)
        self.assertIn("仅 L2", refusal)
        self.assertIn("L1", refusal)

    def test_reference_routers_state_l1_exemption(self):
        self.assertIn("不套三方向门", self.routing)
        self.assertIn("L1 不套三方向门", self.adapters)
        self.assertIn("L1 不适用", self.product_value)

    def test_l3_keeps_own_workflow(self):
        l3 = next(line for line in self.skill.splitlines()
                  if "**L3 · 非 UI 载体**" in line)
        self.assertIn("不套 UI 三方向门", l3)
        self.assertIn("不是 UI 方向门", l3)

        l3_rows = [row for row in self.routing_rows()
                   if "幻灯片/PPT" in row or "动画/导出" in row
                   or "launch film" in row or "宣传的产品有 UI 界面" in row]
        self.assertTrue(l3_rows, "L3 任务必须有独立路由行")
        for row in l3_rows:
            self.assertNotIn("GPT 视觉概念生图", row)

        launch = next(row for row in self.routing_rows() if "launch film" in row)
        self.assertIn("方向板", launch)
        demo = next(row for row in self.routing_rows()
                    if "宣传的产品有 UI 界面" in row)
        self.assertIn("ui-demo-animation.md", demo)

    def test_gpt_failure_does_not_silently_fall_back(self):
        workflow = read("references/gpt-visual-workflow.md")
        self.assertNotIn("不改工作流**，保留原有 HTML/CSS 三方向通路", workflow)
        self.assertNotIn("回落 HTML/CSS 三方向", workflow)
        self.assertNotIn("原有 HTML/CSS 通路原样保留", workflow)
        self.assertIn("明确报告技术限制并暂停生图环节", workflow)
        self.assertIn("不得静默改用 HTML/SVG 冒充概念图", workflow)

    def test_no_unscoped_direction_gate_remains(self):
        exception_rule = next(line for line in self.skill.splitlines()
                              if "异常时" in line and "方向门" in line)
        for needle in ("L2", "L1"):
            self.assertIn(needle, exception_rule)

        step1 = next(line for line in self.skill.splitlines()
                     if "多方向硬门（仅 L2" in line)
        self.assertIn("默认走 GPT 通路", step1)
        self.assertIn("Phase 1-3.5", step1)
        self.assertNotIn("Phase 1-5", step1)

        handoff = next(line for line in self.skill.splitlines()
                       if "两套检查点的衔接" in line)
        for needle in ("GPT 通路", "HTML fallback", "Phase 3.5"):
            self.assertIn(needle, handoff)

        gpt = read("references/gpt-visual-workflow.md")
        self.assertIn("不得只做 1 个", gpt)
        self.assertNotIn("只有一个合理视觉方向", gpt)

    def test_verification_scope_is_tiered(self):
        verification = read("references/verification.md")
        self.assertIn("L1 只跑受影响屏/状态的最小矩阵", verification)

    def test_readmes_do_not_promise_universal_direction_gate(self):
        zh = read("README.md")
        en = read("README.en.md")
        self.assertNotIn("收到任何会产出新视觉设计的任务", zh)
        self.assertNotIn("任何新视觉设计", zh)
        self.assertNotIn("Any task that produces new visual design starts", en)
        self.assertIn("**L2（新视觉语言或重大结构变化）**", zh)
        self.assertIn("Any **L2** task", en)

        weak_zh = next(line for line in zh.splitlines()
                       if "仍然出多个方向" in line)
        self.assertIn("L2", weak_zh)
        self.assertIn("L1", weak_zh)
        weak_en = next(line for line in en.splitlines()
                       if "still produces multiple directions" in line)
        self.assertIn("L2", weak_en)
        self.assertIn("L1", weak_en)

    def test_phase_3_5_checkpoint_applies_to_both_paths(self):
        self.assertIn("Phase 3.5 · 🔴 CHECKPOINT 图片素材前置", self.skill)
        self.assertIn("GPT 通路与 HTML fallback 都必须先过本节", self.skill)
        self.assertIn("L2 默认前置；HTML fallback 仅限三种例外", self.skill)

    def test_no_response_uses_default_gpt_path(self):
        line = next(line for line in self.skill.splitlines()
                    if "无应答策略" in line)
        self.assertIn("Phase 3.6/3.7", line)
        self.assertNotIn("Phase 2-4", line)

    def test_gpt_unavailable_statement_is_scoped(self):
        gpt = read("references/gpt-visual-workflow.md")
        one_liner = next(line for line in gpt.splitlines()
                         if "GPT 不可用时" in line and "一句话立场" in line)
        self.assertIn("L2", one_liner)
        self.assertIn("暂停", one_liner)
        self.assertNotIn("原样保留", one_liner)

        baseline = next(line for line in gpt.splitlines()
                        if "降级底线" in line)
        self.assertIn("L2", baseline)
        self.assertIn("暂停", baseline)
        self.assertNotIn("三方向硬门", baseline)

    def test_l2_candidate_recording_requirement(self):
        line = next(line for line in self.skill.splitlines()
                    if line.strip().startswith("**L2 的候选形态**"))
        for needle in ("design-brief.md", "direction-approved.md",
                       "不得只凭执行方"):
            self.assertIn(needle, line)

    def test_l3_deck_has_its_own_direction_workflow(self):
        example = next(line for line in self.skill.splitlines()
                       if "咖啡主题的 PPT" in line)
        self.assertIn("不是 L2 的 Phase 4", example)

        deck = next(line for line in self.skill.splitlines()
                    if "多页 deck 需要三版方向对比时" in line)
        self.assertIn("L3 载体自身规则", deck)
        self.assertIn("L3 载体的方向探索", self.skill)

    def test_brand_asset_l1_exemption(self):
        asset = read("references/brand-asset-protocol.md")
        row = next(line for line in asset.splitlines()
                   if "色值完全找不到" in line)
        self.assertIn("L2", row)
        self.assertIn("L1 局部优化", row)
        self.assertIn("不铺三方向", row)

    def test_flow_header_states_default(self):
        line = next(line for line in self.skill.splitlines()
                    if "完整流程（" in line)
        self.assertIn("默认 GPT 通路", line)
        self.assertIn("HTML fallback 仅限", line)
        self.assertIn("三种例外", line)

    def test_representative_task_routes(self):
        """Dashboard 按钮微调 → L1；App 首页改版 → L2；动画 → L3。"""
        l1 = next(line for line in self.skill.splitlines()
                  if "**L1 · 既有体系内的局部优化**" in line)
        self.assertIn("按钮体系微调", l1)
        self.assertIn("默认直接改现有 UI", l1)
        self.assertIn("Gate 1 不适用", l1)

        l2_row = next(row for row in self.routing_rows()
                      if "**L2" in row or "L2：" in row)
        self.assertIn("首页或重要页面整体设计", l2_row)
        self.assertIn("默认 GPT 视觉概念生图通路", l2_row)

        l3 = next(line for line in self.skill.splitlines()
                  if "**L3 · 非 UI 载体**" in line)
        self.assertIn("动画", l3)

        animation_row = next(row for row in self.routing_rows()
                             if "动画/导出 MP4/GIF" in row)
        self.assertIn("Step 9", animation_row)
        self.assertIn("storyboard-basics.md", animation_row)
        self.assertNotIn("GPT 视觉概念生图", animation_row)

    def test_hard_gates_are_unchanged(self):
        for needle in ("--confirm-gpt-review", "Copilot 正式 REVIEW 仅用户点名",
                       "Gate 1", "Gate 2", "SKIP_DESIGN_GATE", "48dp",
                       "CSS px", "失败关闭"):
            self.assertIn(needle, self.skill)

        verification = read("references/verification.md")
        self.assertIn("业务断言必须独立推导", verification)
        self.assertIn("HTML 的 CSS px 不能直接证明 Android 48dp", verification)
        self.assertIn("48×48dp", verification)
        self.assertIn("不得复制 UI 里手写的顺序 / 数值 / 文案", verification)

    # ── L1 轻量流程（2026-10-29）──────────────────────────────
    L1_HEADING = "L1 四步流程（最高优先，覆盖通用流程偏好）"

    def test_l1_four_step_flow_is_defined(self):
        block = section(self.skill, self.L1_HEADING)
        for step in ("理解现状", "直接修改", "针对性验证", "交付"):
            self.assertIn(step, block)
        for needle in ("不强制提问", "默认只实现一个方案", "不强制生图",
                       "不产出", "design-state.md", "不因普通局部改动自动启动"):
            self.assertIn(needle, block)

    def test_l1_verification_keeps_hard_gates(self):
        block = section(self.skill, self.L1_HEADING)
        for needle in ("Android 原生按 dp", "不能用 HTML CSS px 代替",
                       "业务规则断言必须独立于 UI 自报结果",
                       "触控、字号、对比度、字体缩放、布局溢出与交互"):
            self.assertIn(needle, block)

    def test_l1_does_not_enter_direction_consultant_or_long_spec(self):
        head = self.skill[self.skill.index("## 设计方向顾问（Fallback 模式）"):][:500]
        self.assertIn("L1 不进入本节", head)
        self.assertIn("≥200 字", head)
        self.assertIn("≥500 字", head)
        self.assertIn("不跑 Phase 1-5", head)

    def test_standard_checkpoints_are_scoped_for_l1(self):
        flow = section(self.skill, "标准流程（用TaskCreate追踪）")
        self.assertIn("L1 走「L1 四步流程」", flow)
        for label in ("检查点1", "检查点2·资产自检", "检查点3", "检查点4", "检查点5"):
            line = next(l for l in self.skill.splitlines()
                        if ("**" + label) in l and "🛑" in l)
            self.assertIn("L1", line, "%s 必须标明 L1 口径" % label)
        principle = next(l for l in self.skill.splitlines()
                         if l.startswith("**检查点原则**"))
        self.assertIn("L1", principle)
        self.assertIn("不因确认而停轮", principle)

    def test_l1_preserves_authorization_and_reclassification(self):
        block = section(self.skill, self.L1_HEADING)
        for needle in ("用户明确要求多个视觉方案", "选择权",
                       "重新判型为 L2", "不看页面数量",
                       "权限、安全、发布或生产数据",
                       "不因 L1 简化获得任何新授权"):
            self.assertIn(needle, block)

    def test_l1_fast_path_is_linked_from_references(self):
        self.assertIn("L1 四步流程", self.routing)
        self.assertIn("L1 四步流程", self.workflow)
        fast = section(self.workflow, "L1 快速路径（优先于本文件其余流程偏好）", level=2)
        for needle in ("理解现状", "直接改现有 UI", "只验受影响屏", "极简交付"):
            self.assertIn(needle, fast)
        junior = section(self.workflow, "Junior Designer模式", level=2)
        self.assertIn("L1 局部改动不走 Pass 1-4", junior)

    def test_l1_acceptance_scenarios(self):
        """A 按钮尺寸 / B 弹窗局部 / C 字体适配 / D 首页整体 / E 多方案要求 / F 授权。"""
        block = section(self.skill, self.L1_HEADING)
        row = next(line for line in self.skill.splitlines()
                   if "**L1 · 既有体系内的局部优化**" in line)
        self.assertIn("按钮体系微调", row)          # A
        self.assertIn("弹窗", row)                  # B
        self.assertIn("字号", block)                # C
        self.assertIn("Android 原生按 dp", block)   # C：原生仍需真实验证
        l2_row = next(r for r in self.routing_rows() if "**L2" in r or "L2：" in r)
        self.assertIn("首页或重要页面整体设计", l2_row)   # D
        self.assertIn("用户明确要求多个方案", block)      # E
        self.assertIn("不因 L1 简化获得任何新授权", block)  # F

    def test_l2_direction_gate_unchanged_by_l1_work(self):
        """L1 轻量化不得稀释 L2 的停轮与方向选择。"""
        for needle in ("停轮等用户选定", "默认 **3 个**", "不得只做 1 个",
                       "唯一豁免（仅此三种"):
            self.assertIn(needle, self.skill)
        gpt = read("references/gpt-visual-workflow.md")
        self.assertIn("不得只做 1 个", gpt)
        self.assertIn("不得静默改用 HTML/SVG 冒充概念图", gpt)
        l3 = next(line for line in self.skill.splitlines()
                  if "**L3 · 非 UI 载体**" in line)
        self.assertIn("不套 UI 三方向门", l3)


if __name__ == "__main__":
    unittest.main()
