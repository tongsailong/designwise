# Content Guidelines：反AI slop、内容准则、Scale规范

AI设计里最容易掉进去的陷阱。这是一份「不做什么」的清单，比「做什么」更重要——因为AI slop是默认值，你不主动避免就会发生。

## AI Slop 完整黑名单

### 视觉陷阱

**❌ 激进渐变背景**
- 紫色 → 粉色 → 蓝色 全屏渐变（AI生成网页的典型味道）
- 任何方向的rainbow gradient
- Mesh gradient铺满背景
- ✅ 如果要用渐变：subtle、单色系、有意图地点缀（比如button hover）

**❌ 圆角卡片 + 左border accent色**
```css
/* 这是AI味卡片的典型签名 */
.card {
  border-radius: 12px;
  border-left: 4px solid #3b82f6;
  padding: 16px;
}
```
这种卡片在AI生成的Dashboard里泛滥。想做强调？用更有设计感的方式：背景色对比、字重/字号对比、plain分隔线、或者干脆不分卡片。

**❌ Emoji 装饰**
除非品牌本身使用emoji（比如Notion、Slack），否则不要在UI上放emoji。**尤其不要**：
- 标题前的 🚀 ⚡️ ✨ 🎯 💡
- Feature列表的 ✅
- CTA按钮里的 →（箭头单独出现OK，emoji箭头不行）

没图标用真icon库（Lucide/Heroicons/Phosphor），或者用placeholder。

**❌ SVG 画 imagery**
不要试图用SVG画：人物、场景、设备、物品、抽象艺术。AI画的SVG imagery一眼就是AI味，幼稚且廉价。**一个灰色矩形+"插画位 1200×800"的文字标签，比一个拙劣的SVG hero illustration强100倍**。

唯一可以用SVG的场景：
- 真正的icon（16×16到32×32级别）
- 几何图形做装饰元素
- Data viz的chart

**❌ 过多iconography**
不是每个标题/feature/section都需要icon。滥用icon会让界面像toy。Less is more。

**❌ "Data slop"**
编造的stats装饰：
- "10,000+ happy customers" （你都不知道有没有）
- "99.9% uptime" （没有真数据就别写）
- 用图标+数字+词组成的装饰"metric cards"
- Mock table里的假数据装点得花里胡哨

如果没真数据，留placeholder或问用户要。

**❌ "Quote slop"**
编造的用户评价、名人名言装饰页面。留placeholder问用户要真quote。

### 字体陷阱

**❌ 避免这些烂大街字体**：
- Inter（AI生成的网页默认）
- Roboto
- Arial / Helvetica
- 纯system font stack
- Fraunces（AI发现了这个就用滥了）
- Space Grotesk（最近AI的最爱）

**✅ 用有特点的display+body配对**。灵感方向：
- 衬线display + 无衬线body（editorial feel）
- Mono display + sans body（technical feel）
- Heavy display + light body（contrast）
- Variable font做hero的粗细动画

字体资源：
- Google Fonts的冷门好选项（Instrument Serif、Cormorant、Bricolage Grotesque、JetBrains Mono）
- 开源字体站（Fraunces的兄弟字体、Adobe Fonts）
- 不要凭空发明字体名

### 色彩陷阱

**❌ 凭空发明颜色**
不要从头设计一整套不熟悉的色彩。这通常不和谐。

**✅ 策略**：
1. 有品牌色 → 用品牌色，缺的 color token 按同一色相推导
2. 没有品牌色但有参考 → 从参考产品截图吸色
3. 完全从零 → 用平台语义色板（Material 3 tonal / iOS system colors）或一个已验证的开源色板，不逐个手调

色彩在原型里用语义 token（`ui_background` / `surface` / `on_surface` / `primary` / `on_primary`），不把 `white`/`black` 当语义色——深色模式会反色（`design-handoff.md` ③）。

**❌ 夜间模式随手加反色**
不是简单invert颜色。好的dark mode需要重新调整饱和度、对比度、accent色。不想做dark mode就别做。

## 内容准则

### 1. Don't add filler content

每个元素都必须earn its place。空白是设计问题，用**构图**解决（对比、节奏、留白），**不是**靠内容填满。

**判断filler的问题**：
- 如果去掉这段内容，设计会变差吗？答案若是"不会"，就去掉。
- 这个元素解决了什么真问题？如果是"让页面不那么空"，删掉。
- 这个stats/quote/feature有真数据支持吗？没有就不要凭空写。

「One thousand no's for every yes」。

### 2. 加内容属于范围变化

多加一页/一个区块/一个功能不是设计自由度，是**范围漂移**：先说明它服务哪个真实目标，需要用户拍板时才问；用户没要求的默认不加（`SKILL.md` §0 范围冻结）。

### 3. Create a system up front

探索完 design context 后，**把设计系统写进 `design-brief.md`** 的视觉定位与 token 计划，不停轮等确认：

```markdown
设计系统（写入 brief，随方向一起验证）：
- 色彩：语义 token（背景 / 表面 / 主色 / on_*），来自品牌或平台色板
- 字型：display + body 配对，中文按平台字体栈
- 层级：app bar / 内容区 / 底部导航的密度与间距节奏
- 图像：按资产计划（槽位、职责、来源），不用占位图冒充完成
- 表面：材质语言 ≤2 种，层级不超过必要层数
```

不停轮不等于不沟通：方向阶段用真实概念图与 `direction-approved.md` 呈现判断；只有**业务规则冲突、范围变化、授权边界、关键业务取舍**需要用户拍板（`workflow.md` §3）。

## Scale 规范

### App（iOS / Android）

- 正文基准 **15–17pt/sp**（iOS body 17pt，Android body 14–16sp）；**任何产品文本 ≥12**，正文 ≥14。低于 12 只允许出现在设备外框等非产品文本，并用 `--font-ignore` 排除；不存在「辅助标注可以 11px」的口子（见 `verification.md` §1）
- 标题按层级 20 / 28 / 34+；大标题不要再叠加多重装饰
- 触控目标：Android **≥48dp**，iOS **≥44pt**；图标视觉尺寸小不代表触控区小
- 行高：iOS 约 1.2–1.4 倍字号；中文正文 1.6–1.8
- 字体缩放：系统放大到 1.3 及更大档时不得截断、重叠、遮挡（见 `references/design-handoff.md` ⑥）

### 规范单位

| 平台 | 字号 | 间距 | 触控 |
|---|---|---|---|
| Android | `sp` | `dp`（4/8 栅格） | ≥48dp |
| iOS | `pt`（Dynamic Type） | `pt` | ≥44pt |
| HTML 原型 | CSS px（按 1x 设计基准） | px | iOS ≥44px；Android ≥48px（与目标平台一致） |

### 对比度（三档判定 · 不得混为一谈）

先判定元素**属于哪一档**，再套对应门槛——把承载信息的图形当装饰放行，是「不合格设计混进交付」最常见的口子。

| 档位 | 包含什么 | 门槛（WCAG AA） | 不合格怎么办 |
|---|---|---|---|
| **① 正文文字** | 正文、标签、数值、按钮文字、任何要读的字 | 正常字号 **≥4.5:1**；大字（≥24px，或 ≥18.66px 且加粗）**≥3:1** | 🔴 **阻断交付**，必须改前景或背景色 |
| **② 重要图标 / 图形** | 承载信息的图标、进度条、图表线、状态指示、输入框边界、分割信息的线 | **≥3:1**（WCAG 1.4.11 非文本对比） | 🔴 **阻断交付**（信息会丢失）；若该图形**纯属装饰、删掉不损信息**，可改判为档 ③ |
| **③ 纯装饰元素** | 氛围装饰、非信息性纹理、已被文字重复表达的点缀 | 无硬门槛 | 允许低对比，但**必须在交付包显式标注为「装饰·不承载信息」** |

**计算与核验**：用 WCAG 相对亮度公式算比值（`(L1+0.05)/(L2+0.05)`），别凭肉眼；Chrome DevTools 的 accessibility 面板可直接读。**每对前景/背景都要留实测值**——存在交付包（见 `design-handoff.md` ⑥），不靠「看着还行」。

**典型陷阱**：品牌金/橙等暖色在白底上常在 2–3:1（如 `#C8A44D` on `#FFFDF8` ≈ 2.33:1）——**只能当档 ② 图形/描边，绝不能当档 ① 正文**；金色小字一律换深色版。

## 原型里的 CSS 边界

HTML 原型可以用现代 CSS（`text-wrap`、container queries、`color-mix`、`@view-transition` 等），但**它是移动端原型的表现手段，不是桌面网页设计**：

- 用单列/移动断点布局；不引入 sidebar、桌面 Dashboard 网格、hover 才出现的操作。
- 设备外框与系统栏只用 `assets/ios_frame.jsx` / `assets/android_frame.jsx`，不手写。
- CSS px 只用于原型；原生落地按 dp/pt 与平台 token 重述（`SKILL.md` 阶段 5）。
- 动效必须可中断、尊重 `prefers-reduced-motion`，并跑 `scripts/check-motion.py`。

## 决策速查：当你犹豫时

- 想加个渐变？→ 大概率不加
- 想加个emoji？→ 不加
- 想给卡片加圆角+border-left accent？→ 不加，换其他方式
- 想用SVG画个hero插画？→ 不画，用placeholder
- 想加一段quote装饰？→ 先问用户有没有真quote
- 想加一排icon features？→ 先问要不要icon，可能不需要
- 用Inter？→ 换一个更有特点的
- 用紫色渐变？→ 换一个有根据的配色

**当你觉得"加一下会更好看"的时候——那通常是AI slop的征兆**。先做最简的版本，只在用户要求时加。


---

## 附录：反AI slop速查（补充项）

> 2026-10-27 从 SKILL.md 移入，内容逐字保留；入口见 `SKILL.md` §5 设计质量红线。

完整的反 slop 规则在本文件「AI Slop 完整黑名单」（视觉 / 字体 / 色彩），字体配对逻辑见 `references/typography.md`。以下只列黑名单没覆盖的补充项：

| 类别 | 避免 | 采用 |
|------|------|------|
| 图标 | **装饰性** icon 每处都配（撞 slop）| **承载差异化信息**的密度元素必须保留——不要把产品特色也一并减掉 |
| 填充 | 编造stats/quotes装饰 | 留白，或问用户要真内容 |
| 动画 | 散落的微交互、每次点击都弹一下 | 一次有编排的页面进入 + 必要的状态反馈；尊重 `prefers-reduced-motion` |
| 动效落地 | 只在 HTML 里成立、原生实现不了或太贵的效果 | 用原生可达的转场/缓动重述；写进 `design-handoff.md` 的动效规格 |
