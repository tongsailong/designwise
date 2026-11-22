# 核心资产协议（完整版）

> 2026-06 从 SKILL.md 下沉的完整协议：5 步详细操作、下载命令、brand-spec 模板、全流程失败兜底、反例与代价对比。SKILL.md 只保留首层规则（具名产品必须取官方 logo、生成图不得冒充真实资产）。
> 触发：任务涉及具体品牌/产品时强制执行；入口见 `references/routing-table.md` §3.1。

#### 1. 核心资产协议（涉及具体品牌时强制执行）

> **这是核心约束，也是稳定性的生命线。** Agent 是否走通这个协议，直接决定输出质量是 40 分还是 90 分。不要跳过任何一步。
>
> **协议重构说明**：从「品牌资产协议」升级为「核心资产协议」。早期版本过度聚焦色值和字体，漏掉了设计中最基础的 logo / 产品图 / UI 截图。花叔的原话：「除了所谓的品牌色，显然我们应该找到并且用上大疆的 logo，用上 pocket4 的产品图。如果是网站或者 app 等非实体产品的话，logo 至少该是必须的。这可能是比所谓的品牌设计的 spec 更重要的基本逻辑。否则，我们在表达什么呢？」

**触发条件**：任务涉及具体品牌——用户提了产品名/公司名/明确客户（Stripe、Linear、Anthropic、Notion、Lovart、DJI、自家公司等），不论用户是否主动提供了品牌资料。

**前置硬条件**：走协议前必须已通过「#0 事实验证先于假设」确认品牌/产品存在且状态已知。如果你还不确定产品是否已发布/规格/版本，先回去搜。

##### 核心理念：资产 > 规范

**品牌的本质是「它被认出来」**。认出来靠什么？按识别度排序：

| 资产类型 | 识别度贡献 | 必需性 |
|---|---|---|
| **Logo** | 最高 · 任何品牌出现 logo 就一眼识别 | **任何品牌都必须有** |
| **产品图/产品渲染图** | 极高 · 实体产品的"主角"就是产品本身 | **实体产品（硬件/包装/消费品）必须有** |
| **UI 截图/界面素材** | 极高 · 数字产品的"主角"是它的界面 | **数字产品（App/网站/SaaS）必须有** |
| **色值** | 中 · 辅助识别，脱离前三项时经常撞衫 | 辅助 |
| **字体** | 低 · 需配合前述才能建立识别 | 辅助 |
| **气质关键词** | 低 · agent 自检用 | 辅助 |

**翻译成执行规则**：
- 只抽色值 + 字体、不找 logo / 产品图 / UI → **违反本协议**
- 用 CSS 剪影/SVG 手画替代真实产品图 → **违反本协议**（生成的就是「通用科技动画」，任何品牌都长一样）
- 找不到资产不告诉用户、也不 AI 生成，硬做 → **违反本协议**
- 宁可停下问用户要素材，也不要用 generic 填充

##### 5 步硬流程（每步有 fallback，绝不静默跳过）

##### Step 1 · 问（资产清单一次问全）

不要只问「有 brand guidelines 吗？」——太宽泛，用户不知道该给什么。按清单逐项问：

```
关于 <brand/product>，你手上有以下哪些资料？我按优先级列：
1. Logo（SVG / 高清 PNG）—— 任何品牌必备
2. 产品图 / 官方渲染图 —— 实体产品必备（如 DJI Pocket 4 的产品照）
3. UI 截图 / 界面素材 —— 数字产品必备（如 App 主要页面截图）
4. 色值清单（HEX / RGB / 品牌色盘）
5. 字体清单（Display / Body）
6. Brand guidelines PDF / Figma design system / 品牌官网链接

有的直接发我，没有的我去搜/抓/生成。
```

##### Step 2 · 搜官方渠道（按资产类型）

| 资产 | 搜索路径 |
|---|---|
| **Logo** | `<brand>.com/brand` · `<brand>.com/press` · `<brand>.com/press-kit` · `brand.<brand>.com` · 官网 header 的 inline SVG |
| **产品图/渲染图** | `<brand>.com/<product>` 产品详情页 hero image + gallery · 官方新闻稿附图 |
| **UI 截图** | App Store / Google Play 产品页截图 · 官网 screenshots section |
| **色值** | 官网 inline CSS / Tailwind config / brand guidelines PDF |
| **字体** | 官网 `<link rel="stylesheet">` 引用 · Google Fonts 追踪 · brand guidelines |

`WebSearch` 兜底关键词：
- Logo 找不到 → `<brand> logo download SVG`、`<brand> press kit`
- 产品图找不到 → `<brand> <product> official renders`、`<brand> <product> product photography`
- UI 找不到 → `<brand> app screenshots`、`<brand> dashboard UI`

##### Step 3 · 下载资产 · 按类型三条兜底路径

**3.1 Logo（任何品牌必需）**

> ⚠️ **别只试 `curl <brand>.com/logo.svg` 就放弃**——现在的官网大多是 SPA，直连静态路径基本返回空壳 HTML（2026-06-06 实测 Trae 官网 5 条直连路径全是空壳）。**数字产品 / SaaS / AI 工具优先用图标聚合源**，命中率最高、直出干净 SVG。

按成功率递减：
0. **图标聚合源（知名数字产品/SaaS/AI 工具首选，命中率最高）**：
   ```bash
   unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy   # 清代理，否则 TLS 易炸
   # svgl —— AI/开发者品牌覆盖最全（Claude/Cursor/OpenAI/Copilot/Anthropic/Vercel…），含 light/dark + wordmark
   curl -s "https://api.svgl.app?search=<brand>"   # 返回 JSON，取 route(.light/.dark) 的 svg URL 再下载
   # simpleicons —— 单色 glyph，可直接按品牌色上色
   curl -o logo.svg "https://cdn.simpleicons.org/<slug>/<hexcolor>"
   ```
1. 独立 SVG/PNG 文件 / 官方 brand 页（如 `<brand>.com/brand`、`/press`）：
   ```bash
   curl -A "Mozilla/5.0" -L -o assets/<brand>-brand/logo.svg "<official-logo-url>"
   ```
2. 官网 HTML 全文提取 inline SVG：
   ```bash
   curl -A "Mozilla/5.0" -L https://<brand>.com -o assets/<brand>-brand/homepage.html
   # 然后 grep <svg>...</svg> 提取 logo 节点
   ```
3. **Google favicon 服务（站点真实 mark 兜底，几乎不失败）**：
   ```bash
   curl -o logo.png "https://www.google.com/s2/favicons?domain=<brand-domain>&sz=256"   # 256px 官方站点图标
   ```
4. 官方社交媒体 avatar（最后手段）：GitHub/Twitter/LinkedIn 的公司头像通常是 400×400 或 800×800 透明底 PNG

下载后**逐个核对**：`file <logo>` 确认是真 SVG/PNG（不是 106 字节占位或 HTML 空壳），`head -c 90 <logo.svg>` 看是否 `<svg`。

**3.2 产品图/渲染图（实体产品必需）**

按优先级：
1. **官方产品页 hero image**（最高优先级）：右键查看图片地址 / curl 获取。分辨率通常 2000px+
2. **官方 press kit**：`<brand>.com/press` 常有高清产品图下载
3. **Wikimedia Commons**：公共领域常有
4. **AI 变体兜底**：仅在宿主已授权生图链路可用时，以真实产品图为参考生成变体；**不要用 CSS/SVG 手画代替**

```bash
# 示例：下载产品 hero image
curl -A "Mozilla/5.0" -L "<hero-image-url>" -o assets/<brand>-brand/product-hero.png
```

**3.3 UI 截图（数字产品必需）**

- App Store / Google Play 的产品截图（注意：可能是 mockup 而非真实 UI，要对比）
- 官网 screenshots section
- 产品官方 Twitter/X 的发布截图（常是最新版本）
- 用户有账号时，直接截屏真实产品界面

**3.4 · 素材质量门槛（按需，不设固定搜索轮次）**

> **Logo 的规则不同于其他素材**：Logo 有就必须用（没有就问用户）；其他素材（产品图 / UI / 配图）按下面的门槛筛，不凑数量。

| 标准 | 做法 |
|---|---|
| **官方来源优先** | 官方产品页 / press kit / 官方社媒 > Wikimedia / 公共领域 > 免费素材；疑似盗图不用 |
| **够用即止** | 同类素材有 1–2 个合格的就够；不为了「有得选」批量抓取 |
| **分辨率与版权清楚** | 产品图 ≥2000px；UI 截图是新版本且无用户数据；来源可记 |
| **气质一致** | 放在一起不打架，能服务同一叙事角色 |
| **不合格就诚实占位** | 用灰块 + 文字标签并标注「待补」，或按授权用 AI 以官方图为参考生成变体；**不拿 6 分素材凑数** |

**Logo 例外**：有就必须用——logo 不是「多选一」问题，而是识别度根基。

##### Step 4 · 验证 + 提取（不只是 grep 色值）

| 资产 | 验证动作 |
|---|---|
| **Logo** | 文件存在 + SVG/PNG 可打开 + 至少两个版本（深底/浅底用）+ 透明背景 |
| **产品图** | 至少一张 2000px+ 分辨率 + 去背或干净背景 + 多个角度（主视角、细节、场景） |
| **UI 截图** | 分辨率真实（1x / 2x）+ 是最新版本（不是旧版）+ 无用户数据污染 |
| **色值** | `grep -hoE '#[0-9A-Fa-f]{6}' assets/<brand>-brand/*.{svg,html,css} \| sort \| uniq -c \| sort -rn \| head -20`，过滤黑白灰 |

**警惕示范品牌污染**：产品截图里常有用户 demo 的品牌色（如某工具截图演示喜茶红），那不是该工具的色。**同时出现两种强色时必须区分**。

**品牌多切面**：同一品牌的官网营销色和产品 UI 色经常不同（Lovart 官网暖米+橙，产品 UI 是 Charcoal + Lime）。**两套都是真的**——根据交付场景选合适的切面。

##### Step 5 · 固化为 `brand-spec.md` 文件（模板必须覆盖所有资产）

```markdown
# <Brand> · Brand Spec
> 采集日期：YYYY-MM-DD
> 资产来源：<列出下载来源>
> 资产完整度：<完整 / 部分 / 推断>

## 🎯 核心资产（一等公民）

### Logo
- 主版本：`assets/<brand>-brand/logo.svg`
- 浅底反色版：`assets/<brand>-brand/logo-white.svg`
- 使用场景：<启动页 / 关于页 / 全局>（App 内不加水印，见 `components-and-output.md` §3）
- 禁用变形：<不能拉伸/改色/加描边>

### 产品图（实体产品必填）
- 主视角：`assets/<brand>-brand/product-hero.png`（2000×1500）
- 细节图：`assets/<brand>-brand/product-detail-1.png` / `product-detail-2.png`
- 场景图：`assets/<brand>-brand/product-scene.png`
- 使用场景：<特写/旋转/对比>

### UI 截图（数字产品必填）
- 主页：`assets/<brand>-brand/ui-home.png`
- 核心功能：`assets/<brand>-brand/ui-feature-<name>.png`
- 使用场景：<产品展示/Dashboard 渐现/对比演示>

## 🎨 辅助资产

### 色板
- Primary: #XXXXXX  <来源标注>
- Background: #XXXXXX
- Ink: #XXXXXX
- Accent: #XXXXXX
- 禁用色: <品牌明确不用的色系>

### 字型
- Display: <font stack>
- Body: <font stack>
- Mono（数据 HUD 用）: <font stack>

### 签名细节
- <哪些细节是「120% 做到」的>

### 禁区
- <明确不能做的：比如 Lovart 不用蓝色、Stripe 不用低饱和暖色>

### 气质关键词
- <3-5 个形容词>
```

**写完 spec 后的执行纪律（硬要求）**：
- 所有 HTML 必须**引用** `brand-spec.md` 里的资产文件路径，不允许用 CSS 剪影/SVG 手画代替
- Logo 作为 `<img>` 引用真实文件，不重画
- 产品图作为 `<img>` 引用真实文件，不用 CSS 剪影代替
- CSS 变量从 spec 注入：`:root { --brand-primary: ...; }`，HTML 只用 `var(--brand-*)`
- 这让品牌一致性从「靠自觉」变成「靠结构」——想临时加色要先改 spec

##### 全流程失败的兜底

按资产类型分别处理：

| 缺失 | 处理 |
|---|---|
| **Logo 完全找不到** | **停下问用户**，不要硬做（logo 是品牌识别度的根基） |
| **产品图（实体产品）找不到** | 按授权用生图链路以官方参考图为基底生成 → 向用户索取 → 最后才是诚实 placeholder（灰块+文字标签，明确标注"产品图待补"） |
| **UI 截图（数字产品）找不到** | 向用户索取自己账号的截屏 → 官方公开截图。不用 mockup 生成器凑 |
| **色值完全找不到** | 有既有 design system → 停下确认既有 token 或按现有 spec 取色；**没有既有体系 → 按设计方向顾问模式出自己的最佳方案，写进 `design-brief.md` 的可探索约束，并在方向图里体现**（方向数量与流程见 `SKILL.md` 与 `direction-strategy.md`，按实质分歧决定，不固定三个） |

**禁止**：找不到资产就静默用 CSS 剪影/通用渐变硬做——这是协议最大的反 pattern。**宁可停下问，也不要凑**。

##### 反例（真实踩过的坑）

- **Kimi 动画**：凭记忆猜「应该是橙色」，实际 Kimi 是 `#1783FF` 蓝色——返工一遍
- **Lovart 设计**：把产品截图里演示品牌的喜茶红当成 Lovart 自己的色——差点毁整个设计
- **DJI Pocket 4 发布物料（2026-04-20，触发本协议升级的真实案例）**：走了旧版只抽色值的协议，没下载 DJI logo、没找 Pocket 4 产品图，用 CSS 剪影代替产品——做出来是「通用黑底+橙 accent」的物料，没有大疆识别度。→ 协议升级为「资产 > 规范」。
- 抽完色没写进 brand-spec.md，第三页就忘了主色数值，临场加了个「接近但不是」的 hex——品牌一致性崩溃
- **多产品对比页（2026-06-06）**：只抽了五家品牌色，**五个产品 logo 一个没取**。根因：把「对比 / 榜单页」误判为不触发协议，且 Fallback 路径没有 logo 检查点。→ 修复：设计里点名/并列的真实产品，logo 一律取；Fallback 不豁免。

##### 协议代价 vs 不做代价

资产协议按需执行，不做固定时长要求；一次取对 logo、UI 截图与色值，比返工便宜一个数量级。

