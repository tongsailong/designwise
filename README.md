<sub>🌐 <b>中文</b> · <a href="README.en.md">English</a></sub>

<div align="center">

# DesignWise

### 面向 AI Agent 的开源产品设计能力

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent](https://img.shields.io/badge/Agent-Agnostic-blueviolet)](https://skills.sh)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-green)](https://skills.sh)

在支持 Skills 的 AI Agent 里打一句话，拿回一份**经得起产品判断的设计交付**——可点击的 App / Web 交互原型、能编辑的 PPTX、产品发布动画、印刷级信息图，或一次专业设计评审。

3–30 分钟。不是「AI 做的还行」那种水平——内置 84 种 HTML 原生风格库、品牌资产协议与反 AI slop 底线；更关键的是，它在设计前后各加了一层普通设计 Skill 没有的东西：**先判产品价值，再做好看的界面**。

```bash
npx skills add tongsailong/designwise
```

[安装](#安装) · [能做什么](#能做什么) · [效果演示与案例](#效果演示与案例) · [差异化](#核心价值它和普通设计-skill-有什么不同) · [工作原理](#工作原理) · [支持平台与依赖](#支持平台与依赖) · [上游项目与致谢](#上游项目与致谢)

</div>

> **TL;DR**
> **这是什么** — 一个面向 AI Agent 的**产品设计** Skill：既做视觉（交互原型 / 幻灯片 / 动画 / 信息图），也做产品判断（价值取舍 / UX 评审 / Spec 一致性）。
> **解决什么** — 让「一句话需求」变成能交付、能评审、范围不漂移的设计产出，而不是看起来还行的一堆页面。
> **怎么装** — `npx skills add tongsailong/designwise`，跨 agent，不绑定某个具体工具（见 [安装](#安装)）。
> **真的有用吗** — 下面所有演示与样例，都是这个 Skill 自己产出的。

<p align="center">
  <img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/hero-animation-v10-en.gif" alt="演示：终端输入一句话 → 三个设计方向并排 → 聚焦选定方向 → 品牌视觉显形" width="100%">
</p>

<p align="center"><sub>▲ 25 秒 hero 动画：Terminal → 三方向 → Gallery ripple → 四次 Focus → 品牌显形<br>
本演示素材来自上游项目 huashu-design（<a href="https://github.com/alchaincyf">@alchaincyf</a>），本分支完整保留该能力。可本地打开 <a href="demos/hero-animation-v10-en.html">demos/hero-animation-v10-en.html</a> 查看交互版。</sub></p>

> ℹ️ **本项目是 [huashu-design](https://github.com/alchaincyf/huashu-design)（作者 [@alchaincyf](https://github.com/alchaincyf)，MIT License）的二次开发分支。** 上游的视觉设计能力、60 种风格库（本分支已扩到 84 种）、资产协议与交付链**完整保留**；本分支在其上叠加**产品价值判断、UX 与易用性评审、Spec 一致性核验与跨 Agent 适配**。安装本分支请用本仓库命令，**不要**用上游命令（上游入口见 [上游项目与致谢](#上游项目与致谢)）。

---

## 核心价值：它和普通设计 Skill 有什么不同

多数「设计 skill」只回答一个问题：**怎么把它做得好看**。本项目回答两个——**做得对不对**，然后才是**做得好不好看**。

| | 普通设计 Skill | 本项目 |
|---|---|---|
| 设计前 | 直接开工，按「页面该有什么」堆内容 | **先判产品价值**：谁在用 / 此刻要完成什么 / 设计哪一处替他承担了复杂性 |
| 设计判断 | 以视觉为主（配色、排版、层级） | 视觉 + **三条可检验的价值判断**：理解成本 / 操作成本 / 容错 |
| 范围控制 | 习惯性「顺手做完整一点」 | **Scope 冻结**：不做用户没要求的页面与功能，不把「通常会有」当成「被要求」 |
| 评审 | 好不好看 | **概念/立意 + 5 维度评审** + **UX 与易用性一层**（产品界面类）+ 有 spec 时跑一层 **Spec 一致性核验** + **生图前的提示词专家评审**；视觉方向判断与阶段门槛**默认由原生自检看真实像素**；**用户明确授权 GPT 评审通道后**才用 `scripts/zcode_vision.py --confirm-gpt-review`，只有明确点名 Copilot 时才走 copilot 正式 REVIEW（Gate 1 在真实候选图之后给推荐、方向仍由你选定；Gate 2 在精修完成后判阶段门槛），**像素级微调不重复送审** |
| 平台 | 绑定某个 AI 编程工具 | **Agent 无关**：能力 → 载体映射表，弱 runtime 自动降级 |
| 视觉能力 | 视实现而定 | 上游 60 种 HTML 原生风格库（本分支扩到 84 种：+App 12、+中文东亚 12）、视觉方向门（默认 1 个最佳方案）、品牌资产协议、反 AI slop 底线（**完整保留**） |

> 本文中「点名 Copilot」均指：用户**明确点名 Copilot**，或**明确要求使用 `copilot` Skill / Copilot 正式 REVIEW**。未授权时视觉评审走原生自检；外部 GPT（`zcode_vision`）与 Copilot 都不会自动调用。

### 一、产品价值判断（有用 → 好懂 → 舒服 → 有意义）

产品界面 / 交互原型类任务默认加一层轻量判断，四个维度**按顺序成立，前一层不成立、后一层补不上**：

| 维度 | 要问的一句话 | 判错了会怎样 |
|------|-------------|-------------|
| **有用** | 它解决的是真实用户问题，还是我们自己觉得该有？ | 好看但没人需要 = 精致的 slop |
| **好懂** | 用户理解它要花多少力气？复杂性由谁承担？ | 功能在，但用户找不到 / 看不懂 = 等于没有 |
| **舒服** | 有没有无意义的操作、违背既有习惯的交互？ | 每次多一步、多想一下 = 长期摩擦 |
| **有意义** | 功能成立后，值得为它加一点审美 / 情绪 / 身份表达吗？ | 过早加 = 装饰压过功能；永远不加 = 工具感 |

配套三条**可检验**的检查（自检与评审共用）：**理解成本**（几秒内能否说出这页是干嘛的）/ **操作成本**（核心行为几步，其中几步本该系统替用户做）/ **容错**（点错了会怎样，能否撤销、有没有解释）。任一条亮红灯就是该修的点。

完整方法见 [`references/product-value.md`](references/product-value.md)。**动画 / 幻灯片 / 信息图 / 封面等「只是看 / 被展示」的任务不套用**，原有视觉流程照跑——不把设计变成写 PRD。

### 二、UX 与易用性评审

在做设计评审时（用户说「评审」「好不好看」「review」，或你主动质检），产品界面 / 交互原型类会在 **概念/立意（权重最高）与原有 5 维度（哲学一致性 / 视觉层级 / 细节执行 / 功能性 / 创新性）**的「功能性」里**加查一层用户价值与易用性**：核心行为是否被首屏服务、三条价值检查哪条亮灯。问题必须**具体可操作**（说得出改哪一处、改成什么），不做「交互可以更顺」这类空泛评价。

> **走 GPT 概念通路时，生图前还有一层「提示词专家评审」**：提示词已生成但尚未出图，评审只判**文字可判项**（是否服务需求 / 有无区分度 / 有无冲突与歧义 / 哪些要求该留到产品化 / 可实现性），**不决定视觉方向**，也**不会凭提示词宣称「48px 清晰度通过」「满底合规」**——那些结论只由真实图片得出（方向比较由 Gate 1 在真实候选图上做）。

### 三、Spec 一致性核验（Scope / Non-goals / AC）

当项目有设计 spec / 明确需求时，评审额外跑一层**范围核验**：Scope 是否越界、Non-goals 是否被突破、每条 Acceptance Criteria 是否都能在设计里找到对应证据。命中即标 `BLOCKING_SPEC_DEVIATION`；无 spec 时记 N/A。这是**附加核验**，不替代 6 项评审、不新增审批环节。配合设计阶段的 **Scope 冻结**（不做用户没要求的页面 / 功能 / 状态），把「范围漂移」从交付里挡掉。

### 四、跨 Agent 适配（不绑定某个具体工具）

Skill 是 **agent-agnostic** 的：Claude Code、Codex、Cursor、Trae、OpenClaw、Hermes Agent 或任何支持 markdown-based skill 的 agent 都能用。做法不是「为每个平台写一套」，而是把**能力**与**载体**解耦——文档只规定「这一步需要什么能力」（网络检索 / 子代理并行 / 浏览器截图 / 本地命令 / 文件读写），具体工具由 agent 按当前环境自行映射。弱 runtime（无 subagent、非 Claude、上下文小）有**逐级降级模式**，牺牲多样性与流程，**绝不牺牲反 slop 底线与真实资产协议**。见 [`references/runtime-adapters.md`](references/runtime-adapters.md)。

### 五、完整保留的原有视觉设计能力

上面四项是**新增判断层**，它们不替代原有能力——上游的视觉产出链路一条不少：

- **视觉方向探索**：**L2 新视觉设计默认只出 1 个最佳方案**——但仍然先出**真实候选图**，由**原生自检**在真实像素上给结论（授权后才用 `zcode_vision --confirm-gpt-review`；Copilot 正式 REVIEW 仅点名时启用），再收敛出最终提示词与正式概念图，然后做**一套** HTML；**只有存在实质性设计分歧、或你明确要多方向时**才出 2–3 个有实质差异的真实方向，由**你看着真实候选图选定**（L1 局部优化直接改现有 UI，不铺方向门；指定风格 / 品牌也不豁免真实视觉证据）
- **84 种 HTML 原生风格库**（网页 20 + PPT 20 + 信息图 20 + App 12 + 中文东亚 12，纯 CSS 无需生图；App 与中文东亚两区带真实样张）
- **交互原型**（真 iPhone 机身、可点击、Playwright 验证）/ **动画**（Stage + Sprite 时间轴，导出 MP4 / GIF）/ **可编辑 PPTX**（导出真文本框）/ **信息图**（印刷级排版，可导 PDF / PNG / SVG）
- **品牌资产协议**（5 步硬流程，绝不从记忆猜品牌色）/ **反 AI slop 底线**

### 六、参考板 · 外观账本 · 素材选择 · 设计体检（全部复用既有通路）

上游有四项能力本分支之前缺一半或全缺，这次补上，但**不新建第二套机制**：

- **参考板（按需，不强制）**：有参考链接或截图时，`scripts/ref_board.py` 用真实 Chrome 截真实像素、出看板（`board.html` / `board.jpg` / `board.json`），再拆成**能落到 Brief 与 prompt 的规则**（栏数、字号比、主色占比、图文关系、母题）。**借方法不抄标识**；没做就直说没做。→ [`references/design-research.md`](references/design-research.md)
- **外观账本（只提示，不阻断）**：`check-ui.mjs --ledger-add / --ledger-check` 记录并比对设计产物指纹（底色、主色板、字体、骨架），撞族给**黄灯**、不改退出码。它是本机像素指纹记录，**不是记忆系统**——用户偏好走 memory、工程事实走知识库候选。同项目多屏同族是优点，**不为差异化而差异化**。
- **素材先行**：先定主角素材（真实摄影 / 插画 / 数据可视化 / 程序化材质 / 字即图 / 实物仿制 / 场景人物），再定载体；能力按需探测（`zcode_image.py --health`、Node/Chrome、ffmpeg、Pillow），**探测不到降级不阻断**。→ [`references/materials.md`](references/materials.md)
- **设计体检（客观项）**：同一个 `check-ui.mjs` 顺带采集**图片加载失败（红灯）、文字/背景计算对比度（正文 <4.5 红灯，大字 ≥3）、相对路径引图（黄灯）、渐变背景上的未知对比度（黄灯）**，并用 `--shot` 出截图。**脚本只出事实，审美归评审**；黄灯永远不改退出码。→ [`references/verification.md`](references/verification.md)

---

## 能做什么

| 能力 | 交付物 | 典型耗时 |
|------|--------|----------|
| 交互原型（App / Web） | 单文件 HTML · 真 iPhone bezel · 可点击 · Playwright 验证 | 10–15 min |
| 演讲幻灯片 | HTML deck（浏览器演讲）+ 可编辑 PPTX（文本框保留） | 15–25 min |
| 时间轴动画 | MP4（25fps / 60fps 插帧）+ GIF（palette 优化）+ BGM | 8–12 min |
| 设计变体 | 多版并排对比 · Tweaks 实时调参 · 跨维度探索（**多版只在实质分歧或你要求时**；默认单一最佳方案） | 10 min |
| 信息图 / 可视化 | 印刷级排版 · 可导 PDF / PNG / SVG | 10 min |
| 设计方向顾问 | **默认 1 个最佳方案**（模糊需求时可用秒数轮盘 + 现实参照获奖站 + 最佳设计师三套逻辑自查）· 存在实质分歧或明确要求多方向时才出 2~3 个有实质差异的真实方向 | 5 min |
| 视觉概念探索（GPT） | 初始视觉提示词 → 提示词专家评审 → **默认单一最佳方案 1 张真实候选图**（多方案分支：每方向 1 张）→ **Gate 1（默认原生自检看真实像素比较并推荐；授权后才用 `zcode_vision --confirm-gpt-review`；Copilot 仅点名）** → 单一方案直接收敛、多方案分支**你选定方向** → 收敛型最终提示词 → 正式概念图 → 按需**一套** HTML 原型验证体验 → 定向迭代（生图按任务需要，无需逐次付费审批） | 5–15 min |
| 专家评审 | **概念/立意（权重最高）+ 5 维度** · Keep / Fix / Quick Wins · 可操作修复清单 · **含生图前的提示词专家评审**（文字可判 / 不可判边界，不决定方向） | 3 min |

> 耗时为上游实测区间，会随模型能力与任务复杂度浮动。

**适用场景**：高保真交互原型与产品 mockup · 需要被点击 / 演示的界面 · 设计方向探索与变体对比 · 演示幻灯片 · 动画与视频素材 · 信息图与数据可视化 · 设计评审与交付前质检。

**不适用场景**：生产级 Web App · SEO 网站 · 需要后端与数据库的动态系统。这些不走本 Skill。

---

## 安装

```bash
npx skills add tongsailong/designwise
```

> ℹ️ 本仓库原名 `ai-product-design-skill`，已**原地更名**为 `designwise`（仓库 ID、Git 历史与全部提交保留；旧 URL 由 GitHub 重定向）。安装内容与流程不变：此前版本已实测 `npx skills` 安装完整，`references/`、`assets/`、`scripts/`、`demos/` 与仓库逐一对应，无缺文件。若你的环境装出来不完整，见下方故障排查。

**装完先自检**：这个 Skill 不只是 `SKILL.md` 一个文件，`references/`、`assets/`、`scripts/`、`demos/` 四个子目录里有数十个被文档引用的配方、脚本与素材，缺一条路径就走不通。仓库自带自检脚本，可以直接把「装得完不完整」变成一条命令：

```bash
python3 scripts/check-skill.py            # 结构 + 引用完整性
python3 scripts/check-skill.py --strict   # 额外检查未被引用的孤儿文件
```

装完看一眼安装目录（如 `~/.claude/skills/designwise/`）。**若只有 SKILL.md、没有那几个子目录**，说明 `skills` CLI 版本太旧（≤1.5.15 有一个只同步单文件的 bug，已在 1.5.19 修复）。升级后再装一次：

```bash
npm i -g skills@latest        # 或 npx skills@latest add tongsailong/designwise
```

仍异常就用 `git clone` 兜底——把仓库克隆到任意 skills 目录即可：

```bash
git clone https://github.com/tongsailong/designwise.git ~/.claude/skills/designwise
```

安装后在 Claude Code / Codex / Cursor 等任意支持 skills 的 agent 里直接说话（见下一节）。

---

## 使用示例

没有按钮、没有面板、没有 Figma 插件——只需要一句话：

```
「做个 AI 番茄钟 iOS 原型，4 个核心屏幕要真能点击」
「做一份 AI 心理学的演讲 PPT，推荐 3 个风格方向让我选」
「把这段逻辑做成 60 秒动画，导出 MP4 和 GIF」
「帮我对这个设计做一次评审，重点看易用性」
「这是我们 App 的 spec，检查一下实现有没有超出范围、AC 有没有漏」
「界面有点乱，帮我看看理解成本和操作成本哪里有问题」
「用我们品牌（logo + 色板 + UI 截图）做一套官网首页，出三个方向」
「把这个季度的数据做成一张印刷级信息图，能导 PDF」
```

---

## 效果演示与案例

### 本地可直接打开

- **24 个预制设计样例**：8 种场景 × 3 种风格（Pentagram / Build / Takram），PNG 缩略图 + 可渲染 HTML，索引见 [`assets/showcases/INDEX.md`](assets/showcases/INDEX.md)
- **18 个能力演示 HTML**（中英双版，`-en` 为英文）：`demos/c1-ios-prototype.html`、`c2-slides-pptx`、`c3-motion-design`、`c4-tweaks`、`c5-infographic`、`c6-expert-review`、`w1-brand-protocol`、`w2-junior-designer`、`w3-fallback-advisor`，以及 `demos/hero-animation-v10-en.html`
- **长视频 / 配音演示**：`demos/md-html-narration/`、`demos/voiceover-demo/`

### 动态演示（GIF 素材来自上游 Releases）

> 以下 GIF 由上游项目 huashu-design（[@alchaincyf](https://github.com/alchaincyf)）制作并分发，本 Skill 完整保留对应能力；截图与文案描述引用其公开说明。

**设计方向顾问** — 模糊需求时三套互补逻辑（秒数轮盘 + 现实参照获奖站 + 最佳设计师）互相校验，收敛出最优方向；需要比较时才并行出 2–3 版真实视觉让你看着选。**下图是上游演示，展示的是多方案分支**（本分支默认单一最佳方案）。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/w3-fallback-advisor.gif" alt="上游设计方向顾问演示：多方案分支下三套逻辑并行生成的三个差异化设计方向并排展示" width="100%"></p>

**iOS App 原型** — iPhone 15 Pro 精确机身（灵动岛 / 状态栏 / Home Indicator）· 状态驱动多屏切换 · Playwright 自动点击测试。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c1-ios-prototype.gif" alt="iOS App 原型演示：真机机身内多个屏幕状态切换与点击交互" width="100%"></p>

**Motion Design 引擎** — Stage + Sprite 时间片段模型 · `useTime` / `useSprite` / `interpolate` / `Easing` 四 API · 一条命令导出 MP4 / GIF / 60fps 插帧 / 带 BGM 成片。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c3-motion-design.gif" alt="动画引擎演示：时间轴驱动的动态图形与过渡效果" width="100%"></p>

**HTML Slides → 可编辑 PPTX** — `html2pptx.js` 读 DOM 的 computedStyle 逐元素翻译成 PowerPoint 对象，导出的是**真文本框**，PPT 里双击即可编辑。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c2-slides-pptx.gif" alt="幻灯片演示：HTML deck 切换与导出的可编辑 PPTX 文本框" width="100%"></p>

**Tweaks · 实时变体切换** — 配色 / 字型 / 信息密度参数化 · 侧边面板切换 · 纯前端 + `localStorage` 持久化。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c4-tweaks.gif" alt="Tweaks 演示：侧边面板切换配色与字型，页面实时变化" width="100%"></p>

**信息图 / 数据可视化** — 杂志级排版 · CSS Grid 精准分栏 · 真数据驱动 · 可导矢量 PDF / 300dpi PNG / SVG。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c5-infographic.gif" alt="信息图演示：数据驱动的杂志级排版长图" width="100%"></p>

**专家评审** — 概念/立意（权重最高）+ 5 维度各 0–10 分 · 雷达图可视化 · 输出 Keep / Fix / Quick Wins 清单。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/c6-expert-review.gif" alt="设计评审演示：五维雷达图与 Keep/Fix/Quick Wins 清单" width="100%"></p>

**Junior Designer 工作流** — 不闷头做大招：先写 assumptions + placeholders + reasoning，尽早 show 给你，再迭代。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/w2-junior-designer.gif" alt="Junior Designer 工作流演示：先展示占位与假设，再逐步迭代填充" width="100%"></p>

**品牌资产协议 5 步硬流程** — 问 → 搜 → 下载（三条兜底）→ grep 色值 → 写 `brand-spec.md`。

<p align="center"><img src="https://github.com/alchaincyf/huashu-design/releases/download/v2.0/w1-brand-protocol.gif" alt="品牌资产协议演示：从官方渠道抓取 logo 与色值并固化到 spec" width="100%"></p>

### 上游作者的真实案例（引用，非本分支产出）

- **鹦鹉进化史网站** — 一句「做个介绍鹦鹉进化史的网站」，自动跑完顾问流程：判断图片为内容必需 → 抓公共领域博物插画 → 三套逻辑并行各出一版。Live demo：<https://www.huasheng.ai/parrots/>
- **「聊聊 skill」PM after-party 演讲 deck** — 13 页 HTML deck，全部用该 Skill 完成，含两个带 BGM + SFX 的 22 秒 cinematic demo。Live demo：<https://skill-huasheng.vercel.app>

---

## 工作原理

### 视觉方向探索：GPT 在真实候选图上给结论，默认单一最佳方案（多方向只是分支）

收到 **L2（新视觉语言或重大结构变化）** 任务，**默认只出 1 个最佳方案**——但这不等于跳过真实视觉：指定了风格或品牌也不豁免，反而更需要真实像素作证。**L1 局部优化直接改现有 UI，不铺方向门。** **提示词先经专家评审**（生图前，只判文字可判项、**不决定方向**），然后用通过的提示词**生成 1 张真实候选图**；默认由**原生自检**在这些**真实像素**上做 **Gate 1**；授权后才用 `zcode_vision --confirm-gpt-review`（Copilot 仅点名），输出**结论 + 依据 + 风险**。**只有存在实质性设计分歧、或你明确要多方向时**，才出 2–3 个真正不同的方向、每方向 1 张真实候选图，并把选择权交回给你。收敛后生成正式概念图。

**需探索新视觉方向的任务**（App 图标 · 启动页改版 · App 首页或重要页面整体设计 · 多页面视觉体系 · 品牌视觉探索 · 插画主视觉 · 交互原型）走这条完整链路：

```
初始视觉提示词 → 提示词专家评审（生图前，不决定方向）
  → 默认单一最佳方案：1 张真实候选图（多方案分支才 2–3 个方向，每方向 1 张）→ 逐张质量自检
  → **Gate 1**（默认原生自检看真实像素给结论 → 通过 / 风险；授权后才用 `zcode_vision`；Copilot 仅点名）
  → 单一方案直接收敛 / 多方案分支：展示候选图 + 推荐 → **你选定方向** → 收敛型最终提示词 → 正式概念图（质量自检）
  → 概念图转译成视觉规范 → 按需做该方向的一套 HTML 原型
  → 客观尺寸 / 几何 / 遮罩验证 + 第二次评审与定向迭代 → **Gate 2**（默认原生自检对照已确认概念图判阶段门槛；授权后才用 `zcode_vision`；Copilot 仅点名）
  → 通过则进入产品化 / 收口；不通过则只针对影响核心目标的问题定向修改
  → 产品化落地（按需 GPT 正式图片素材）→ 真实运行与验收
```

- **GPT 负责创意探索**：默认给出 **1 个最佳候选方向**（含完整生图 Prompt 与 **1 张真实候选图**）；只有存在**实质分歧或你明确要多方向**时才出 2–3 个有实质差异的候选；生图是**正常的模型能力**，任务范围内自主生成，**不需要逐次申请付费审批**；🔴 **真实候选图是必要投入**——方向错了的返工远贵于一张候选图；同时**不为凑数硬出方向**
- 🔴 **提示词先评审，但不决定方向**：初始视觉提示词交给 **Huashu 原有的专家评审机制**评估（Keep / Fix / Quick Wins），只判**文字可判项**——是否服务需求 / 有无区分度 / 有无冲突与歧义 / 哪些要求该留到产品化 / 可实现性；**发现问题先改提示词再往下**，**不允许跳过评审直接大量生图**；🔴 **本节不产出方向决策**
- 🔴 **Gate 1 在真实候选图之后**：真实候选图生成后，默认由**原生自检**基于真实像素评审（单一方案判「是否成立」，多方案分支逐张比较并标注版本 / 角色）；授权后才交 `zcode_vision --confirm-gpt-review`（Copilot 仅点名），输出**结论 / 推荐方向 + 理由 + 风险**。**真实图产生之前不做 Gate 1**——那时没有像素可比，任何方向结论都只是文字推测
- **评审不越界**：生图前的评审只判**文字可判项**，**不会凭提示词宣称「48px 清晰度通过」「满底合规」**——这些结论只由真实图片得出
- 🔴 **方向归属按分支**：**多方案分支**——GPT 只给推荐，**方向由你在真实候选图上选定**，未选定不进入下一步；**单一方案**——由 agent 基于真实候选图与 Gate 1 结论决策，在 `design-brief.md` 标注为 `agent 决策`（**不得写成「用户选择」**），你随时可以否决并要求换方向。🔴 **定下后只针对该方向继续**，不为其他候选做 HTML 或工程资源
- 🔴 **收敛后重新生成收敛型最终提示词**：收敛期提示词**只围绕已定方向**，用来提高正式概念图的稳定性、明确性与可产品化程度；**不重新引入新方向、不重跑方向选择**；🔴 **探索提示词 ≠ 最终概念图提示词**（不得原封不动拿来用）
- **HTML 按需验证体验**：只有需要验证交互与多状态时才做，且**只做选定方向的一套**；App 图标、简单静态启动页、单张品牌图等直接跳过
- **HTML 要还原视觉，不只是结构**：**视觉价值依赖图片素材时**（插画 / 人物 / 主视觉 / 复杂背景 / 装饰 / 产品展示图），用 GPT 生成**验证素材**把概念图还原出来——**不得用占位图 / 随机图库 / 简单替代**，否则视觉评审会失真。纯布局 / 列表 / 表单 / 几何 / 已有正式资源不必生图
- **质量自检 + 约束分层**：生图前把需求拆成**硬约束**（用途识别 / 品牌色 / 尺寸安全区 / 尺寸可辨）与**可探索约束**（构图 / 元素 / 隐喻，交给 GPT）；生图后按目标底色合成核对硬约束、以「用户能否一眼识别」为首要判据，**不只用像素占比、连通块等技术指标**
- **阶段门槛审 Gate 2**：产品化 / 精修完成后，把真实渲染截图（或产品化产物）对照**已确认概念图** + 客观测量默认交**原生自检**做 **Gate 2**；授权后才交 `zcode_vision --confirm-gpt-review`（Copilot 仅点名），判「方向是否仍成立 / 是否偏离选定方向 / 是否达到下一阶段或收口标准」；**通过就收口，不通过只改影响核心目标的问题**
- **第二次评审定向迭代**：先问「HTML 是否真还原了概念图视觉，而非仅还原结构」；视觉不满意 → 针对该方向重新生图 / 重出验证素材；交互不满意 → 优先改现有 HTML；必要时两者结合——**不从头重跑整个流程**
- 🔴 **像素级微调不默认触发 GPT**：1~2% 几何调整、间距 / 圆角 / 单节点位置微调、已由客观测量确认解决的问题，**不重新送审**；**只有**发生实质视觉变化 / 出现新视觉问题 / 跨越新阶段门 / 对判断有争议 / 客观验证解决不了 / 需重选方向，才重新调用——**禁止「改一点 → GPT 看 → 再改一点 → GPT 看」的循环**
- **验证素材不浪费**：产品化时可直接复用 / 按工程要求重出正式素材 / 改用矢量或代码实现（哪个更可靠就选哪个）
- **成本可控**：按实际需要决定生成数量、失败有限重试、已有素材优先复用、不做"探测式"生成；规模明显扩大按正常任务范围变更处理
- **生图不可用**：**明确报告并暂停生图环节**（可交付完整 prompt 供你在 ChatGPT 出图后交回），**不静默回退成 HTML/SVG 代码绘图冒充概念图**，也不放占位图冒充已还原

**局部修改、Bug 修复、功能实现、适配与简单文案布局修正不进这条链路**，直接实现与验证，不重复生图。完整规则见 [`references/gpt-visual-workflow.md`](references/gpt-visual-workflow.md)。

### 产品价值判断与 Scope 冻结

产品界面类任务在开工前写下三行（谁在用 / 要完成什么 / 哪一处替他承担复杂性），并在各方案 spec 里共用同一行需求定义（**默认 1 个方案**；多方案分支 2–3 套 spec 共用同一行）。设计过程中**不做用户没要求的页面 / 功能 / 状态**——需要扩张就交回用户决定，不自行把「不做 X」改成「做了 X」。

### 品牌资产协议（5 步，绝不猜）

| 步骤 | 动作 | 目的 |
|------|------|------|
| 1 · 问 | 用户有 brand guidelines / logo / 产品图 / UI 截图吗？ | 尊重已有资源 |
| 2 · 搜官方品牌页 | `<brand>.com/brand` · `brand.<brand>.com` · `<brand>.com/press` | 抓权威色值 |
| 3 · 下载资产 | SVG 文件 → 官网 HTML 全文 → 产品截图取色 | 三条兜底，前一条失败立刻走下一条 |
| 4 · grep 提取色值 | 从资产里抓所有 `#xxxxxx`，按频率排序，过滤黑白灰 | **绝不从记忆猜品牌色** |
| 5 · 固化 spec | 写 `brand-spec.md` + CSS 变量，所有 HTML 引用 `var(--brand-*)` | 不固化就会忘 |

### Junior Designer 工作流

默认工作模式（按任务分层使用）：开工前一次性发问题清单、等批量答完；HTML 里先写 assumptions + placeholders + reasoning；尽早 show 给你（哪怕只是灰块）；**L2 或你明确要求对比时**填充内容 → variations → Tweaks 三步分别再 show（**L1 直接改现有 UI**，不铺多版）；交付前用 Playwright 肉眼过一遍浏览器。

### 事实验证先于假设（核心原则 #0）

任务提到具体产品 / 技术 / 事件时，第一步必须是检索核实（存在性、版本、规格），不从训练记忆里直接断言。一次检索约 10 秒，一次错误假设可能让返工花 1–2 小时。

### 反 AI slop 底线

避免一眼 AI 的视觉最大公约数（紫渐变 / emoji 图标 / 圆角 + 左边框的「强调条」/ SVG 画人脸 / Inter 当 display 字体）。用 `text-wrap: pretty` + CSS Grid + 精心选择的 serif display 与 oklch 色彩。

---

## 支持平台与依赖

**Agent 支持**：Claude Code · Codex · Cursor · Trae · OpenClaw · Hermes Agent，或任何支持 markdown-based skill 的 agent。弱 runtime（无 subagent / 非 Claude / 上下文受限）自动进入降级模式：**L2** 仍然要有真实候选图（默认 1 张；多方案分支改为串行、差异化隔离）；**L1** 直接改现有 UI。

**本地工具链**（按需，只有用到对应导出/验证能力时才需要）：

| 依赖 | 用途 |
|------|------|
| Node.js | `scripts/render-video.js`（HTML→MP4）、`html2pptx.js`、`export_deck_*.mjs`、`gen_deck_thumbs.mjs`；`scripts/check-ui.mjs`（UI 验收采集：触控/字号/溢出/控制台/图片/对比度/指纹，`--shot` 截图、`--ledger-*` 账本，无 npm 依赖）；`package.json` 依赖 `playwright` / `pptxgenjs` / `pdf-lib` / `sharp` |
| ffmpeg | MP4 转 60fps / GIF、拼接 BGM、音视频混流（`convert-formats.sh`、`add-music.sh`、`mix-voiceover.sh`） |
| Python 3 | `scripts/verify.py`（Playwright 验证）、`fetch_images.py`、`ref_board.py`（参考板采集，需 Chrome）、`check-skill.py`（结构自检）、`check-contrast.py`（对比度）、`check-assets.py`（素材清单）、Pillow（参考板拼图与空白检测，可选） |
| Playwright | 交付前的浏览器点击测试与截图验证 |

**云能力（完全可选）**：豆包 TTS 配音与 AI 看片评审隔离在 `scripts/cloud/`，需要你自备 API key，首次调用要显式 `--yes` 确认。默认不使用。核心链路（设计 → 渲染 → MP4 / PDF / PPTX 导出）**100% 本地运行，零网络、零 key**，无 telemetry。全部出站域名、密钥处理与删除边界见 [SECURITY.md](SECURITY.md)。

---

## 项目限制

- **不支持图层级可编辑的 PPTX 回 Figma**。产出是 HTML：可截图、录屏、导图，但不能拖进 Keynote 改文字位置。
- **Framer Motion 级别的复杂动画不行**。3D、物理模拟、粒子系统超出本 Skill 边界。
- **完全空白的品牌从零设计，质量会掉到 60–65 分**。凭空画 hi-fi 本来就是 last resort。
- 本 Skill 面向「用 HTML 做视觉产出」的场景，**不做生产级 Web App、SEO 网站、需要后端的动态系统**。

这是一个 80 分的 Skill，不是 100 分的产品。对不愿意打开图形界面的人，80 分的 Skill 比 100 分的产品好用。

---

## 仓库结构

```
ai-product-design-skill/          # 仓库更名 designwise（本目录为历史名）
├── SKILL.md                 # 主文档（给 agent 读，中文）
├── README.md                # 中文 README（默认，本文件）
├── README.en.md             # 英文 README
├── SECURITY.md              # 安全与数据流声明
├── LICENSE                  # MIT
├── assets/                  # Starter Components + 预制样例
│   ├── animations.jsx       # Stage + Sprite + Easing + interpolate
│   ├── ios_frame.jsx        # iPhone 15 Pro bezel
│   ├── android_frame.jsx · macos_window.jsx · browser_window.jsx
│   ├── deck_stage.js        # HTML 幻灯片引擎
│   ├── deck_index.html      # 多文件 deck 拼接器
│   ├── design_canvas.jsx    # 并排变体展示
│   ├── cursor.jsx           # 产品 UI 演示光标叙事
│   ├── showcases/           # 24 个预制样例（8 场景 × 3 风格）
│   └── bgm-*.mp3 · sfx/     # 场景化背景音乐与音效库
├── references/              # 按任务深入读的子文档
│   ├── product-value.md     # 产品价值判断（有用→好懂→舒服→有意义）
│   ├── critique-guide.md    # 概念/立意+5 维度评审 + 易用性 + Spec 一致性核验 + 生图前 Prompt 级评审
│   ├── runtime-adapters.md  # 能力 → 载体映射（跨 Agent）
│   ├── design-styles.md     # 84 种 HTML 原生风格库（App / 中文东亚带样张）
│   ├── design-research.md   # 参考板（真实像素拆规则）+ 外观账本（撞族黄灯）
│   ├── materials.md         # 主角素材矩阵 + 素材能力分档与探测
│   ├── app-prototype.md · slide-decks.md · editable-pptx.md
│   ├── animation-*.md · camera-language.md · storyboard-basics.md
│   └── ...
├── scripts/                 # 导出与验证工具链
│   ├── render-video.js      # HTML → MP4
│   ├── convert-formats.sh   # MP4 → 60fps + GIF
│   ├── add-music.sh         # MP4 + BGM
│   ├── export_deck_pdf.mjs · export_deck_pptx.mjs · html2pptx.js
│   ├── verify.py · check-ui.mjs · check-contrast.py · check-assets.py · check-skill.py
│   ├── ref_board.py         # 参考板采集（真实截图 + board.html/jpg；需 Chrome）
│   └── cloud/               # 可选云能力（自备 key + --yes）
└── demos/                   # 能力演示（中英双版 HTML）+ hero 动画
```

> `test-prompts.json` 是**验收提示集**（人工或会话内逐条执行的断言清单），不是自动测试框架——运行方式是在真实会话里按 `prompt` 走一遍、核对 `expected`。`scripts/check-skill.py` 只校验它存在，不执行它。

结构自检：

```bash
python3 scripts/check-skill.py            # 结构 + 引用完整性
python3 scripts/check-skill.py --strict   # 额外检查孤儿文档
```

### 维护者：源码仓库与运行时副本

本仓库（git 工作区）是**唯一源码**；agent 的 skills 目录是**运行时副本**，只由
`scripts/sync_runtime.py` 单向写入。不要手工改副本：

```bash
# 默认只检查；有漂移时退出码 1
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --check

# 确认后写入缺失/不同的文件；默认不删除目标多出的文件
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply

# 只有明确要删除副本多余文件时才加 --prune（危险）
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply --prune
```

脚本自动排除 `.env` / `.env.*`（保留 `.env.example`）、`assets/personal-asset-index.json`、
`.git`、`node_modules`、`design-demos`、`__pycache__`，以及**开发资产**：根目录 `AGENTS.md` 与
`scripts/test_*.py`（只匹配 `scripts/` 的直接子文件，不波及其它目录的同名文件），并拒绝源码/目标互为祖先或后代。

运行时副本包含运行所需资产：`SKILL.md`、`README*.md`、`SECURITY.md`、`LICENSE`、`references/`、
`assets/`、`demos/`、`scripts/` 中的运行脚本，以及根目录的 `.gitignore`、`.env.example`、`package.json`、
`package-lock.json`、`test-prompts.json`。**`LICENSE` 始终随副本分发**（MIT 许可证义务，不得排除或删减）。
排除对源与副本两侧同时生效，因此排除生效前已存在于副本中的旧开发资产不会被 `--check` 报为漂移、
也不会被 `--prune` 删除，需单独清理。

目标必须含 `SKILL.md` 的 `name: designwise`；首次安装到空目录时加 `--force`。
若在副本上做了紧急修改，先搬回源码仓库再同步，不做双向合并。详见 `references/zcode-host.md`。

---

## 上游项目与致谢

本项目的视觉能力、方法论源头与下列素材来自上游：

**[花叔Design · huashu-design](https://github.com/alchaincyf/huashu-design)** — 作者 [@alchaincyf](https://github.com/alchaincyf)（花生 / 花叔），MIT License。

- 上游仓库与安装命令（**安装本项目请用本仓库命令**）：`npx skills add alchaincyf/huashu-design`
- 上游作者录制的新手教程：<https://www.youtube.com/watch?v=m-_BlUdcIvw>
- 上游 Star 趋势：<https://star-history.com/#alchaincyf/huashu-design&Date>
- 上游作者的案例：鹦鹉进化史网站 · 「聊聊 skill」演讲 deck · [FanBox · Coding Agent 的驾驶舱](https://github.com/alchaincyf/fanbox)
- 上游作者自述的起源故事：Anthropic 发布 Claude Design 后，作者让 agent 拆解其公开的系统提示词、品牌资产协议与组件机制，蒸馏成结构化 spec 并写成 Skill。
- **样张资产来源**：`assets/style-specimens/` 的 50 个文件（App 12 + 中文与东亚 12，每种含 `.html` 源码与 `.jpg` 样张；另加 `sheet-app.jpg` / `sheet-east.jpg` 两张分区总览板）取自上游同一路径，与本仓库文件**字节一致**。上游以 MIT License 发布仓库内容，样张是其**原创 HTML/CSS 演绎**（题材与数字虚构）；风格名中的设计师 / 工作室与书名只作**风格参照**，不是其作品的复制，也不代表作者授权或背书。

<table>
<tr><td>

**<b>上游作者的自我介绍（原作者本人，非本项目贡献）</b>**：花生是 AI Native Coder、独立开发者、AI 自媒体博主。代表作：小猫补光灯（App Store 付费榜 Top 1）、《一本书玩转 DeepSeek》、女娲 .skill。X / 公众号 / B站 / YouTube / 小红书 / [huasheng.ai](https://www.huasheng.ai/) / [bookai.top](https://bookai.top) 均可找到他。

</td></tr>
</table>

> 上游项目还维护了社区翻译版本（English / 한국어 / Tiếng Việt），翻译质量与各版本 license 条款由对应维护者负责，详见上游仓库。

**本分支的差异**（谁做了什么，不混淆）：本分支由本仓库维护者维护，在保留上游全部视觉能力的前提下，新增并迭代 **产品价值判断、UX 与易用性评审、Spec 一致性核验、跨 Agent 能力映射**。README 中标注「上游 / 原作者」的演示、教程、案例与自我介绍，其版权与贡献归上游作者。

关于上游的知识产权处理：上游曾基于 Anthropic 公开的 Claude Design 提示词思路与社区流传材料做二次创作；本分支进一步将其中依赖专有代码的部分（如幻灯片转 PPTX）净室重写为自有实现。详见提交历史与 [LICENSE](LICENSE)。

### 想给本项目贡献

发现安装问题、引用缺失或想补充语种？欢迎开 issue。翻译请同时给出 `SKILL.md` 与 `README.md` 的对应改动。

---

## License

[MIT License](LICENSE)。你可以**自由使用、修改、分发**，**包括商业用途**——公司内部用、客户商单交付、做成付费产品对外卖，都没问题。无需事先授权、无需付费。注明出处不强制，但欢迎。

上游 huashu-design 自 2026-05-14 起同样采用 MIT License（此前为限制商用的 Personal Use License，该限制已解除）。本分支继承同一许可证，并保留原作者署名。
