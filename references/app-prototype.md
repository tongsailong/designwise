# App 原型专属守则（iOS / Android）· 完整操作手册

> 从 SKILL.md 下沉的完整版：架构选型、取图渠道与代码、AppPhone JSX 骨架、ios_frame 三步用法、品位锚点全表。文末附录是 7 条硬规则速查，正文是每条规则的展开。


做 iOS/Android/移动 app 原型时（触发：「app 原型」「iOS mockup」「移动应用」「做个 app」），下面四条**覆盖**通用 placeholder 原则——app 原型是 demo 现场，静态摆拍和米白占位卡没有说服力。

### 0. 架构选型（必先决定）

**默认单页 inline React**——所有屏组件/data/styles 直接写进主 HTML 的 `<script type="text/babel">...</script>` 标签，**不要**把屏代码拆成 `<script src="components.jsx">` 外部加载。React/Babel 这类第三方库可用本地 `vendor/` 副本（同样的库文件内联会让单个脚本超 500KB，Babel 会告警）。原因：`file://` 协议下浏览器把外部 JS 当跨 origin 拦截，强制用户起 HTTP server 违反「双击就能开」的原型直觉。引用本地图片必须 base64 内嵌 data URL，别假设有 server。

**拆外部文件只在两种情况**：
- (a) 单文件 >1000 行难维护 → 拆成 `components.jsx` + `data.js`，同时明确交付说明（`python3 -m http.server` 命令 + 访问 URL）
- (b) 需要多 subagent 并行写不同屏 → `index.html` + 每屏独立 HTML（`today.html`/`graph.html`...），iframe 聚合，每屏也都是自包含单文件

**选型速查**：

| 场景 | 架构 | 交付方式 |
|------|------|----------|
| 单人做 4-6 屏原型（主流） | 单页 inline（库可本地 vendor） | 一个 `.html` 双击开 |
| 单人做大型 App（>10 屏） | 多 jsx + server | 附启动命令 |
| 多 agent 并行 | 多 HTML + iframe | `index.html` 聚合，每屏独立可开 |

### 1. 先找真图，不是 placeholder 摆着

默认主动去取真实图片填充，不要画 SVG、不要拿米白卡摆着、不要等用户要求。常用渠道：

| 场景 | 首选渠道 |
|------|---------|
| 美术/博物馆/历史内容 | Wikimedia Commons（公共领域）、Met Museum Open Access、Art Institute of Chicago API |
| 通用生活/摄影 | Unsplash、Pexels（免版权） |
| 用户本地已有素材 | `~/Downloads`、项目 `_archive/` 或用户配置的素材库 |

Wikimedia 下载避坑（本机 curl 走代理 TLS 会炸，Python urllib 直接走得通）：

```python
# 合规 User-Agent 是硬性要求，否则 429
UA = 'ProjectName/0.1 (https://github.com/you; you@example.com)'
# 用 MediaWiki API 查真实 URL
api = 'https://commons.wikimedia.org/w/api.php'
# action=query&list=categorymembers 批量拿系列 / prop=imageinfo+iiurlwidth 取指定宽度 thumburl
```

**只有**当所有渠道都失败 / 版权不清 / 用户明确要求时，才退回诚实 placeholder（仍然不画烂 SVG）。

**真图诚实性测试**（关键）：取图之前先问自己——「如果去掉这张图，信息是否有损？」

| 场景 | 判断 | 动作 |
|------|------|------|
| 文章/Essay 列表的封面、Profile 页的风景头图、设置页的装饰 banner | 装饰，与内容无内在关联 | **不要加**。加了就是 AI slop，等同紫色渐变 |
| 博物馆/人物内容的肖像、产品详情的实物、地图卡片的地点 | 内容本身，有内在关联 | **必须加** |
| 图谱/可视化背景的极淡纹理 | 氛围，服从内容不抢戏 | 加，但 opacity ≤ 0.08 |

**反例**：给文字 Essay 配 Unsplash「灵感图」、给笔记 App 配 stock photo 模特——都是 AI slop。取真图的许可不等于滥用真图的通行证。

### 2. 交付形态：默认「平铺 + 可操作」，不要问用户

iOS App 原型的**默认交付形态就一种，不要再问用户「要平铺还是可操作」**：**平铺多个主界面，且每一台都能交互**。一眼看全貌（多台 iPhone 并排），又每台都能点 tab 切换、在界面上做基本操作（展开、切换、选中、打开弹层）。两个好处一次给齐，别让用户二选一。

| 维度 | 默认做法 |
|------|---------|
| **屏数** | 按覆盖矩阵决定：`coverage.json` 里每个 `rendered` 的 `P*`/`S*`/`X*` 都要有真实屏。**不得先压成 4–6 个，再用「其余可通过 tab/导航到达」代替覆盖**；也不得把未渲染项写成已覆盖。屏数少（如 4–6 个）只在页面地图确实只有这么多，或其余已写 `deferred-native` + 理由 + 原生验证义务时成立 |
| **布局** | 多台独立 iPhone 横向 `flexWrap` 并排，每台上方一行 italic 小字标签说明这是哪个界面 |
| **每台交互** | 每台都是独立的迷你状态机：tab bar 可切、界面内按钮/卡片/开关可点、能弹 modal——不是静态摆拍 |

**平铺只是展示方式，不是覆盖口径**：哪些页面/弹层/全局状态被真实渲染，以 `prototype-notes.md` 与 `coverage.json` 为准（`SKILL.md` §2.2 阶段 2、§6.3）。

**只有两种特例才偏离默认**（用户明确说了才走，否则一律默认）：
- 用户明确「只要静态截图 / 不用能点 / 就看 layout」→ 退回纯静态 overview（每台只渲染 `ScreenComponent`，不挂状态机）
- 用户明确「只演示一条流程 / 走一遍 onboarding / 单机 demo」→ 单台 `AppPhone` 走完整 flow

**默认骨架**（平铺多台，每台各自一个带 state 的 AppPhone）：

```jsx
// 每台 = 一个独立状态机，初始落在自己负责的主界面
function AppPhone({ initial }) {
  const [screen, setScreen] = React.useState(initial);
  const [modal, setModal] = React.useState(null);
  // 按 screen 渲染对应 ScreenComponent，传入 onTabChange/onOpen/onClose/onToggle 等 callback
  return (
    <IosFrame>
      <ScreenComponent
        screen={screen}
        onTabChange={setScreen}
        onOpen={setModal}
        onClose={() => setModal(null)}
      />
    </IosFrame>
  );
}

// 平铺：4-6 台并排，每台 initial 落在不同主界面
<div style={{display: 'flex', gap: 32, flexWrap: 'wrap', padding: 48, alignItems: 'flex-start'}}>
  {mainScreens.map(s => (
    <div key={s.id}>
      <div style={{fontSize: 13, color: '#666', marginBottom: 8, fontStyle: 'italic'}}>{s.label}</div>
      <AppPhone initial={s.id} />
    </div>
  ))}
</div>
```

Screen 组件接 callback props（`onTabChange`、`onOpen`、`onClose`、`onToggle`、`onAnnotation`），不硬编码状态。TabBar、按钮、作品卡、开关加 `cursor: pointer` + hover 反馈。每台落在不同主界面，但 tab 切换后能到达彼此——平铺给全貌，点击给纵深。

### 3. 交付前跑真实点击测试

静态截图只能看 layout，交互 bug 要点过才发现。用 Playwright 跑 3 项最小点击测试：进入详情 / 关键标注点 / tab 切换。检查 `pageerror` 为 0 再交付。Playwright 可用 `npx playwright` 调用，或按本机全局安装路径（`npm root -g` + `/playwright`）。

### 3.1 平铺是展示形态，不是覆盖上限

**平铺 4–6 台只解决"一眼看全貌"，不解决"每个 `P*`/`S*`/`X*` 都被建模"。** 多页面重设计里，其余页面与状态必须可到达，方式按优先级：

1. **真实路径**：tab / 导航 / 按钮点进去（首选，最接近用户）。
2. **审阅路由**：`?screen=<id>` 直达，用于平铺里没摆出来的页面；路由名与 `P*` 对得上。
3. **状态/弹层参数**：`?overlay=<S*>`、`?state=<X*>`，用于空/错/锁定/未授权/额度用尽等无法从正常路径自然到达的状态。
4. **审阅面板**（最后手段）：一个只用于评审的开发者切换器，明确标注"非产品 UI"，不进 `baselines/`、不参与设计评审。**不得用它代替真实路径**——如果用户在产品里到不了这个状态，说明状态设计本身有问题。

**判定**：说不清"这个 `S*`/`X*` 怎么到达"，就等于没建模；`coverage.json` 里写 `rendered` 但实际到不了，是虚假覆盖。

### 3.2 状态覆盖闭合

- 每个 `P*` 至少有：默认态；存在数据时加空/加载/错误（可放在同一屏的审阅路由里）。
- 每个 `S*` 能开能关，关闭路径（按钮/返回/下滑）至少一种在最大字号下可达。
- 每个 `X*` 要么有真实呈现，要么 `deferred-native` + 理由 + `native_verify: true`。
- 状态切换只改**数据与状态**，不改布局骨架——否则评审时无法判断"这是状态设计还是另一版设计"。
- 状态命名和 `state-map.md` 的枚举一致，不临时造同义词。

### 3.3 缩放矩阵

- 默认 `1.0 / 1.3 / 1.6 / 2.0`（项目有规定按项目，更严取更严）。
- 实现方式二选一：`?fs=` 参数或根节点 CSS 变量；把方式写进 `prototype-notes.md`。
- **多列、label+value 同行、固定高度卡片/弹层、长中文文案**必须在最大档单独渲染并截图；这些结构是 1.6 错位的高发区。
- 缩放档位是设计变量，不是浏览器缩放：浏览器 zoom 不会触发重排，不能替代 `?fs=`。

### 4. 品位锚点（pursue list，fallback 首选）

没有 design system 时默认往这些方向走，避免撞 AI slop：

| 维度 | 首选 | 避免 |
|------|------|------|
| **字体** | 衬线 display（Newsreader/Source Serif/EB Garamond）+ `-apple-system` body | 全场 SF Pro 或 Inter——太像系统默认，没风格 |
| **色彩** | 一个有温度的底色 + **单个** accent 贯穿全场（rust 橙/墨绿/深红）| 多色聚类（除非数据真的有 ≥3 个分类维度） |
| **信息密度·克制型**（默认）| 少一层容器、少一个 border、少一个**装饰性** icon——给内容留气口 | 每条卡片都配无意义的 icon + tag + status dot |
| **信息密度·高密度型**（例外）| 当产品核心卖点是「智能 / 数据 / 上下文感知」时（AI 工具、Dashboard、Tracker、Copilot、番茄钟、健康监测、记账类），每屏需**至少 3 处可见的产品差异化信息**：非装饰性数据、对话/推理片段、状态推断、上下文关联 | 只放一个按钮一个时钟——AI 的智能感没表达出来，跟普通 App 没区别 |
| **细节签名** | 留一处「值得截图」的质感：极淡油画底纹 / serif 斜体引语 / 全屏黑底录音波形 | 到处平均用力，结果处处平淡 |

**两条原则同时生效**：
1. 品位 = 一个细节做到 120%，其它做到 80%——不是所有地方都精致，而是在合适的地方足够精致
2. 减法是 fallback，不是普适律——产品核心卖点需要信息密度支撑时（AI / 数据 / 上下文感知类），加法优先于克制。详见下文「信息密度分型」

### 5. iOS 设备框必须用 `assets/ios_frame.jsx`——禁止手写 Dynamic Island / status bar

做 iPhone mockup 时**硬性绑定** `assets/ios_frame.jsx`。这是已经对齐过 iPhone 15 Pro 精确规格的标准外壳：bezel、Dynamic Island（124×36、top:12、居中）、status bar（时间/信号/电池、两侧避让岛、vertical center 对齐岛中线）、Home Indicator、content 区 top padding 都处理好了。

**禁止在你的 HTML 里自己写**以下任何一项：
- `.dynamic-island` / `.island` / `position: absolute; top: 11/12px; width: ~120; 居中的黑圆角矩形`
- `.status-bar` with 手写的时间/信号/电池图标
- `.home-indicator` / 底部 home bar
- iPhone bezel 的圆角外框 + 黑描边 + shadow

自己写 99% 会撞位置 bug——status bar 的时间/电池被岛挤压、或 content top padding 算错导致第一行内容盖在岛下。iPhone 15 Pro 的刘海是**固定 124×36 像素**，留给 status bar 两侧的可用宽度很窄，不是你凭空估的。

**用法（严格三步）**：

```jsx
// 步骤 1: Read 本 skill 的 assets/ios_frame.jsx（相对本 SKILL.md 的路径）
// 步骤 2: 把整个 iosFrameStyles 常量 + IosFrame 组件贴进你的 <script type="text/babel">
// 步骤 3: 你自己的屏组件包在 <IosFrame>...</IosFrame> 里，不碰 island/status bar/home indicator
<IosFrame time="9:41" battery={85}>
  <YourScreen />  {/* 内容从 top 54 开始渲染，下边留给 home indicator，你不用管 */}
</IosFrame>
```

**例外**：只有用户明确要求「假装是 iPhone 14 非 Pro 的刘海」「做 Android 不是 iOS」「自定义设备形态」时才绕过——此时读对应 `android_frame.jsx` 或修改 `ios_frame.jsx` 的常量，**不要**在项目 HTML 里另起一套 island/status bar。


---

## 附录：App / iOS 原型专属守则（速查版）

> 2026-10-27 从 SKILL.md 移入，内容逐字保留；入口见 SKILL.md 对应小节。

做移动 app 原型时（触发：「app 原型」「iOS mockup」「移动应用」「做个 app」），以下硬规则**覆盖**通用 placeholder 原则——app 原型是 demo 现场，静态摆拍没有说服力。完整操作细节（架构选型表 / 取图渠道与代码 / AppPhone JSX 骨架 / ios_frame 三步用法 / 品位锚点全表）见本文档正文 §0–§4：

1. **架构默认单页 inline React**：屏代码、样式、图片都在同一页（React/Babel 等库可用本地 `vendor/` 副本），`file://` 双击就能开；仅 >1000 行难维护或多 agent 并行写不同屏才按屏拆文件（拆了必须附 `python3 -m http.server` 启动说明）
2. **先找真图再设计**：渠道见本文 §1 与 `references/image-assets.md`；取图前过**真图诚实性测试**——「去掉这张图信息是否有损？」无损 = 装饰 = slop，不加
3. **交付形态默认「平铺 4-6 主屏 + 每台可交互」**，不要问用户二选一；每台是独立迷你状态机（tab 可切 / 按钮可点 / 能弹 modal），仅用户明确说「只要静态」或「单流程 demo」才偏离
4. 🔴 **设备框必须用现成组件**：iOS 用 `assets/ios_frame.jsx`，Android 用 `assets/android_frame.jsx`；禁止手写 Dynamic Island / status bar / home indicator / bezel / 导航栏——自己写 99% 撞位置 bug（iOS 岛是固定 124×36，两侧 status bar 空间极窄；Android 系统栏高度随版本与手势模式变化）
5. **信息密度分型**：默认克制型（少一层容器 / 少一个 border / 少一个装饰 icon）；产品卖点是 AI / 数据 / 上下文感知时走**高密度型**——每屏 ≥3 处**有内容的**差异化信息，装饰 icon 照样忌讳
6. **交付前 Playwright 跑 3 项点击测试**（进详情 / 关键标注点 / tab 切换），`pageerror` 为 0 再交付
7. **品位锚点**：衬线 display（Newsreader/Source Serif/EB Garamond）+ `-apple-system` body；一个有温度的底色 + 单 accent 贯穿；留一处「值得截图」的 120% 细节签名
