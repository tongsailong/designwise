# References 路由表（完整版）

> **ZCode 适配（自 Reasonix 迁移 · 2026-10-24）**：本文件是 `SKILL.md` 原「## References路由表」一节的**逐字完整版**。
> 它会从 ZCode 迁入时被完整保留；`SKILL.md` 正文只保留压缩后的导航表（因 ZCode 读取 SKILL.md 有
> 100,000 字节上限，超限会静默截断尾部）。
> **何时读本文件**：正文压缩表找不到对应任务、或需要该行的完整约束描述时。
> **路径约定**：下表里所有 `references/xxx.md`、`assets/xxx`、`scripts/xxx` 均相对本 skill 根目录。

> **任务分层优先（2026-10-29）**：**L2** 默认走 GPT 视觉概念通路；HTML fallback 仅限 `SKILL.md`「L2 的候选形态」列出的三种例外；**L1** 直接改现有 UI，按 `SKILL.md`「L1 四步流程」执行（理解现状 → 直接修改 → 针对性验证 → 交付），**不进入设计方向顾问 Phase 1-5**、不套三方向门、概念图或 Gate 1；**L3** 走各自专业工作流。任务路由以 `SKILL.md`「任务路由」与「任务分层」为准，本表只负责 references 入口。

## 工具路由（与全局 `AGENTS.md` §5《委派与独立复核》一致）

1. **常规独立编码、修复、测试** → 默认由 **ZCode 主控使用原生工具直接完成**；只有确实可拆分、并行有收益时才派原生子智能体。
2. **用户明确要求的独立复核，以及全局风险分档触发的复核** → 使用 **ZCode 原生子智能体的独立上下文**（只读）。
3. **DesignWise Gate 1 / Gate 2 视觉评审** → 默认 **原生视觉自检**（主模型直接读真实图片，结论标注「自检」）；**用户明确授权 GPT 评审通道后**才可用 `scripts/zcode_vision.py --confirm-gpt-review`（直连 CPA、只收真实图片；不是 copilot 正式 REVIEW）。未授权时不得用它绕过 Copilot 的启用限制。
4. **Copilot 正式 REVIEW** → 仅在用户**明确点名 Copilot** / **明确要求使用 `copilot` Skill** / **明确要求正式 REVIEW** 时调用；任务复杂度、风险高低、是否需要独立复核、其他通道是否可用，均不构成授权。
5. **普通第二视角、并行探索、一般协作** → 遵循全局规则，用原生子智能体，**不强制**走独立复核通道。
6. **用户明确指定其他工具** → 遵循用户指定。
7. **Pi 已卸载（2026-10-27）** → 无 Pi 路由。

## 路由表（原文完整表）

根据任务类型深入读对应references：

| 任务 | 读 |
|------|-----|
| 开工前问问题、定方向 | `references/workflow.md` |
| 🎨 **GPT 视觉概念生图**（阶段 2 · **L2 默认前置**：Visual Brief（含约束分层）/ 能力探测 / **生成范围与成本控制 §1.5** / 多方向与英文 prompt 自动生成（图标 §2.3.1）/ **提示词专家评审 §2.6（生图前，不决定方向）** / 🔴 **Gate 1 视觉方向评审 §2.6.1（真实候选图之后；默认原生自检，授权后才用 `zcode_vision --confirm-gpt-review`；Copilot 仅点名）** / **候选方向的取舍与用户选定 §2.7** / **收敛型最终提示词与决策记录 §2.8（用户选定后）** / **用户介入边界 §2.9** / **生成结果质量自检 §2.4** / **禁止静默回退为代码绘图**）→ **第一次评审：真实图专家评审 + 用户确认方向**（阶段 3）→ **概念图→视觉规范转译 §3.5** → **按需单套 HTML 原型 §3.6**（**图片素材规则 §3.6.3** / 素材三态 §3.6.4）→ **第二次评审与定向迭代 §3.7** → **验证素材处置 §5.1** / **正式图片素材 §4.6** / **开发期按需生成 §4.7** → 验证闭环 §6.2 / 费用治理 / 降级 | `references/gpt-visual-workflow.md` |
| 📦 **设计交付契约**（DesignWise → **Web / Android / PPT**：七件套 = 页面结构 / 设计 token / 状态与交互 / 真实文案与数据 / 素材清单 / 适配与无障碍 / 验收基准图；三平台共用一套 + 平台适配层；含交付包自检、红线、**§8 真实实现反馈闭环**） | `references/design-handoff.md` |
| ⭐ **产品价值判断**（产品界面/交互原型：谁在用·核心行为·关键取舍·易用性；含「要不要用」的适用边界判定） | `references/product-value.md` |
| **App/iOS 原型完整守则**（架构表/取图代码/AppPhone骨架/ios_frame用法） | `references/app-prototype.md` |
| 反AI slop、内容规范、scale | `references/content-guidelines.md` |
| 字体排印/字体配对/中文排印 | `references/typography.md` |
| React+Babel项目setup | `references/react-setup.md` |
| 做幻灯片 | `references/slide-decks.md` + `assets/deck_index.html`（默认多文件概览墙）+ `scripts/gen_deck_thumbs.mjs`（画廊缩略图）+ `assets/deck_stage.js`（仅 ≤10 页单文件） |
| 导出可编辑 PPTX · 路线 A（HTML 还没写，按 4 条硬约束写） | `references/editable-pptx.md` + `scripts/html2pptx.js` |
| 导出可编辑 PPTX · 路线 B（**HTML 已写好的视觉稿**、**甲方要求用他们的模板**、或 A 转不出来） | `references/pptx-from-rendered-html.md` + `scripts/pptx_from_rendered.py` |
| **验证 PPTX/渲染产物时「先验证验证工具」** | `references/pptx-from-rendered-html.md` 的「验证」节 + `references/verification.md` |
| 做动画/motion（**先读 pitfalls**）| `references/animation-pitfalls.md` + `references/animations.md` + `assets/animations.jsx` |
| ⭐ **动画分镜/画面构图**（任何动画开工前；每一镜先是一张会动的封面：定格帧十一律+景别体系+能量骨架+轻量分镜卡） | `references/storyboard-basics.md`（launch-film 导演稿是它的重装版） |
| ⭐ **镜头语言/运镜**（zoom/pan/orbit/parallax/转场；预算制+镜间语法+PageCam 相机数学+CSS zoom 栅格化） | `references/camera-language.md`（设计判断）+ `gsap-recipes.md` §9 Camera Rig（实现） |
| ⭐ **产品UI展示动画**（画面主角是一个界面：截图vs重建决策树+UI展示八式+typing+光标+3D巡览） | `references/ui-demo-animation.md` + `assets/cursor.jsx` |
| **HyperFrames 渲染后端**（新动画默认；选型边界/合成契约/老demo迁移/check流程） | `references/hyperframes-backend.md` |
| **设计语言的 GSAP 实现配方**（easing 映射/运动语言8条/五段叙事骨架/seek 安全规则） | `references/gsap-recipes.md` |
| **动画的正向设计语法**（Anthropic 级叙事/运动/节奏/表达风格）| `references/animation-best-practices.md`（5 段叙事+Expo easing+运动语言 8 条+3 种场景配方）|
| **带解说的长动画 / 长概念视频**（5-20 分钟带配音、解说驱动画面、TTS 实测时长生成 timeline）| `references/voiceover-pipeline.md`（铁律：连续运动叙事、禁 PowerPoint 切换）+ `assets/narration_stage.jsx` + `scripts/cloud/tts-doubao.mjs`（可选云TTS，自备key，见SECURITY.md）+ `scripts/narrate-pipeline.mjs` + `scripts/{mix-voiceover,render-narration}.sh` |
| 做Tweaks实时调参 | `references/tweaks-system.md` |
| 没有design context怎么办 | `references/design-context.md`（薄 fallback） 或 `references/design-styles.md`（厚 fallback：HTML 原生 60 种风格库，网页 20+PPT 20+信息图 20，按温度分级） |
| **需求模糊要推荐风格方向** | `references/design-styles.md`（60 种 HTML 原生风格库，含还原度/温度/开源字体）+ `assets/showcases/INDEX.md`（预制截图画廊） |
| **按输出类型查场景模板**（封面/PPT/信息图） | `references/scene-templates.md` |
| 输出完后验证 | `references/verification.md` + `scripts/verify.py`（渲染/控制台）+ `scripts/check-ui.mjs`（触控 / 字号 / 溢出 / 控制台采集；输出 CSS px，不等同 Android dp）+ `scripts/check-contrast.py`（对比度三档机械校验）+ `scripts/check-assets.py`（素材清单可追踪/可复现/可引用） |
| **设计评审/打分**（设计完成后可选；**含生图前的提示词专家评审**） | `references/critique-guide.md`（**概念/立意（第 0 位，权重最高）+ 5 维度评分** + 常见问题清单；+产品界面类「用户价值与易用性」、+有 spec 时「Spec 一致性与范围核验」、+GPT 通路「视觉还原检查」、+**生图前「Prompt 级创意评审」**（文字可判 / 不可判边界，**不决定视觉方向**）四项附加检查）。🔴 **视觉方向判断与阶段门槛默认由原生自检承担；外部 GPT 仅用户授权后**（Gate 1 / Gate 2，见「视觉评审门」大节；**Copilot 正式 REVIEW 仅用户点名**）——本行是 DesignWise 自主的专家评审，两者职责不同、不互相替代 |
| **动画导出MP4/GIF/加BGM** | `references/video-export.md` + `scripts/render-video.js`（默认25fps）/ `scripts/render-video-seek.js`（真60fps·确定性·无黑帧，走Stage时钟时用）+ `scripts/convert-formats.sh` + `scripts/add-music.sh` |
| **动画加音效SFX**（苹果发布会级，37个预制） | `references/sfx-library.md` + `assets/sfx/<category>/*.mp3` |
| **动画音频配置规则**（SFX+BGM双轨制、黄金配比、ffmpeg模板、场景配方） | `references/audio-design-rules.md` |
| **Apple画廊展示风格**（3D倾斜+悬浮卡片+缓慢pan+焦点切换，v9实战同款） | `references/apple-gallery-showcase.md` |
| **Gallery Ripple + Multi-Focus 场景哲学**（当素材 20+ 同质+场景需表达「规模×深度」时优先用；含前置条件、技术配方、5 个可复用模式）| `references/hero-animation-case-study.md`（huashu-design hero v9 蒸馏）|
| ⭐ **Launch Film 工作流**（30 秒级品牌宣传片 / launch trailer / superbowl-tier ad / Apple 级别预期）：先写**万字 director's notes** 再做动画。含 5 大部分结构 + 触发判断 + 多视角并行策略 + 关键帧验证流程 | `references/launch-film-director-notes.md`（huashu-md-html v2.0 launch film 蒸馏）|
| ⭐ **多视角并行实验**（用户说「再做几个版本」「想看不同方向」/ 多平台分发 / 客户拍不了板）：6 位艺术家视角同时启动 subagent 各做独立版本 + 完成后 5 维度审校 | `references/multi-perspective-parallel-case-study.md`（huashu-md-html v2.0 6 视角实战）|
| ⚠️ **不确定当前环境有没有某能力**（网络检索 / 子代理 / 截图 / 命令执行 → 用什么载体顶上） | `references/runtime-adapters.md`（能力映射，平台无关） |
