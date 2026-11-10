<sub>🌐 <b>中文</b> · <a href="README.en.md">English</a></sub>

<div align="center">

# DesignWise

### 面向 AI Agent 的 App UI 设计与落地能力

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent](https://img.shields.io/badge/Agent-Agnostic-blueviolet)](https://skills.sh)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-green)](https://skills.sh)

只做一件事：把一个 App UI 需求，从**全页面产品理解**一路做到**真机双验收**——先用 Copilot 预审提示词，再由 GPT 生成三个真实概念方向，Copilot 基于真实像素决定采用 / 融合 / 拒绝，HTML 高保真原型经真实截图设计评审，最后把设计意图（不是只把配色）落到原生 App，并用旧版 / HTML / 新版三方真机对照验收。

```bash
npx skills add tongsailong/designwise
```

[标准流程](#唯一标准流程) · [产品原则](#产品原则) · [生图与素材](#gpt-生图与素材复用) · [能力范围](#能力范围) · [安装](#安装) · [依赖](#支持平台与依赖) · [上游与致谢](#上游项目与致谢)

</div>

> **TL;DR**
> **这是什么** — 一个**只服务 App UI** 的设计 skill：信息架构、导航、布局、视觉与交互规范、HTML 高保真原型、原生转译、图片素材生成与复用、真机验收。
> **怎么走** — 唯一标准流程，没有 L1/L2/L3 分层：全页面理解 → 提示词预审 → GPT 三方向概念图 → Copilot 方向选择 → HTML 原型与设计评审 → 素材 → 原生实现 → 真机三方对照与工程/设计双验收。
> **不能跳的** — 整机重设计的页面地图、生图前预审、三方向真实概念图、Copilot 基于真实像素的方向决策、真实截图设计评审、原生落地映射。局部迭代复用已定方向，不重新探索。
> **不做的** — 幻灯片、视频、音频、信息图、海报，生产级 Web App 与后端系统。

> ℹ️ **本项目是 [huashu-design](https://github.com/alchaincyf/huashu-design)（作者 [@alchaincyf](https://github.com/alchaincyf)，MIT License）的独立二次开发分支。** 保留了上游的视觉方法论、风格库、资产协议与交付链，并按 MIT 义务保留 `LICENSE` 与署名（见 [上游项目与致谢](#上游项目与致谢)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。**本分支独立维护**：不跟随上游同步，运行时也不依赖上游或其他 skill。

---

## 唯一标准流程

**没有任务分层。** 所有新 App UI 任务走同一条流程；流程内部按**证据门**推进，不按审批仪式推进。

| 阶段 | 目标 | 证据门 |
|---|---|---|
| **0 任务受理与产品理解** | 搞清真实需求、完整产品范围与约束 | 事实与约束有来源；原生可行性已记录；整机重设计有覆盖全部页面/弹层的页面地图 |
| **1 设计目标与假设** | 固定方向探索的输入 | 目标对应已识别问题或有依据的保留项；无未标注假设 |
| **2 GPT 三方向概念图** | 先审提示词，再用真实像素探索 3 个实质不同方向 | 预审已发生且绑定生成版本；3 张真实、可解码、同比例、结构可辨、硬约束不破 |
| **3 Copilot 方向选择** | 基于真实像素先判合格性，再决定采用 / 融合 / 拒绝 | 3 张图都在请求内；身份核验通过；有单一目标方案或全部拒绝；融合有统一逻辑 |
| **4 HTML 高保真原型** | 把选定方向变成可交互真实视觉并过设计评审 | 真实渲染；控制台 0 error；状态/对比度/触控达标；真实截图评审已修正复验 |
| **5 设计完善与素材生成** | 补齐视觉资产并保证可复用 | 每张素材有来源、sha256、消费者；无未决临时图 |
| **6 App 原生实现** | 把设计意图落地成原生 UI，不是换皮 | 构建/安装/可启动/流程可走；关键结构/层级/交互落地或有依据保留；三方对照已开始 |
| **7 真机验收与收口** | 用真实设备做工程与设计双验收 | 验收矩阵逐项有本轮真实证据；工程与设计分别达标才 PASS |

### 不可省略的规则

1. **整机重设计先建页面地图，不能只数页面、收截图。** 每页/每个弹层写清用户目标、主要功能、关键信息与数据口径、业务规则、适用状态、当前问题、值得保留的成熟体验与依据、要重构的部分，加导航与关键任务路径。数量与截图不证明理解完成。
2. **三个方向必须真实、必须结构不同，而且共享同一套产品约束。** 三张 prompt 逐字共用**任务块**（产品/用户/本页问题/硬约束/禁止项）与**原则转译块**（把「有用 → 好懂 → 舒服 → 有意义」转成本页可检查的要求，不是复述原则名）；差异只落在方向块——布局骨架 / 信息组织 / 视觉母题，只换配色、间距或圆角不算方向，也不靠增删业务功能制造差异。每个方向一个 prompt、一次真实生图，App 默认竖版 `1024x1536`，三张同比例同尺寸同模型，便于并排比较。
3. **生成前先预审提示词。** 三组方向与完整 prompt 先用文本证据走 Copilot `CONSULT`：是否真回答已识别的产品问题、是否依赖不存在的资产、是否伪差异、共用块是否锁死解法。修订后把「预审版本 → 生成版本」记进 `concept-prompts.md`；**不允许先出图再补审**。CONSULT 不可用则暂停生成（可交付已预审 prompt 供外部真实出图）。
4. **方向由 Copilot 基于真实像素决策，出口有三个。** 执行 agent 不得自选后伪称 Copilot 裁决，也不得用文字总结、文件名或缩略图替代真实图片。证据桥接把三张图都放进请求，`CONSULT` 先逐方向判断是否合格，再给**采用 / 融合为统一方案 / 全部拒绝**之一：融合要说明取用、舍弃与统一层级交互逻辑，结构性融合须补真实整合图；全部拒绝时给出 prompt 修正建议，只重出受影响方向。**失败关闭**（图缺失 / 未入请求 / 身份核验失败 / 承认看不到图 / 只有泛泛评价 / 未判合格性就挑「最不差」，都不算裁决）。
5. **机械校验通过不等于设计完成。** 阶段 4 还要用当前版本真实渲染截图（含弹层与空/错/大字体）走 `CONSULT` 设计评审：功能表达、IA 与层级、核心操作、四原则、页面/状态/组件完整性、方向意图、漂亮但不实用的问题；修正后用新截图复验。
6. **HTML 是原型，不是产品；也是设计目标，不是配色参考。** 最终实现必须是原生 App，**不得把原型 HTML 塞进 App 充当实现**；原生落地允许重构页面结构、组件层级、IA 与交互，**最小改动不是设计理由**，只换 token 不算落地。保留旧结构要有真实依据（用户任务、可读性、平台惯例、成熟体验），不能拿「代码可复用 / 测试锁住了」当理由。
7. **验收分两条线，且要三方对照。** 工程验收（功能/业务规则/测试/构建/真实运行）与设计验收（产品目标/页面完整/原则/原型意图/真机体验）分别给结论，两项都达标才 PASS；用旧版 App ↔ HTML ↔ 新版真机的真实证据检查改善与退化。**不得用代码修改量、视觉变化百分比、页面改动数量或测试数量替代设计成功。**

**局部迭代**（文案、间距、单个组件状态、Bug、适配、替换已登记素材）复用 `design-brief.md` + 三图记录 + `direction-approved.md`，从阶段 4 继续，不重新探索三方向。**实质变化**（换 token 或视觉母题、信息架构/导航变化、跨多页面视觉体系、品牌探索、新核心流程）按新任务重走 0–7。

---

## 产品原则

**顺序：有用 → 好懂 → 舒服 → 有意义。前一层不成立，后一层补不上。**

| 层 | 要问的一句话 | 判错了会怎样 |
|---|---|---|
| **有用** | 服务真实需求与真实任务，还是我们自己觉得该有？ | 好看但没人需要 = 精致的 slop |
| **好懂** | 用户理解它要花多少力气？复杂度由谁承担？ | 功能在，但找不到 / 看不懂 = 等于没有 |
| **舒服** | 有没有无意义操作、违背平台习惯的交互？ | 每次多一步、多想一下 = 长期摩擦 |
| **有意义** | 方向能说明它服务什么定位、场景、用户吗？ | 风格抽签；用积分/徽章/动画代替真实价值 |

- **游戏化是可选手段，不是产品目标。** 不强制积分、勋章、排行榜、签到或任务体系；不用强制任务、损失焦虑、虚假稀缺、惩罚性连续或过度竞争制造压力；不以短期活跃牺牲长期价值。不采用游戏化也可以是更好的设计。
- **自主感 / 掌控感 / 成长感是判断视角，不是功能清单。** 不要求每个产品、每个页面、每个版本同时提供三者。
- **专业信息密度正当。** 工具、数据、上下文感知类产品允许高密度；但每一处信息都要有内容价值，装饰性 icon、无意义 stats 与状态点仍是 slop。
- **系统承担复杂度。** 该由系统判断、合并、解释的东西，不推给用户逐步操作。

完整方法见 [`references/product-value.md`](references/product-value.md)；落地到各阶段的检查见 [`references/app-visual-workflow.md`](references/app-visual-workflow.md)。

---

## GPT 生图与素材复用

生图是**本 skill 内建能力**，不依赖其他 skill：`scripts/zcode_image.py` 走 OpenAI 兼容的图像接口（默认 `gpt-image-2.5`），支持 `--health` 零成本核验、`--ref` 参考图、`--size` / `--fit` 尺寸与裁切、`--n` 批量。凭据来自环境变量或本机 provider 配置，不写进仓库。

- **贯穿全程**：方向概念图（阶段 2）→ 原型补齐视觉（阶段 4）→ 局部元素/插画/背景/装饰（阶段 5）。三处保持同一视觉语言、参考图、尺寸与裁切规则。
- **先复用，再生成**：查 `asset-manifest.json`、项目已有素材、已登记的概念图与原型资产；能复用就不重新生成，不为微小差异重复生图。
- **素材三态**：参考图（判断输入，不是产出）/ 概念图（只用于方向比较）/ 正式素材（可进产品）。概念图不得直接当生产素材。
- **清单是唯一事实源**：`asset-manifest.json` 记录 id、路径、sha256、类型、来源、provenance（模型/prompt/参考图）、变体、消费者、许可、状态。`scripts/asset_manifest.py` 负责登记与校验（缺文件、hash 不符、临时图残留都会报错）。
- **处理与转换**：尺寸、裁切、透明、压缩、格式、色彩由本机 Pillow 链路完成；`object-fit: cover` 与原生 `CENTER_CROP` 不是同一件事，**焦点与裁切参数必须登记**；px 与 dp/sp 不混用。
- **生图不可用**：明确报告并暂停该环节，可交付完整 prompt 供你在外部真实出图后交回**真实文件**继续；**不静默改用 HTML/SVG 绘图冒充概念图**，也不用占位图冒充已还原。

---

## 能力范围

| 能力 | 交付物 |
|---|---|
| 产品理解与设计目标 | `design-brief.md`（页面地图、目标→问题映射、约束分层、成功标准、非目标、假设） |
| 方向探索 | 提示词预审记录 + 3 张真实概念图 + `concept-prompts.md` + `concept-index.json`（含 sha256） |
| 方向决策 | `direction-approved.md`（逐图合格性、采用/融合/拒绝、目标方案、理由、风险） |
| 高保真原型 | `prototype/index.html`（单页 inline React，库用本地 vendor，真机机身、可点击）、基准截图、设计评审记录、`prototype-notes.md` |
| 素材体系 | `assets/`、`asset-manifest.json`、生成与复用记录 |
| 原生交付 | 原生交付包（结构 / tokens / 状态 / 素材 / 适配 / 无障碍 / 基准图） |
| 原生实现与验收 | 构建与安装日志、真机截图/录屏、落地对照表、`verification-report.md`（工程 + 设计双结论） |

**唯一范围**：iOS / Android 移动应用的界面与交互设计，以及把它落地成原生 App。

**不在范围内**：幻灯片 / PPT / deck、视频 / 动画成片 / 宣传片、配音 / 音频 / 音乐 / SFX、信息图 / 海报 / 封面等静态平面载体、生产级 Web App 与后端系统、纯代码重构、图层级可编辑 PPTX。

---

## 安装

```bash
npx skills add tongsailong/designwise
```

装完先自检（本 skill 不只是 `SKILL.md` 一个文件）：

```bash
python3 scripts/check-skill.py            # 结构 + 引用完整性（exit 0 才算过）
python3 scripts/check-skill.py --strict   # 额外检查未被引用的孤儿文件
```

若安装目录里只有 `SKILL.md`，说明 `skills` CLI 版本过旧（≤1.5.15 有只同步单文件的 bug，已在 1.5.19 修复）：

```bash
npm i -g skills@latest        # 或 npx skills@latest add tongsailong/designwise
```

仍异常就用 `git clone` 兜底：

```bash
git clone https://github.com/tongsailong/designwise.git ~/.claude/skills/designwise
```

### 使用示例

没有按钮、没有面板——只需要一句话：

```
「做个 AI 番茄钟 iOS 原型，4 个核心屏幕要真能点击」
「我们的记账 App 首页太乱，帮我重新设计并给出几个真实方向」
「把这个设计做成 Android 原生界面，装到我的测试机上验一遍」
「给这个页面补一套插画和背景，复用已有的视觉语言」
「真机看一下这版的对比度、字号缩放和空态」
```

---

## 支持平台与依赖

**Agent 支持**：Claude Code · Codex · Cursor · Trae · OpenClaw · Hermes Agent，或任何支持 markdown-based skill 的 agent。能力与载体解耦：文档只规定「这一步需要什么能力」（文件读写 / 本地命令 / 真实生图 / 浏览器渲染 / Copilot 裁决 / 真机取证 / 公开检索），具体工具由 agent 按当前环境映射，见 [`references/runtime-adapters.md`](references/runtime-adapters.md)。

**本地工具链**（按需）：

| 依赖 | 用途 |
|---|---|
| Node.js | `scripts/check-ui.mjs`（结构/溢出/图片/对比度采集，`--shot` 截图，`--ledger-*` 外观账本；无 npm 依赖）、Playwright 浏览器验证 |
| Python 3 | `scripts/zcode_image.py`（真实生图）、`scripts/verify.py`（Playwright 渲染与截图）、`scripts/check-contrast.py`、`scripts/asset_manifest.py`、`scripts/ref_board.py`（参考板，需 Chrome）、`scripts/extract_grid.py` / `contact_sheet.py` / `chroma_key.py`（图片处理）、`scripts/check-skill.py`；Pillow（图片读写，可选但推荐） |
| Playwright + Chromium | HTML 原型真实渲染、点击测试与基准截图 |
| Android SDK / Xcode | 原生构建；真机装包只走宿主授权的安装入口（见 [SECURITY.md](SECURITY.md)） |

**生图凭据**：`ZCODE_CPA_BASE_URL` / `ZCODE_CPA_API_KEY`，或本机 `~/.zcode/v2/provider_config.json`。不随仓库分发，不写入产物。

---

## 项目限制

- **只做 App UI**。要幻灯片、视频、音频、信息图或生产级 Web App，本 skill 不是合适工具。
- **概念图不是 UI 真相**。图中的文字、伪控件、不可实现效果必须按真实产品与平台规范修正，修正点写进 `prototype-notes.md`。
- **机械校验不是设计验收**。脚本全绿只证明没坏；设计质量要真实截图评审，落地要三方真实对照。
- **HTML 原型的 CSS px 不能直接证明 Android 48dp**。dp/sp 必须在原生侧按密度与字体缩放实测。
- **真机证据不可替代**。设备不在线或缺工具链时标 `PARTIAL` / `BLOCKED`，**不写成通过**。
- **完全空白的品牌从零设计，质量会掉**。凭空画 hi-fi 本来就是 last resort。

---

## 仓库结构

```
designwise/
├── SKILL.md                 # agent 执行入口（任务路由唯一权威）
├── README.md                # 中文 README（默认，本文件）
├── README.en.md             # 英文 README
├── SECURITY.md              # 安全与数据流声明
├── THIRD_PARTY_NOTICES.md   # 移植代码的第三方许可全文
├── LICENSE                  # MIT
├── references/              # 方法论细则（按阶段读）
│   ├── app-visual-workflow.md   # 0–7 阶段完整展开
│   ├── image-generation.md      # 生图 prompt 方法与尺寸/质量
│   ├── image-assets.md          # 素材三态、清单格式、复用与溯源
│   ├── design-handoff.md        # 原生交付包与 token 映射
│   ├── app-prototype.md         # HTML 原型规格
│   ├── verification.md          # HTML 与原生证据链
│   ├── product-value.md         # 产品原则
│   ├── critique-guide.md        # 设计评审
│   ├── design-styles.md         # HTML 原生风格库
│   ├── design-research.md       # 参考板与外观账本
│   ├── brand-asset-protocol.md  # 品牌资产 5 步
│   ├── routing-table.md · workflow.md   # 流程速查与展开
│   └── runtime-adapters.md · zcode-host.md  # 宿主能力映射
├── assets/                  # 起手组件与样张
│   ├── ios_frame.jsx · android_frame.jsx · design_canvas.jsx
│   └── style-specimens/     # 风格样张（App / 中文东亚）
├── scripts/                 # 生图 / 处理 / 验证 / 门禁 / 同步
└── demos/                   # 能力演示（中英双版 HTML）
```

> `test-prompts.json` 是**验收提示集**（人工或会话内逐条执行的断言清单），不是自动测试框架；`scripts/check-skill.py` 只校验它存在。

### 维护者：源码仓库与运行时副本

本仓库（git 工作区）是**唯一源码**；agent 的 skills 目录是**运行时副本**，只由 `scripts/sync_runtime.py` 单向写入。不要手工改副本：

```bash
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --check   # 0 = 无漂移
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply   # 写入缺失/不同的文件
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply --prune  # 删除副本多余文件（危险）
```

脚本自动排除 `.env` / `.env.*`（保留 `.env.example`）、`assets/personal-asset-index.json`、`.git`、`node_modules`、`design-demos`、`__pycache__`，以及**开发资产**：根目录 `AGENTS.md`、`scripts/test_*.py` 与 `.zcode/`。**`LICENSE` 始终随副本分发**（MIT 义务，不得排除或删减）。排除对源与副本两侧同时生效，因此排除生效前已存在于副本中的旧开发资产不会被 `--check` 报为漂移、也不会被 `--prune` 删除，需单独清理。详见 [`references/zcode-host.md`](references/zcode-host.md)。

---

## 上游项目与致谢

本项目的视觉方法论与部分资产来自上游：

**[花叔Design · huashu-design](https://github.com/alchaincyf/huashu-design)** — 作者 [@alchaincyf](https://github.com/alchaincyf)（花生 / 花叔），MIT License。

- 上游 Star 趋势：<https://star-history.com/#alchaincyf/huashu-design&Date>
- **样张资产来源**：`assets/style-specimens/` 取自上游同一路径，与本仓库文件字节一致。上游以 MIT License 发布仓库内容，样张是其**原创 HTML/CSS 演绎**（题材与数字虚构）；风格名中的设计师 / 工作室与书名只作**风格参照**，不是其作品的复制，也不代表作者授权或背书。
- **移植代码**：`scripts/extract_grid.py`、`contact_sheet.py`、`chroma_key.py` 移植自 huashu-gpt-image（MIT），copyright 与许可全文见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，各文件头部保留来源声明。

> 上游作者的自我介绍归上游：花生是 AI Native Coder、独立开发者、AI 自媒体博主。

**本分支的差异**（谁做了什么，不混淆）：本分支由本仓库维护者独立维护，在保留上游视觉方法论与风格库的前提下，重构为 **GPT-first 的 App UI 单一标准流程**，并把产品价值判断、素材清单与溯源、原生转译与真机验收纳入同一流程。README 中标注「上游 / 原作者」的内容，其版权与贡献归上游作者。

---

## License

[MIT License](LICENSE)。你可以**自由使用、修改、分发**，**包括商业用途**——公司内部用、客户商单交付、做成付费产品对外卖，都没问题。无需事先授权、无需付费。注明出处不强制，但欢迎。

保留的 MIT 代码与版权声明不得删除或改写：见 `LICENSE` 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。生成的设计素材不自动继承 MIT。
