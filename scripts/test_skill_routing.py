#!/usr/bin/env python3
"""路由与默认设计策略的文档契约测试。

三类契约：

1. **任务路由**：L1 / L2 / L3 分流，L1 不被通用 variations / 方向门反向覆盖，
   L3 保留自己的专业工作流，授权、Gate、失败关闭、48dp 与业务断言等硬规则仍在。
2. **默认设计策略（2026-10-30 归并）**：`SKILL.md`「项目规则优先」是方案数量、
   设计自由度与产品原则权威的唯一口径——默认单一最佳方案、替代方向只在实质分歧
   或用户明确要求时出现、项目规则可以更严、业务与合规边界与质量门槛不放宽。
3. **效力分层与交付物数量（2026-10-30 精修）**：规则效力按职责分 5 层（全局安全 →
   用户决策 → 项目规则 → `SKILL.md` → `references/`），分层排序只在 `SKILL.md` 维护；
   设计方向数量（默认 1）与实际交付物数量相互独立，L3 不因方向数为 1 就限制
   页面 / 尺寸 / 状态 / 组件变体 / 导出格式的数量。

这些是文档契约测试：读真实文件、检查真实规则内容与跨文档一致性，
不执行渲染，也不调用外部模型。
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 「项目规则优先」是方案数量 / 设计自由度 / 产品原则权威的唯一口径。
RULE_HEADING = "项目规则优先（产品原则 / 设计自由度 / 方案数量）"

# 已废止的强制多方向口径：SKILL.md、references 与两份 README 的规则文本里都不该再出现（断言范围见下方用例）。
BANNED_RULE_PATTERNS = (
    "不得只做 1 个",
    "默认 **3 个**",
    "默认 3 个",
    "默认 3 版",
    "推荐 3+",
    "三方向硬门",
    "多方向硬门",
    "唯一豁免（仅此三种",
    "仍然出多个方向",
    "still produces multiple directions",
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


def reference_docs():
    """All references/*.md as {relative path: text}."""
    folder = os.path.join(ROOT, "references")
    return {os.path.join("references", name): read(os.path.join("references", name))
            for name in sorted(os.listdir(folder))
            if name.endswith(".md")}


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
        for needle in ("默认 GPT 视觉概念生图通路", "默认单一最佳方案",
                       "Visual Brief", "多方向每方向 1 张",
                       "Gate 1", "单一方案直接收敛概念图进入实现",
                       "停轮等用户选定", "收敛提示词", "正式概念图",
                       "visual-translation.md", "按需做一套 HTML",
                       "客观验证", "Gate 2", "HTML fallback", "三种例外",
                       "依据记入 `design-brief.md` 或 `direction-approved.md`"):
            self.assertIn(needle, row)
        self.assertNotIn("Fallback Phase 1-5", row)

    def test_l1_row_does_not_require_direction_gate(self):
        row = next(line for line in self.skill.splitlines()
                   if "**L1 · 既有体系内的局部优化**" in line)
        for needle in ("默认直接改现有 UI", "不做多方向门", "Gate 1 不适用"):
            self.assertIn(needle, row)
        self.assertNotIn("direction-approved.md", row)

    def test_product_ui_row_defers_to_l1_l2(self):
        row = next(row for row in self.routing_rows()
                   if "产品界面 / 交互原型" in row)
        self.assertIn("先按「任务分层」判 L1/L2", row)
        self.assertIn("L1 直接改现有 UI", row)
        self.assertIn("不强制多方向", row)

    def test_variation_rules_are_scoped(self):
        philosophy = section(
            self.skill, "3. 给variations（实质分歧 / 用户明确要求），不给「最终答案」")
        for needle in ("L1", "L2", "L3", "默认直接改现有 UI"):
            self.assertIn(needle, philosophy)

        step6 = next(line for line in self.skill.splitlines()
                     if line.startswith("6. **Full pass**"))
        for needle in ("L1", "L2"):
            self.assertIn(needle, step6)

        question = next(line for line in self.skill.splitlines()
                        if "想要几种 variations" in line)
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
        self.assertIn("不套多方向门", self.routing)
        self.assertIn("L1 不套方向门", self.adapters)
        self.assertIn("L1 不适用", self.product_value)

    def test_l3_keeps_own_workflow(self):
        l3 = next(line for line in self.skill.splitlines()
                  if "**L3 · 非 UI 载体**" in line)
        self.assertIn("不套 UI 多方向门", l3)
        self.assertNotIn("GPT 视觉概念生图", l3)

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
                     if "视觉方向门（仅 L2" in line)
        self.assertIn("默认走 GPT 通路", step1)
        self.assertIn("Phase 1-3.5", step1)
        self.assertNotIn("Phase 1-5", step1)

        handoff = next(line for line in self.skill.splitlines()
                       if "两套检查点的衔接" in line)
        for needle in ("GPT 通路", "HTML fallback", "Phase 3.5"):
            self.assertIn(needle, handoff)

        gpt = read("references/gpt-visual-workflow.md")
        self.assertIn("不得把单方向包装成多方向比较", gpt)
        self.assertNotIn("只有一个合理视觉方向", gpt)

    def test_verification_scope_is_tiered(self):
        verification = read("references/verification.md")
        self.assertIn("L1 只跑受影响屏/状态的最小矩阵", verification)

    def test_readmes_state_single_scheme_default(self):
        zh = read("README.md")
        en = read("README.en.md")
        self.assertNotIn("收到任何会产出新视觉设计的任务", zh)
        self.assertNotIn("任何新视觉设计", zh)
        self.assertNotIn("Any task that produces new visual design starts", en)
        self.assertIn("**L2（新视觉语言或重大结构变化）**", zh)
        self.assertIn("Any **L2** task", en)

        self.assertIn("默认只出 1 个最佳方案", zh)
        self.assertIn("single best scheme", en)

        weak_zh = next(line for line in zh.splitlines()
                       if "仍然要有真实候选图" in line)
        self.assertIn("L2", weak_zh)
        self.assertIn("L1", weak_zh)
        weak_en = next(line for line in en.splitlines()
                       if "still requires real candidate visual evidence" in line)
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

        l3_note = next(line for line in self.skill.splitlines()
                       if "L3 载体的方向探索" in line)
        self.assertIn("默认 1 版", l3_note)

    def test_brand_asset_l1_exemption(self):
        asset = read("references/brand-asset-protocol.md")
        row = next(line for line in asset.splitlines()
                   if "色值完全找不到" in line)
        self.assertIn("L2", row)
        self.assertIn("L1 局部优化", row)
        self.assertIn("不铺方向门", row)

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

    def test_l2_single_scheme_does_not_weaken_gate(self):
        """单方案默认不得稀释 Gate 1 的真实视觉证据与多分支停轮。"""
        for needle in ("停轮等用户选定", "默认交付单一最佳方案",
                       "不得用文字描述替代真实视觉"):
            self.assertIn(needle, self.skill)
        self.assertNotIn("不得只做 1 个", self.skill)

        gpt = read("references/gpt-visual-workflow.md")
        self.assertIn("不得把单方向包装成多方向比较", gpt)
        self.assertIn("不得静默改用 HTML/SVG 冒充概念图", gpt)
        self.assertIn("不得把它包装成「用户选择」", gpt)

        l3 = next(line for line in self.skill.splitlines()
                  if "**L3 · 非 UI 载体**" in line)
        self.assertIn("不套 UI 多方向门", l3)


class DefaultDesignStrategyContractTests(unittest.TestCase):
    """「项目规则优先」归并后的 9 项契约（2026-10-30）。

    这些断言检查真实规则内容与跨文档一致性，不是孤立关键词：
    每个 bullet 按自己的语义被单独取出校验，跨文档则检查同一条口径。
    """

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.agents = read("AGENTS.md")
        cls.product_value = read("references/product-value.md")
        cls.routing = read("references/routing-table.md")
        cls.workflow = read("references/workflow.md")
        cls.gpt = read("references/gpt-visual-workflow.md")
        cls.direction_path = read("references/direction-gpt-path.md")
        cls.readme_zh = read("README.md")
        cls.readme_en = read("README.en.md")
        cls.refs = reference_docs()

    # ── helpers ────────────────────────────────────────────────
    @classmethod
    def rule_block(cls):
        return section(cls.skill, RULE_HEADING)

    @classmethod
    def rule_bullets(cls):
        bullets = {}
        for line in cls.rule_block().splitlines():
            match = re.match(r"- \*\*(.+?)\*\*", line)
            if match:
                bullets[match.group(1)] = line
        return bullets

    def bullet(self, label):
        bullets = self.rule_bullets()
        self.assertIn(label, bullets, "「项目规则优先」缺少条目：%s" % label)
        return bullets[label]

    # ── 1. 唯一口径节存在，且名称保留 ─────────────────────────
    def test_01_rule_section_is_single_authority(self):
        self.assertEqual(self.skill.count("### " + RULE_HEADING), 1,
                         "「项目规则优先」必须恰好一个三级小节（引用兼容）")
        block = self.rule_block()
        self.assertIn("权威口径", block)
        self.assertIn("不得给出不同数值", block)
        self.assertIn("不放宽", block)

        # 方案数量口径只有 SKILL.md 这一处给出数字；references 只能指针引用。
        for rel, text in self.refs.items():
            if "单一最佳方案" in text:
                self.assertIn("项目规则优先", text,
                              "%s 提到方案数量却没有指向唯一口径" % rel)

    # ── 2. 默认单一最佳方案是本 skill 自身默认，不是项目 opt-in ──
    def test_02_default_is_single_best_scheme(self):
        bullet = self.bullet("默认交付单一最佳方案")
        for needle in ("1 个", "不需要使用方项目另行声明",
                       "实质性设计分歧", "2–3 个", "只换配色"):
            self.assertIn(needle, bullet)

        for rel in ("references/gpt-visual-workflow.md",
                    "references/routing-table.md",
                    "references/workflow.md",
                    "references/direction-gpt-path.md",
                    "README.md"):
            self.assertIn("单一最佳方案", read(rel), "%s 未声明单一最佳方案默认" % rel)

        # 单一最佳方案不需要在每个使用方项目重复声明
        self.assertIn("不需要使用方项目另行声明", bullet)

    # ── 3. 全仓不再有强制多方向 / 三方向硬门 ───────────────────
    def test_03_no_forced_multi_direction_leftover(self):
        docs = dict(self.refs)
        docs["SKILL.md"] = self.skill
        docs["README.md"] = self.readme_zh
        docs["README.en.md"] = self.readme_en
        for rel, text in docs.items():
            for pattern in BANNED_RULE_PATTERNS:
                self.assertNotIn(pattern, text,
                                 "%s 仍保留已废止的强制多方向口径：%r" % (rel, pattern))

        # 量化口径只能指向 1 个默认
        self.assertIn("方向数量**：默认 **1 个**", self.skill)
        self.assertIn("默认 1 套", self.skill)          # Phase 4 套数
        self.assertIn("默认 1 版", self.skill)          # L3 载体版本数

    # ── 4. 替代方向只在实质分歧或用户明确要求时出现 ─────────────
    def test_04_alternatives_only_on_divergence_or_request(self):
        gate = next(line for line in self.skill.splitlines()
                    if "默认单一最佳方案不走方向门" in line)
        for needle in ("默认单一最佳方案不走方向门",
                       "实质性设计分歧", "用户明确要求", "先出自己的最佳方案"):
            self.assertIn(needle, gate)
        self.assertIn("先出自己的最佳方案", gate)
        self.assertNotIn("默认出 3", gate)

        quantity = next(line for line in self.skill.splitlines()
                        if line.startswith("**方向数量**"))
        self.assertIn("默认 **1 个**", quantity)
        self.assertIn("2–3 个", quantity)
        self.assertIn("结构性不同", quantity)

        philosophy = section(
            self.skill, "3. 给variations（实质分歧 / 用户明确要求），不给「最终答案」")
        self.assertIn("只有存在实质性设计分歧、或用户明确要求多版本对比时", philosophy)

        self.assertIn("存在实质分歧或用户要求对比时 2–3 版",
                      self.skill)  # L3 deck 例

    # ── 5. 常规设计自由度不被旧 IA / 旧设计稿锁死 ───────────────
    def test_05_design_freedom_not_bound_to_existing_design(self):
        bullet = self.bullet("「从 existing context 出发」≠ 必须继承上一版设计")
        for needle in ("信息架构", "页面数量", "导航", "交互", "视觉语言",
                       "设计基线", "组件形态", "常规设计自由度",
                       "不需要为此逐步申请批准"):
            self.assertIn(needle, bullet)
        self.assertIn("真实资产", bullet)

    # ── 6. 业务 / 商业化 / 隐私 / 安全 / 合规边界不因自由度放宽 ──
    def test_06_business_and_compliance_boundaries_hold(self):
        bullet = self.bullet("设计自由度不改变业务与合规边界")
        for needle in ("业务规则", "商业化", "广告", "隐私", "安全", "合规",
                       "不因设计自由度放宽", "见上级 `AGENTS.md` 与项目规则",
                       "设计自主不构成实施、发布或推送授权"):
            self.assertIn(needle, bullet)

        # 停轮与授权语义仍在：单一方案不停轮 ≠ 不用给用户看
        stop = self.bullet("停轮语义")
        for needle in ("单一方案默认路径**不设「方向选择」停轮**",
                       "真实视觉证据", "多个真实候选", "不得用文字描述替代真实视觉"):
            self.assertIn(needle, stop)

    # ── 7. 质量门槛不放宽（真实证据 / 不伪造 / dp）──────────────
    def test_07_quality_gates_remain(self):
        bullet = self.bullet("质量要求不放宽")
        for needle in ("真实像素", "dp", "业务不变量", "不伪造 PASS",
                       "历史结论不等于现状", "项目要求更严时取更严值"):
            self.assertIn(needle, bullet)

        for needle in ("Gate 1", "Gate 2", "--confirm-gpt-review",
                       "SKIP_DESIGN_GATE", "48dp"):
            self.assertIn(needle, self.skill)

        gate_js = read("scripts/design-gate-check.js")
        self.assertIn("MIN_LONG", gate_js)
        self.assertIn("direction-approved.md", gate_js)

    # ── 8. 项目规则权威在项目；SKILL.md 不再硬编码他项目的 §1.4 ──
    def test_08_project_rule_authority_without_hardcoded_ref(self):
        self.assertNotIn("§1.4", self.skill)
        self.assertNotIn("AGENTS.md §1.4", self.readme_zh)
        self.assertNotIn("AGENTS.md §1.4", self.readme_en)

        bullet = self.bullet("产品原则的权威在项目")
        for needle in ("唯一权威", "product-value.md", "默认方法",
                       "章节位置由项目自定",
                       "不把两套原则同时复述"):
            self.assertIn(needle, bullet)
        self.assertIn("本 skill 自身不定义产品设计原则", bullet)

        trust = self.bullet("项目规则可以更严")
        for needle in ("多方向探索", "标注 `agent 决策`",
                       "可回退版本", "不把它们升级为全局硬门"):
            self.assertIn(needle, trust)

        # AGENTS.md 只声明职责分工，不搬其他项目规则、不新增 §1.4
        self.assertIn("产品原则的权威在使用方项目", self.agents)
        self.assertIn("不把其他项目的产品规则搬进本仓库", self.agents)
        self.assertNotIn("## 1.4", self.agents)

    # ── 9. product-value.md 只留指针，不复述长规则 ──────────────
    def test_09_product_value_only_keeps_pointer(self):
        note = next(line for line in self.product_value.splitlines()
                    if line.startswith("> **效力顺序**"))
        for needle in ("唯一权威", "默认方法", "`SKILL.md`「项目规则优先」",
                       "不得给出不同数值"):
            self.assertIn(needle, note)

        # 不复述规则正文
        for duplicated in ("不需要使用方项目另行声明",
                           "项目规则可以更严",
                           "不把它们升级为全局硬门"):
            self.assertNotIn(duplicated, self.product_value)

        # 不保留日期戳式的「效力顺序」快照
        self.assertIsNone(
            re.search(r"效力顺序[（(]\s*\d{4}-\d{2}-\d{2}", self.product_value),
            "product-value.md 不应带日期的效力顺序快照")
        self.assertNotIn("2026-10-30", self.product_value)

        # 方向门数字口径只在 SKILL.md 给出
        self.assertIn("数量口径见 `SKILL.md`「项目规则优先」", self.product_value)


class RulePrecedenceAndDeliverableContractTests(unittest.TestCase):
    """第 6 轮精修的 13 项契约（2026-10-30）。

    检查**规则之间的关系**而不只是关键词：5 层的层间约束、单一维护处的结构事实、
    方向数量与交付物数量的独立性、L3 的完整交付、以及外置内容入口能否解析。
    """

    PRECEDENCE_MARKERS = "①②③④⑤"

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.agents = read("AGENTS.md")
        cls.product_value = read("references/product-value.md")
        cls.routing = read("references/routing-table.md")
        cls.workflow = read("references/workflow.md")
        cls.gpt = read("references/gpt-visual-workflow.md")
        cls.components = read("references/components-and-output.md")
        cls.ui_demo = read("references/ui-demo-animation.md")
        cls.storyboard = read("references/storyboard-basics.md")
        cls.launch_film = read("references/launch-film-director-notes.md")
        cls.design_styles = read("references/design-styles.md")
        cls.readme_zh = read("README.md")
        cls.readme_en = read("README.en.md")
        cls.refs = reference_docs()

    # ── helpers ────────────────────────────────────────────────
    @classmethod
    def rule_block(cls):
        return section(cls.skill, RULE_HEADING)

    def bullet(self, label):
        for line in self.rule_block().splitlines():
            if line.startswith("- **" + label + "**"):
                return line
        raise AssertionError("「项目规则优先」缺少条目：%s" % label)

    @classmethod
    def precedence_line(cls):
        return next(line for line in cls.skill.splitlines()
                    if "效力关系按职责分层判断" in line)

    @classmethod
    def layers(cls):
        """Split the single precedence sentence into its 5 responsibility layers."""
        line = cls.precedence_line()
        positions = [line.index(m) for m in cls.PRECEDENCE_MARKERS]
        positions.append(len(line))
        return {mark: line[positions[i]:positions[i + 1]]
                for i, mark in enumerate(cls.PRECEDENCE_MARKERS)}

    # ── 1. 5 层效力关系存在、排序正确，且只在 SKILL.md 维护完整排序 ──
    def test_01_precedence_is_single_sourced(self):
        layers = self.layers()
        # 层序：全局安全 → 用户决策 → 项目规则 → SKILL.md → references
        self.assertIn("全局安全与授权约束", layers["①"])
        self.assertIn("用户明确的业务目标与关键决策", layers["②"])
        self.assertIn("使用方项目规则", layers["③"])
        self.assertIn("本 skill `SKILL.md`", layers["④"])
        self.assertIn("`references/`", layers["⑤"])
        self.assertIn("按规则所属职责判断", self.precedence_line())

        # 单一维护处：完整 5 层只在 SKILL.md 出现；AGENTS.md 只记结论、不复制分层
        self.assertEqual(self.skill.count("效力关系按职责分层判断"), 1)
        self.assertIn("本文件不复述完整分层", self.agents)
        self.assertNotIn("⑤", self.agents)
        self.assertNotIn("⑤", self.product_value)
        self.assertIn("完整 5 层效力关系", self.product_value)
        self.assertIn("`SKILL.md`「项目规则优先」", self.product_value)
        self.assertIn("`SKILL.md`「项目规则优先」", self.routing)

    # ── 2. 全局安全与授权约束不得被项目规则或 skill 放宽 ──────────
    def test_02_global_safety_not_relaxed(self):
        top = self.layers()["①"]
        self.assertIn("上级 `AGENTS.md`", top)
        self.assertIn("不得被项目规则或本 skill 放宽", top)

        # 三处文档口径一致，且都指向同一层
        self.assertIn("全局安全与授权硬约束", self.skill)              # ZCode 适配
        self.assertIn("不得被项目规则或本 skill 放宽", self.skill)
        self.assertIn("不被本文件或项目规则放宽", self.product_value)
        self.assertIn("全局安全与授权硬约束", self.agents)
        self.assertIn("被本项目规则或 DesignWise 放宽", self.agents)

    # ── 3. 用户业务决策定方向，但不扩大授权范围 ─────────────────
    def test_03_user_decisions_set_direction_not_authorization(self):
        layer = self.layers()["②"]
        self.assertIn("决定本次任务的产品方向、优先级与取舍", layer)
        self.assertIn("受 ① 约束", layer)
        self.assertIn("不自动获得任务范围外的操作授权", layer)

        # 同一条授权语义在边界条与 AGENTS.md 维护结论里成立
        self.assertIn("设计自主不构成实施、发布或推送授权",
                      self.bullet("设计自由度不改变业务与合规边界"))
        self.assertIn("使用方项目的产品原则与用户关键决策", self.agents)

    # ── 4. 项目产品原则 > skill 通用设计偏好；项目规则覆盖不了全局安全 ──
    def test_04_project_principles_outrank_skill_preferences(self):
        layers = self.layers()
        self.assertIn("覆盖本 skill 的通用设计偏好", layers["③"])
        self.assertIn("却覆盖不了 ①", layers["③"])
        self.assertIn("不把自身设计偏好强加给项目", layers["④"])
        self.assertIn("不形成独立于 `SKILL.md` 的冲突规则", layers["⑤"])

        # 层次关系是「按职责」的：③ 高于 ④，但 ① 高于 ③
        self.assertIn("DesignWise 的一般设计偏好", self.agents)
        self.assertIn("唯一权威", self.bullet("产品原则的权威在项目"))

    # ── 5. 默认设计方向数 = 1（跨文档同一口径）────────────────
    def test_05_default_direction_count_is_one(self):
        self.assertIn("默认产出 **1 个**",
                      self.bullet("默认交付单一最佳方案"))
        self.assertIn("**方向数量**：默认 **1 个**", self.skill)
        self.assertIn("默认 1 套", self.skill)          # HTML fallback 套数
        self.assertIn("设计方向**版本数同样按「方案数量」默认 1 版", self.skill)

        for rel, needle in (
                ("references/routing-table.md", "默认单一最佳方案"),
                ("references/design-styles.md", "默认只出 1 个方向"),
                ("references/gpt-visual-workflow.md", "默认 1 个＝单一最佳方案"),
                ("references/ui-demo-animation.md", "默认 1 版方向板"),
                ("references/storyboard-basics.md", "默认 1 张"),
                ("references/launch-film-director-notes.md", "默认 1 版"),
        ):
            self.assertIn(needle, read(rel), "%s 的方向默认数口径不一致" % rel)

    # ── 6. 全仓不得再有强制三方向 ───────────────────────────────
    def test_06_no_forced_three_directions(self):
        docs = dict(self.refs)
        docs["SKILL.md"] = self.skill
        docs["AGENTS.md"] = self.agents
        docs["README.md"] = self.readme_zh
        docs["README.en.md"] = self.readme_en
        forced = re.compile(r"(必须|强制|默认)[^。\n]{0,12}(3|三)\s*(个|版)\s*(方向|方案)")
        for rel, text in docs.items():
            for pattern in BANNED_RULE_PATTERNS:
                self.assertNotIn(pattern, text,
                                 "%s 仍保留强制多方向口径：%r" % (rel, pattern))
            self.assertIsNone(forced.search(text),
                              "%s 仍把三个方向写成必须/默认" % rel)

    # ── 7. 替代方向只在实质分歧或用户明确要求时出现 ─────────────
    def test_07_alternatives_only_on_substantive_divergence(self):
        gate = next(line for line in self.skill.splitlines()
                    if "默认单一最佳方案不走方向门" in line)
        self.assertIn("存在实质性设计分歧", gate)
        self.assertIn("用户明确要求", gate)
        self.assertNotIn("默认出 3", gate)

        self.assertIn("存在实质分歧或用户明确要求时才 2–3 个", self.gpt)
        self.assertIn("只有当确实存在实质性设计分歧、或用户明确要求多方向时",
                      self.workflow)

    # ── 8. 方向数量与交付物数量相互独立 ─────────────────────────
    def test_08_direction_and_deliverable_counts_are_independent(self):
        bullet = self.bullet("设计方向数量 ≠ 交付物数量")
        for needle in ("只约束**设计方向**", "**不限制实际交付物**",
                       "交付物由任务范围、载体、平台与验收要求决定",
                       "不因方向数为 1 就只交一页、一个文件、一个尺寸或一个状态"):
            self.assertIn(needle, bullet)

        self.assertIn("设计方向数量与交付物数量相互独立", self.routing)
        self.assertIn("variations 数量只约束「设计方向」，不约束交付物", self.workflow)
        self.assertIn("方案数量只约束「设计方向」", self.components)

    # ── 9. 一个方向可含多页面/多尺寸/多状态/组件变体 ─────────────
    def test_09_one_direction_covers_full_delivery(self):
        block = section(self.components, "交付物数量（与设计方向数量无关）")
        for needle in ("多个页面与完整页面流程",
                       "多尺寸与多设备适配稿",
                       "多个页面状态与交互状态",
                       "必要组件及组件变体",
                       "各平台所需素材尺寸与导出文件",
                       "同一方向的多种交付格式"):
            self.assertIn(needle, block)

        # 同一口径回写 SKILL.md 与 GPT 通路「一套」的定义
        self.assertIn("多页面与完整页面流程", self.bullet(
            "设计方向数量 ≠ 交付物数量"))
        self.assertIn("「一套」指同一设计方向下的完整交付，不是只交一屏", self.gpt)
        self.assertIn("「一套」指同一设计方向下的完整交付", self.skill)

    # ── 10. L3 无机械「单文件 / 单载体版本」限制 ────────────────
    def test_10_l3_has_no_single_file_limit(self):
        l3_row = next(line for line in self.skill.splitlines()
                      if "**L3 · 非 UI 载体**" in line)
        self.assertIn("交付物按任务范围完整交付", l3_row)
        self.assertIn("不因方向数为 1 而受限", l3_row)

        self.assertIn("交付物数量不受此限", self.skill)      # Phase 4 L3 说明
        self.assertIn("不因方向数为 1 就只交一屏", self.skill)  # Phase 5.5

        for text, needle in (
                (self.ui_demo, "方向板 1 版 ≠ 只交 1 支成片 / 1 个尺寸"),
                (self.storyboard, "方向板 1 张 ≠ 成片只 1 个镜头或只 1 个交付版本"),
                (self.launch_film, "方向板 1 版 ≠ 交付物只有 1 个版本"),
        ):
            self.assertIn(needle, text)

        # 没有任何文档把「单交付物」写成规则（只允许否定式表述）
        positive_only = re.compile(r"只能交付一个(文件|版本|尺寸)|只允许一个版本")
        for rel, text in dict(self.refs, **{"SKILL.md": self.skill}).items():
            self.assertIsNone(positive_only.search(text),
                              "%s 仍把交付物数量限制为一个" % rel)

    # ── 11. references 与 SKILL.md 的数量口径不冲突 ─────────────
    def test_11_no_conflicting_count_rules_across_docs(self):
        # 声明方向默认数的文档必须指向唯一口径，避免各自维护一套数字
        for rel in ("references/routing-table.md",
                    "references/design-styles.md",
                    "references/gpt-visual-workflow.md",
                    "references/ui-demo-animation.md",
                    "references/storyboard-basics.md",
                    "references/launch-film-director-notes.md",
                    "references/workflow.md",
                    "references/product-value.md"):
            self.assertIn("项目规则优先", read(rel),
                          "%s 给出方向/交付物数量口径却没有入口指针" % rel)

        # 除 SKILL.md 外，任何文档不得另立「默认 3 个方向」式默认值
        default_three = re.compile(r"默认\s*(3|三)\s*(个|版)\s*(方向|方案)")
        for rel, text in self.refs.items():
            self.assertIsNone(default_three.search(text),
                              "%s 私自改了方向默认数" % rel)

    # ── 12. 业务 / 隐私 / 安全 / 商业化 / 合规边界仍在 ──────────
    def test_12_core_boundaries_survive(self):
        header = self.rule_block().splitlines()[2]
        for needle in ("不放宽**授权与隐私/合规边界", "真实视觉证据", "不伪造结论"):
            self.assertIn(needle, header)

        boundary = self.bullet("设计自由度不改变业务与合规边界")
        for needle in ("业务规则", "商业化", "广告", "隐私", "安全", "合规"):
            self.assertIn(needle, boundary)

        # 硬门与授权语义未因压缩而消失
        for needle in ("48dp", "Gate 1", "Gate 2", "不伪造 PASS",
                       "SKIP_DESIGN_GATE", "--confirm-gpt-review"):
            self.assertIn(needle, self.skill)

    # ── 13. 外置内容仍有可解析的入口 ────────────────────────────
    def test_13_externalized_content_is_resolvable(self):
        # SKILL.md 里提到的每个 references/*.md 都真实存在
        for rel in set(re.findall(r"`(references/[^`]+?\.md)`", self.skill)):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)),
                            "SKILL.md 指向不存在的文件：%s" % rel)

        # 方向/交付物口径的入口指向真实小节，不是悬空标题
        self.assertIn("清单见 `references/components-and-output.md`「交付物数量」",
                      self.skill)
        section(self.components, "交付物数量（与设计方向数量无关）")

        # GPT 通路「一套」的定义与「按需 HTML」入口对得上
        self.assertIn("按需做一套 HTML", self.skill)
        self.assertIn("## 3.6 按需制作一套可交互 HTML 原型", self.gpt)


class DocConsistencyRepairTests(unittest.TestCase):
    """第 8 轮独立验收发现的文档一致性缺陷的回归测试（2026-10-30）。

    这些缺陷此前被测试漏掉：悬空的「SKILL.md §某节」引用、被压缩掉的落档义务、
    被简化的评审维度锚点，以及「唯一口径/不复述数字」与实际文本自相矛盾。
    """

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.routing = read("references/routing-table.md")
        cls.components = read("references/components-and-output.md")
        cls.video = read("references/video-export.md")
        cls.philosophy = read("references/design-philosophy.md")
        cls.direction_path = read("references/direction-gpt-path.md")
        cls.product_value = read("references/product-value.md")

    # ── 1. 方向门豁免的落档义务仍在 ────────────────────────────
    def test_01_exemption_trail_is_still_required(self):
        self.assertIn("多方案分支下三种都要把原话/理由落档到 `direction-approved.md`",
                      self.skill)
        # 三条豁免一条都不能少
        for needle in ("本次会话明说", "已选定方向后的迭代", "非设计的机械操作"):
            self.assertIn(needle, self.skill)
        self.assertIn("设计方向数量 ≠ 交付物数量", section(self.skill, RULE_HEADING))

    # ── 2. design-philosophy 的入口指向真实小节 ────────────────
    def test_02_design_philosophy_entry_resolves(self):
        head = self.philosophy.splitlines()[2]
        self.assertIn("入口见 SKILL.md", head)
        self.assertNotIn("你不是一个人，是一个工作室", head)
        # 入口指向的落点在 SKILL.md 里真实存在
        self.assertIn("你是设计师，不是写 HTML 的程序员", self.skill)
        self.assertIn("`references/design-philosophy.md`", self.skill)

    # ── 3. video-export 的水印指针指向真实小节 ─────────────────
    def test_03_watermark_pointer_resolves(self):
        self.assertNotIn("SKILL.md §「水印」", self.skill + self.video)
        self.assertIn("`references/components-and-output.md`「水印（动画产出）」",
                      self.video)
        section(self.components, "水印（动画产出）", level=2)

    # ── 4. 方案数量的口径声明与实际复述不矛盾 ──────────────────
    def test_04_scheme_count_authority_wording_is_consistent(self):
        header = section(self.skill, RULE_HEADING).splitlines()[2]
        self.assertIn("权威口径", header)
        self.assertIn("不得给出不同数值", header)
        # 旧措辞会让「多处带数字复述」变成违规（文件自称不复述、正文却复述），已废止。
        # 注意断言对象是真正会复述数字的那两份文件，不是 SKILL.md。
        for rel, text in (("references/direction-gpt-path.md", self.direction_path),
                          ("references/product-value.md", self.product_value)):
            self.assertNotIn("不复述数字", text, "%s 仍自称不复述数字" % rel)
            self.assertNotIn("只引用不复述", text, "%s 仍自称只引用不复述" % rel)
            self.assertIn("不得给出不同数值", text, "%s 缺统一口径声明" % rel)

    # ── 5. 专家评审的「功能性」维度锚点没被精简掉 ─────────────
    def test_05_review_dimension_anchor_survives(self):
        self.assertIn("产品界面类在「功能性」维度加查用户价值与易用性", self.skill)

    # ── 6. routing-table 不再自称逐字副本，且承认 SKILL.md 权威 ─
    def test_06_routing_table_points_to_authority(self):
        head = "\n".join(self.routing.splitlines()[:6])
        self.assertNotIn("逐字完整版", head)
        self.assertIn("参考入口（速查）", head)
        self.assertIn("冲突时以 `SKILL.md` 为准", head)
        self.assertIn("## 参考入口（速查）", self.skill)


class ProductPrincipleIntegrationContractTests(unittest.TestCase):
    """产品价值四层与上游能力整合的文档契约（2026-10-31）。

    守的是「整合」而不是「加段落」：四层必须落到 Brief / prompt / Gate 1 / 验收，
    参考板与外观账本必须不强制、不阻断，素材与体检必须复用既有通路，计数口径必须一致。
    """

    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.workflow = read("references/gpt-visual-workflow.md")
        cls.product_value = read("references/product-value.md")
        cls.critique = read("references/critique-guide.md")
        cls.research = read("references/design-research.md")
        cls.materials = read("references/materials.md")
        cls.verification = read("references/verification.md")
        cls.handoff = read("references/design-handoff.md")
        cls.routing = read("references/routing-table.md")

    # ── 1. 四层在各环节都有落点，且不是形容词 ─────────────────
    def test_01_four_layers_land_in_each_stage(self):
        self.assertIn("四层在各环节的落点", self.product_value)
        for stage in ("Visual Brief 第 3 段", "生图 prompt 正文", "Gate 1（仅产品界面/交互）",
                      "真实体验验收", "设计评审"):
            self.assertIn(stage, self.product_value, "四层落点缺环节：%s" % stage)
        # Brief 要求可检验约束，不是四句好话
        self.assertIn("每层一条可检验约束", self.workflow)
        self.assertIn("不写四句好话", self.workflow)
        # prompt 正文必须带两句可被画面验证的话
        self.assertIn("价值四层要进 prompt 正文", self.workflow)
        for needle in ("第一眼聚焦", "系统承担的复杂度", "no shortcut is claimed"):
            self.assertIn(needle, self.workflow)
        # Gate 1 四问限定在产品界面类，且明确不新增门槛
        self.assertIn("产品界面 / 交互类追加四问", self.workflow)
        self.assertIn("不评分、不新增门槛", self.workflow)
        # 评审侧补「舒服」层检查点，且不新增维度
        self.assertIn("视觉噪音与干扰", self.critique)
        self.assertIn("不新增评分维度", self.critique)

    # ── 2. 四层不越界：不新增评分体系，不强迫加情绪 ───────────
    def test_02_four_layers_stay_advisory(self):
        self.assertIn("不新增评分体系", self.workflow)
        self.assertIn("不新增检查点", self.product_value)
        self.assertIn("情绪机会只写一处", self.workflow)
        # 情绪价值不成立时必须允许「本版不加」
        self.assertIn("本版不加情绪价值", self.workflow)

    # ── 3. 参考板：真实像素、按需、借方法不抄标识 ─────────────
    def test_03_reference_board_is_optional_and_honest(self):
        self.assertIn("不强制", self.research)
        self.assertIn("借方法，不抄标识", self.research)
        self.assertIn("scripts/ref_board.py", self.research)
        h1 = self.research.splitlines()[0]
        self.assertIn("参考板", h1)
        # 不能把参考截图当产出
        self.assertIn("参考截图**永远不是**本项目的产出", self.research)
        # 脚本入口真实存在且在路由表里可发现
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "scripts", "ref_board.py")))
        self.assertIn("scripts/ref_board.py", self.routing)

    # ── 4. 外观账本：只提示、不阻断、不是记忆系统 ─────────────
    def test_04_ledger_warns_never_blocks(self):
        self.assertIn("--ledger-check", self.research)
        self.assertIn("只提示，从不改退出码", self.research)
        self.assertIn("不为差异化而差异化", self.research)
        self.assertIn("它不是记忆系统", self.research)
        self.assertIn("本机私有", self.research)
        # 账本不得被描述成第二个记忆/知识系统
        self.assertNotIn("长期记忆", self.research)
        # 体检文档同步说明黄灯不改退出码
        self.assertIn("审美提示不得变成阻断条件", self.verification)
        self.assertIn("--ledger-check", self.verification)

    # ── 5. Design Lint 复用既有通路，不新建 playwright 链路 ────
    def test_05_design_lint_reuses_existing_scripts(self):
        self.assertIn("设计体检", self.verification)
        self.assertIn("contrast.unknown", self.verification)
        self.assertIn("images.broken", self.verification)
        self.assertIn("--shot", self.verification)
        self.assertIn("脚本只出事实", self.verification)
        # 不引入新的采集依赖
        self.assertNotIn("design_lint.py", self.verification)

    # ── 6. 素材先行：主角素材 + 能力分档，探测不到不阻断 ──────
    def test_06_materials_tiers_do_not_block(self):
        for needle in ("主角素材", "真图诚实性测试", "探测不到不阻断", "--health"):
            self.assertIn(needle, self.materials)
        self.assertIn("## §4 素材三态：参考 / 概念 / 正式", self.materials)
        # 三态权威仍在 gpt-visual-workflow，素材文档只给指针
        self.assertIn("§3.6.4", self.materials)
        self.assertIn("references/materials.md", self.skill)
        self.assertIn("references/materials.md", self.routing)

    # ── 7. 经验回流：四类证据去向不同，不新建系统 ─────────────
    def test_07_experience_loop_has_four_states(self):
        for needle in ("preference", "observed", "verified", "superseded"):
            self.assertIn(needle, self.handoff)
        self.assertIn("不为回流新建第三个记录系统", self.handoff)
        self.assertIn("经验不扩大授权", self.handoff)

    # ── 8. 参考入口与计数口径 ─────────────────────────────────
    def test_08_reference_entries_and_counts(self):
        entry = section(self.skill, "参考入口（速查）", level=2)
        self.assertIn("references/design-research.md", entry)
        self.assertIn("references/materials.md", entry)
        # 风格库计数统一为 84，SKILL.md 里不得残留 60
        self.assertNotIn("60 种", self.skill)
        self.assertIn("84 种", self.skill)
        self.assertIn("84 种", self.routing)
        # 新文档必须在 check-skill 的引用扫描下可解析（路径形如 references/xxx.md 且文件存在）
        for rel in ("references/design-research.md", "references/materials.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), rel)

    # ── 9. 不因整合而放宽既有硬规则 ───────────────────────────
    def test_09_existing_hard_rules_untouched(self):
        self.assertIn("默认产出 **1 个**", self.skill)
        self.assertIn("效力关系按职责分层判断", self.skill)
        self.assertIn("Copilot 正式 REVIEW 仅用户点名", self.skill)
        # L1 仍是四步，不因新增参考板/账本变成五步
        self.assertIn("理解现状", self.skill)
        self.assertIn("针对性验证", self.skill)


if __name__ == "__main__":
    unittest.main()
