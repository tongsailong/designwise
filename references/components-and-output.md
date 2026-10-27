# Starter Components · 产出要求 · 水印 · 版本自检

> **ZCode 适配（自 Reasonix 迁移 · 2026-10-24）**：本文件收纳 `SKILL.md` 原「Starter Components」
> 「产出要求」「水印」「版本自检」四节，**内容逐字保留**。迁入 ZCode 时因 SKILL.md 有 100,000 字节
> 读取上限，这四节整体搬到此处，正文留指针。
> **不变的部分**：组件用法、产出命名规范、不加水印的立场、版本自检逻辑全部照原样生效。
> **路径约定**：`assets/`、`scripts/` 均相对本 skill 根目录。

---

## Starter Components（assets/下）

造好的起手组件，直接copy进项目使用：

| 文件 | 何时用 | 提供 |
|------|--------|------|
| `deck_index.html` | **幻灯片的默认基础产物** | **直接复制为 `index.html`、编辑 MANIFEST 即用，不要重写概览逻辑**（三个坑已内建解决）。自带两种自适应概览（网格 iframe 60% / 画廊 40%，画廊需 `thumb` 字段 + 先跑 `scripts/gen_deck_thumbs.mjs`）+ 键盘翻页 + scale + 计数器 + 打印合并。要改先读 `references/slide-decks.md` 三条硬约束 |
| `scripts/gen_deck_thumbs.mjs` | **给无限画廊概览生成缩略图**（网格 iframe 模式不需要）| playwright 截每页 + sharp 降采样 1600px JPEG：`npm i playwright sharp && node gen_deck_thumbs.mjs --slides slides --out thumbs`，再给 MANIFEST 每项加 `thumb`。分辨率别 <1000px 否则 hover 发虚 |
| `deck_stage.js` | 做幻灯片（单文件架构，≤10页） | web component：auto-scale + 键盘导航 + slide counter + localStorage + speaker notes ⚠️ **script 必须放在 `</deck-stage>` 之后，section 的 `display: flex` 必须写到 `.active` 上**，详见 `references/slide-decks.md` 的两个硬约束 |
| `scripts/export_deck_pdf.mjs` | **HTML→PDF 导出（多文件架构）** · 每页独立 HTML 文件，playwright 逐个 `page.pdf()` → pdf-lib 合并。文字保留矢量可搜。依赖 `playwright pdf-lib` |
| `scripts/export_deck_stage_pdf.mjs` | **HTML→PDF 导出（单文件 deck-stage 架构专用）** · 2026-04-20 新增。处理 shadow DOM slot 导致的「只出 1 页」、absolute 子元素溢出等坑。详见 `references/slide-decks.md` 末节。依赖 `playwright` |
| `scripts/export_deck_pptx.mjs` | **HTML→可编辑 PPTX（路线 A：HTML 还没写时用）** · 调 `html2pptx.js` 导出原生可编辑文本框。**HTML 必须符合 4 条硬约束**（见 `references/editable-pptx.md`）。已经写好的视觉稿别硬跑它，改走下面一行。依赖 `playwright pptxgenjs sharp` |
| `scripts/pptx_from_rendered.py` | **HTML→可编辑 PPTX（路线 B：HTML 已写好、或要继承甲方模板）** · 读浏览器渲染后的 `getBoundingClientRect`，视觉驱动的 HTML（flex/居中/裸文字/背景图/SVG）零改造直接转；能以甲方 `.pptx` 为基底继承母版与版式，让他们改母版对全部页面生效（pptxgenjs 做不到）。见 `references/pptx-from-rendered-html.md`。依赖 `playwright python-pptx Pillow` |
| `scripts/html2pptx.js` | **HTML→PPTX 元素级翻译器** · 读 computedStyle 把 DOM 逐元素翻译成 PowerPoint 对象（text frame / shape / picture）。`export_deck_pptx.mjs` 内部调用。要求 HTML 严格满足 4 条硬约束 |
| `design_canvas.jsx` | 并排展示≥2个静态variations | 带label的网格布局 |
| `animations.jsx` | 任何动画HTML | Stage + Sprite + useTime + Easing + interpolate |
| `ios_frame.jsx` | iOS App mockup | iPhone bezel + 状态栏 + 圆角 |
| `android_frame.jsx` | Android App mockup | 设备bezel |
| `macos_window.jsx` | 桌面App mockup | 窗口chrome + 红绿灯 |
| `browser_window.jsx` | 网页在浏览器里的样子 | URL bar + tab bar |
| `cursor.jsx` | 产品UI演示里的光标操作叙事 | macOS光标4形状 + CursorSprite弧线轨迹（Catmull-Rom+收敛手抖）+ ClickRipple双圈解耦 + hover联动 + GSAP/Stage双驱动，帧确定性 |

用法：读取对应 assets 文件内容 → inline 进你的 HTML `<script>` 标签 → slot 进你的设计。

---

## 产出要求

- HTML文件命名描述性：`Landing Page.html`、`iOS Onboarding v2.html`
- 大改版时copy一份旧版保留：`My Design.html` → `My Design v2.html`
- 避免>1000行的大文件，拆成多个JSX文件import进主文件
- 幻灯片、动画等固定尺寸内容，**播放位置**存localStorage——刷新不丢
- HTML放项目目录，不要散落到`~/Downloads`
- 最终产出用浏览器打开检查或用Playwright截图

## 水印（动画产出）

**默认不加任何第三方 Skill 水印。** 动画（HTML 动画 → MP4 / GIF）、幻灯片、信息图、原型、网页的产出，默认都是**干净的成品**，不附加「Created by Huashu-Design」或任何技能 / 工具署名——那是交付污染。

- 仅在用户**明确要求署名**时才加（加用户自己的品牌 / 作者名，或要求标注来源）；模板见 `references/video-export.md` 末节。
- 第三方品牌的非官方致敬作品，加「非官方出品 · 」前缀防 IP 争议——这同样属用户决策，不默认加。
- **版权与许可信息不受影响**：本 skill 自身的署名与 MIT 许可见 `LICENSE` 与 README 致谢一节；产出物版权归用户，不因本条改变。

---

## 版本自检（静默）

本节给 AI agent：每次使用本 skill 前，先做一个不联网的判断——读本 skill 目录（SKILL.md 所在目录）下的 `.last-update-check` 文件（内容为一行日期 YYYY-MM-DD）。文件存在且距今不足 30 天，跳过本节直接干活，不向用户提任何更新相关的话。

到期或文件不存在时，且仅在此时：

1. 本目录不是 git 克隆（无 `.git` 或无任何 remote）→ 写入今天日期后跳过本节
2. 对比版本：`git -C <本目录> rev-parse HEAD` 与**上游** HEAD——
   - 存在 `upstream` remote（本仓库是 fork，属于这种情况）→ `git -C <本目录> ls-remote upstream HEAD`
   - 无 `upstream` → `git -C <本目录> ls-remote origin HEAD`
3. 无论结果如何，把今天日期写入 `.last-update-check`
4. 两者一致 → 什么都不说；确认落后 → 先完成用户当前任务，结束后附一句「上游有更新，可用 `git -C <本目录> fetch upstream && git -C <本目录> merge upstream/master` 同步（本分支有本地二次开发提交，可能需处理冲突）」。是否更新由用户决定，不要主动执行更新
