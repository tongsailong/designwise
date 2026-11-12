# Huashu 上游能力调查与吸收决策

> 上游 = `alchaincyf/huashu-design`，本次现场核实 `upstream/master` = `e8d1148`（tag v3.3.0）。
> 只做选择性与改写，不恢复上游运行时依赖。所有判断带 `file:line` 或提交证据。

## 0. 数量与归属纠偏

| 历史说法 | 现场 |
|---|---|
| 37 个 references | 上游 `references/` = **45 个**（40 顶层 + 5 `modules/*.md`） |
| 11 个 GPT-image 相关 references | **没有专门的 GPT-image reference**；提到 `huashu-gpt-image` / nano-banana 的是 **5 个文件**（`materials.md`、`brand-asset-protocol.md`、`cinematic-patterns.md`、`design-styles.md`、`about-author.md`）。两者不是同一批文件，也不是 11 个 |
| `design-handoff.md` 是上游能力 | **不是**。上游 `upstream/master:references/design-handoff.md` 不存在；`git log --all -- '*design-handoff*'` 只命中本分支提交（`f05bc89`、`92272e8`、`7fbca50`、`163fe33`、`6efd10f`、`ce7bccf`）。这是 DesignWise 自建产物 |
| 上游有 DISCOVER→SPEC→DESIGN→PLAN→IMPLEMENT→VERIFY | **不存在**。全仓 grep 零命中。上游真实机制是「模块路由 + 产物存在性门 + 任务类型/用户明示跳过表」 |
| 上游「五维评审」 | 写入版是 **六维**：概念/立意（一票否决）+ 哲学一致性/视觉层级/细节执行/功能性/创新性（`references/critique-guide.md:9-107`）。「五维」只出现在 `demos/c6-expert-review.html:638-643` 的雷达图（漏掉概念轴）与两处过期文案 |

## 1. 六项重点能力的真实内容

### 1.1 设计执行引擎
上游没有计算型引擎。它的「引擎」是**工作室角色模型**（`SKILL.md:28-40`）：艺术总监 / 品牌研究员 / 视觉设计师 / 动效设计师 / 前端工程师 / 文案；媒介变了主导角色要换（`:39-40`）。判断方法外置为「摆出来和参考并排让用户看」（`:194`），不是内部打分器。

另有一条真实的「引擎分层」表述只在 motion 模块（`modules/motion.md:71-73`）：方法层与执行后端分层，换后端不改方法。这条对 App UI 的意义：**设计方法与宿主/工具链解耦**，DesignWise 已有同类结构（`runtime-adapters.md`），不需要再引入。

### 1.2 六维评审（见 §0 纠偏）
- 判据是 0–10 五档 + 每维 3–4 条可证伪检查（换客户名测试、眯眼测试、删除测试、2.5 倍字号比、色数/字数计数）。
- 场景加权（`critique-guide.md:110-122`）：App UI 主看「功能性、细节执行」，次看「视觉层级」，哲学一致性按**可用性优先**放宽；概念轴不参与取舍。
- 输出模板（`:184-216`）：总分四档 + 六项分+一句理由 + Keep + Fix（当前/问题/修复，带数值）+ 三级严重度 + Quick Wins。
- **不验证改善**：没有复评分数或缺陷趋势，只有打磨环的首末并排截图（`polish-loop.md:56`）。
- `scripts/design_lint.py` **不是评审实现**：它是事实体检器（红灯：破图/字号/对比度/控制台；黄灯：模板装饰；提示：外观家族；指纹：compare/ledger），`design_lint.py:3-19`，无任何评分/维度 token。

### 1.3 Prompt 方法论
- 公式在 `scene-templates.md:3-4`：`[风格 DNA] + [场景模板] + [具体内容]`；场景模板 8 类，每类 4–6 条英文要点（主体/比例/视觉行为/背景/一条约束）。
- 心法（`design-styles.md:899-905`）：短 > 长，描述情绪与内容，不堆布局坐标；「Mood, Not Layout」。
- 产品理解不是靠 prompt，而是靠**产物链**：`product-facts.md`（事实验证）→ `design-context.md` 上下文阶梯（设计系统 > 代码 > 已发布产品 > 品牌 > 无上下文）→ spec 只写「说什么」不写「长什么样」（`directions.md:33`）→ 方向卡 6 栏 → `form 五问`（`workflow.md:11-18`）。
- **失败后没有 prompt 修正机制**（缺口），只有产物级纠错。

### 1.4 方向图与视觉决策
这是上游最有价值的一块（`references/directions.md`，140 行）：
- **6 候选 → 6 缩略图 → 3 完整版**（`:15`），三种来源各 2 张：最佳设计师 ×2、同媒介真实参照 ×2、秒数轮盘 ×2（`:51-63`）。
- 方向卡 6 栏（`:67-74`）：逻辑与来源 / 借的是什么 / 主角素材 / 骨架 / 胆量花在哪 / **form 来自内容的哪里**。
- 缩略图是廉价门（`:76`）：480×300、真字体真骨架、`data-thumb` 标记；「只有一个标题加一块纯色 = 占位不是候选」。
- 选择标准有序（`:86-93`）：单看够好 → 三张彼此不一样（不同骨架）→ 不撞最近项目 → 最多一张用力过头。
- 防换皮是**实测**（`design_lint.py:214-232, 392-403`）：32×20 灰度边缘版式向量相关性 >0.55 判「骨架相似」；OKLab 色板距离 <0.06 判「色板几乎相同」。
- 拒绝与重出（`:76, 124`）：换来源/换骨架，**不是换颜色**；不合格缩略图从样张 HTML 重建。
- 无自动融合，只有用户混合选择（`:139`）。

### 1.5 design-handoff.md
上游不存在（§0）。DesignWise 自建版 `references/design-handoff.md` 已覆盖：7 件套、tokens、状态交互、文案数据、素材、适配无障碍、baselines、平台映射、红线、反馈闭环、三方对照。V3 只需补它缺的**原生等价性**内容。

### 1.6 交付物路由
上游的真实机制（不是六阶段路由器）：
- 模块路由 `SKILL.md:75-89`；纯机械操作（转换/截图/修 bug/改文案）**不过三方向门**。
- 产物存在性门：`brand-spec.md` / `direction-approved.md` / `导演稿.md` / `polish-log.md`，文件不在 = 环节没做（`SKILL.md:154-164`）。
- 明示跳过表（`workflow.md:9-48`、`SKILL.md:128`）：同项目已选方向的迭代豁免；用户明示「不要三个版本」可降到 1 主 1 变体并记录原话；时间紧可跳过对齐但标「未经早期确认」。
- 上下文阶梯决定要不要新建视觉体系（`design-context.md:9-47`）。

## 2. 逐资源决策

### 2.1 值得吸收（进 V3）

| 资源 | 原始用途 | 已吸收 | 决策 |
|---|---|---|---|
| `references/critique-guide.md` | 六维评分 + 场景加权 + Top10 + 模板 | 是（DesignWise 同名文件已含 0–5 维、场景侧重、Top10、模板） | **保留**，补 App 三项附加检查、严重度、复核方式；不改写判据数值 |
| `references/directions.md` | 6 候选/3 完整、方向卡 6 栏、选择标准、重出规则 | 部分（V2 只有「3 方向、结构差异、一方向一 prompt」） | **改写**为 App 自适应方向策略：`direction-strategy.md` |
| `scripts/design_lint.py` 的 compare/fingerprint | 版式向量 + 色板距离实测防换皮 | 否（`check-ui.mjs` 只有元数据指纹，无相似度） | **改写**：`scripts/direction_divergence.py` 对概念 PNG 做色板距离 + 骨架相关性 |
| `references/polish-loop.md` | 8 问、每轮 3 处、停止规则、首末对比 | 否 | **吸收改写**：`polish-loop.md`，App UI 版 8 问 + 轮次上限 + 停止判据 |
| `references/design-context.md` | 上下文阶梯（DS > 代码 > 已发布 > 品牌 > 无） | 部分（V2 说「读现场」但无阶梯与降级） | **吸收**进 `state-map.md` 与阶段 0：优先从真实代码路径取事实 |
| `references/steady-track.md` | 弱模型/弱运行时的稳妥轨道 | 否 | **部分吸收**：只保留「先写屏幕脚本、从样张起步、逐页检查清单」的降级原则，不引入上游轨道分类 |
| `scripts/capabilities.py` | 本机能力探测（只读有无） | 部分（`zcode_image.py --health`） | **不新增脚本**；保留现有 health 探测 |
| `references/experience.md` + `scripts/learn.py` | 偏好/观察/验证/作废四类记忆 | 否（DesignWise 有 appearance ledger，不做偏好记忆） | **淘汰**：与宿主 Memory 职责重叠，且会引入第二套记忆系统 |
| `SKILL.md` 六角色工作室模型 | 设计角色分工 | 部分（V2 角色是流程角色，不是设计角色） | **吸收**为设计判断视角（一句话级），不新增阶段 |

### 2.2 已吸收、无需再动

| 资源 | 现状 |
|---|---|
| `references/brand-asset-protocol.md` | DesignWise 已有同名文件 |
| `references/content-guidelines.md` | 已有（反 slop、三档对比度） |
| `references/typography.md` | 已有 |
| `references/app-prototype.md` | 已有（设备框、平铺交互、点击测试） |
| `references/design-styles.md` | 已有（含样张） |
| `references/tweaks-system.md`、`react-setup.md` | 已有 |
| `references/verification.md` | 已有且强于上游（三档对比度、真机、双验收） |
| `references/materials.md` 的能力分层 | 已被 `image-generation.md` / `image-assets.md` 覆盖 |
| `scripts/ref_board.py`、`fetch_images.py` | 已在 DesignWise |
| `scripts/check-ui.mjs` 红/黄灯 | 已覆盖上游 lint 的破图/字号/对比度/相对路径/外观族 |

### 2.3 明确淘汰（不迁移）

| 资源 | 原因 |
|---|---|
| `references/modules/*.md`（deck/infographic/motion/web/xiaohongshu） | 非 App UI 载体，DesignWise 已下线 |
| `references/slide-decks.md`、`editable-pptx.md`、`pptx-from-rendered-html.md` | 同上 |
| `references/animations.md`、`gsap-recipes.md`、`camera-language.md`、`cinematic-patterns.md`、`storyboard-basics.md`、`launch-film-director-notes.md`、`hero-animation-case-study.md`、`apple-gallery-showcase.md`、`animation-*.md`、`ui-demo-animation.md`、`hyperframes-backend.md`、`video-export.md`、`ai-video-review.md` | 视频/动效成片能力；V2 已下线，本任务不恢复 |
| `references/voiceover-pipeline.md`、`audio-design-rules.md`、`sfx-library.md`、`demos/voiceover-demo/` | 配音/音频 |
| `references/scene-templates.md` | 8 类场景模板中只有 App UI 一类相关，且已被 `image-generation.md` 的五段结构覆盖 |
| `assets/style-specimens/{ppt,web,info,xhs,east}/` | 非 App 载体；只保留 app 样张 |
| `assets/sfx/`、`assets/bgm-*` | 音频资产 |
| `assets/deck_*`、`cursor.jsx`、`macos_window.jsx`、`browser_window.jsx`、`animations.jsx` | 非 App 载体 |
| `scripts/cloud/*` | 远程模型调用；本机授权外，且 SOL/AI 评审通道不引入 |
| `scripts/design-gate-hook.sh` | 宿主 Hook，与当前环境不兼容；DesignWise 不注册 Hook |
| `scripts/learn.py` | 第二套记忆系统 |
| `package.json` / `cordis.patch.yml` / `references/about-author.md` | 上游运行时与作者宣传，不属能力 |
| 400+ 文件、约 297MB vendored 资产 | 体积与独立性原则 |

## 3. 吸收后仍保留的边界

- 不引入上游任何运行时依赖、脚本调用链或 Hook。
- 不把上游的风格库默认值搬成 DesignWise 的默认审美。
- 上游 `critique-guide.md` 的判据数值保持原样引用，不改写、不"本地化"成新的五维。
- 生成的设计素材不自动继承 MIT；移植的脚本若基于上游实现，按 `THIRD_PARTY_NOTICES.md` 标注。
