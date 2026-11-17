# 动效设计体系 · 从反馈到叙事

> **读这份文档的时机**：阶段 1 定体验基调、阶段 2 做可交互原型、阶段 3 评审、阶段 4 交接、阶段 5 实现、阶段 6 验收。
> **一句话立场**：**动效是信息的一部分**——它回答“我刚才做了什么、现在在哪、接下来会发生什么”。不能回答这三件事的动画就是装饰。
> 本文只展开 `SKILL.md`；阶段与证据门以 `SKILL.md` 为准。平台差异见 `native-platform.md`，状态语义见 `experience-states.md`。

---

## 1. 四条原则

| 原则 | 含义 | 反例 |
|---|---|---|
| **有目的** | 每个动画对应反馈、方向、连续、进度或叙事之一 | 所有内容入场都淡入、粒子背景、无意义的呼吸光 |
| **即时** | 按压反馈 ≤100ms 出现；导航转场 ≤400ms；不与用户抢控制 | 点击后等 800ms 才开始动 |
| **连续** | 元素从哪来、到哪去有空间关系；共享元素不瞬间消失 | 全屏 cross-fade 代替页面推入 |
| **可退出** | 可中断、可重复触发、可跳过；尊重减少动态 | 动画期间锁死输入；必须看完才能操作 |

**判断句**：删掉这个动画，用户会失去什么信息？答不出 → 删掉。

---

## 2. Motion tokens（统一，不逐页随写）

### 2.1 时长

| token | 值 | 用途 |
|---|---|---|
| `motion_duration_instant` | 0–50ms | 按压/选中着色，几乎即时 |
| `motion_duration_xs` | 100ms | 图标切换、状态层、微反馈 |
| `motion_duration_s` | 150ms | 按钮/开关/复选框、snackbar 出现 |
| `motion_duration_m` | 200ms | 内容入场、列表项插入、tab 指示 |
| `motion_duration_l` | 300ms | 底部弹层、dialog、较大区域展开 |
| `motion_duration_xl` | 350–400ms | 页面转场、共享元素 |
| `motion_duration_ambient` | 600–1200ms 循环 | 只用于有语义的氛围（如呼吸引导），必须有降级 |

**硬规则**：UI 响应类转场不得 >400ms；加载指示可 600–1200ms 循环（须有真实进度语义与减少动态降级）；叙事/氛围 >600ms 必须可跳过。

### 2.2 缓动

| token | 曲线 | 用途 |
|---|---|---|
| `motion_easing_standard` | `cubic-bezier(0.2, 0, 0, 1)` | 进入/移动的默认 |
| `motion_easing_decelerate` | `cubic-bezier(0, 0, 0, 1)` | 元素进入、展开 |
| `motion_easing_accelerate` | `cubic-bezier(0.3, 0, 1, 1)` | 元素退出、收起 |
| `motion_easing_emphasized` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | 关键转场、共享元素 |
| `motion_spring_standard` | 刚度≈380 / 阻尼≈32 | 手势驱动的 sheet/卡片 |
| `motion_spring_gentle` | 刚度≈220 / 阻尼≈26 | 大幅位移、有机感 |

**不要**给每个页面随意写 `ease-in-out` 或 `cubic-bezier(.4,0,.2,1)`；token 之外的曲线必须写理由。

### 2.3 距离、缩放与透明度

- 页面推入位移：屏宽的 20–30%；返回反向；不横跨整屏飞入。
- 缩放：0.96–1.04 足够表达按压/弹出；不要 0.5 弹到 1。
- 透明度：内容入场从 0→1 可以，但结构位移必须同时存在，否则只是“闪一下”。
- 阴影/模糊不做逐帧动画（性能与观感都差）。

---

## 3. 基础交互动效清单（每个 App 必查）

| id | 动效 | 触发 | 起 → 止 | 时长 / 缓动 | 中断与重复 | 减少动态 |
|---|---|---|---|---|---|---|
| M01 | 按压反馈 | touch down | 缩放 1→0.97 + 状态层 0→12% | 100ms / standard | 抬起立即回弹；快速连点不叠加 | 只保留状态层变化 |
| M02 | 选中/切换 | 点选 | 指示器位移 + 着色 | 150–200ms / emphasized | 连点跟随最后一次 | 直接切换 |
| M03 | Tab 切换 | 点底部导航 | 内容淡入 + 8dp 上移；保留各 tab 栈 | 200ms / decelerate | 快速切换以最后一次为准 | 直接显示 |
| M04 | 弹层出现 | 点开 | 遮罩 0→40%；面板 y+24→0 | 250–300ms / emphasized | 手势可拖拽中断；重复触发不堆叠 | 直接出现 |
| M05 | 弹层关闭 | 返回/下滑/按钮 | 面板 y→+24；遮罩→0 | 200ms / accelerate | 下滑超过阈值即关闭；未过阈值回弹 | 直接消失 |
| M06 | 加载出现 | 数据请求 | 骨架屏淡入；>300ms 才显示 | 150ms / standard | 数据到达立即替换，不播完 | 静态占位 |
| M07 | 内容入场 | 首屏/列表加载 | 8dp 上移 + 0→1，按 30–50ms 错峰 | 200ms / decelerate | 只播一次；刷新不重播全部 | 不位移，只显示 |
| M08 | 列表插入/删除 | 数据变化 | 高度展开/收起 + 淡入淡出 | 200ms / standard | 连续操作合并；不阻塞滚动 | 直接增删 |
| M09 | 错误出现 | 校验/请求失败 | 行内文案淡入 + 输入框描边 | 150ms / standard | 同字段错误替换，不抖动整页 | 直接显示 |
| M10 | 成功确认 | 保存/完成 | 勾选描边 + 轻微 scale 1→1.06→1 | 250ms / emphasized | 一次操作只播一次 | 静态勾选 |
| M11 | Snackbar | 操作结果 | 底部 y+16→0 + 淡入 | 150ms / decelerate | 新消息替换旧消息；可撤销 | 直接出现 |
| M12 | 下拉刷新 | 下拉过阈值 | 指示器跟随手指；释放后转圈 | 手势驱动 / spring | 未过阈值回弹；刷新中再拉不叠加 | 静态进度 |

**最低要求**：每个可点控件有按压/选中反馈；每次导航有方向性转场；每次数据变化有加载或结果反馈；每个弹层可开可关可中断。

---

## 4. 高级体验动效（按产品需要，不强加）

| id | 动效 | 适用 | 设计要求 |
|---|---|---|---|
| M20 | 页面转场 | 所有多页 App | 方向 = 层级（push 从右/下方进入，pop 反向）；返回保持滚动位置 |
| M21 | 共享元素/容器变换 | 列表 → 详情、卡片 → 全屏 | 同一元素从原位连续放大到目标位；中途不换图；不可实现时用方向性转场，不用全屏淡入 |
| M22 | 数字变化 | 步数、金额、计时、进度 | 等宽数字；滚动/计数按真实值；不做假增长 |
| M23 | 数据可视化 | 图表、进度环 | 从 0 或上一状态生长；坐标轴/刻度先出现；不逐点乱跳 |
| M24 | 阶段完成 | 目标达成、任务完成 | 只对真实成果庆祝；一次；可跳过；不阻塞下一步 |
| M25 | 成长/解锁 | 确有成长机制的产品 | 动画对应真实解锁条件；不制造虚假稀缺；不做无限奖励循环 |
| M26 | 插画/场景动效 | 首页 hero、空态、引导 | 极轻（视差 2–6dp、光点/粒子少量）；不抢文字；可暂停 |
| M27 | 手势反馈 | 拖拽、滑动、缩放 | 跟手优先；松手用 spring 归位；阈值与方向可感知 |

**边界**：产品没有真实成果/解锁机制时，不得为了动效新增积分、徽章、任务或庆祝流程（`SKILL.md` §3 产品原则）。

---

## 5. 动效规格模板（交接与评审共用）

每个重要动效写一条，写入 `prototype-notes.md` 的动效矩阵，并同步 `handoff/states-interactions.md`：

```markdown
### M21 列表卡 → 阅读页（共享元素）
- 触发：点击待读卡
- 起始：卡片封面 rect (x,y,w,h)、圆角 12
- 结束：阅读页头图 rect、圆角 0
- 属性：transform（位置/缩放）+ border-radius；不透明度保持 1
- 时长/缓动：380ms / motion_easing_emphasized
- 中断：转场中返回 → 反向播回；快速连点只响应第一次
- 重复：返回列表后再次进入可重播
- 减少动态：直接切换页面，保留 120ms 淡入
- 平台：Android sharedTransitionLayout；iOS matchedGeometryEffect
- 证据：录屏 motion-m21.mp4 + 首/中/末三帧
```

**缺任何一栏都不算规格**；只写“淡入淡出 300ms”不足以交接。

---

## 6. 动效覆盖矩阵（阶段 2/3 必填）

在 `prototype-notes.md` 维护：行 = 页面/弹层/关键状态，列 = 反馈/导航/加载/结果/转场。

| 对象 | 按压/选中 | 导航/转场 | 加载 | 结果/成功 | 中断/降级 | 证据 |
|---|---|---|---|---|---|---|
| P1 待读 | M01/M02 | M20 进阅读 | M06 | M10 | 减少动态 | r1-p1.mp4 |
| S1 筛选 | M01/M04 | — | — | M11 | 下滑关闭 | r1-s1.mp4 |

- 每格填动效 id 或 `N/A` + 理由；空格 = 未设计。
- 静态截图不能证明动效；证据用录屏、连续帧或可重放的交互脚本。
- 动效数量不是指标：一个页面 2–4 个有目的的动效通常足够。

---

## 7. HTML 原型实现要点

### 7.1 Token 与结构

```css
:root {
  --motion-duration-instant: 50ms;
  --motion-duration-xs: 100ms;
  --motion-duration-s: 150ms;
  --motion-duration-m: 200ms;
  --motion-duration-l: 300ms;
  --motion-duration-xl: 380ms;
  --motion-easing-standard: cubic-bezier(.2, 0, 0, 1);
  --motion-easing-emphasized: cubic-bezier(.05, .7, .1, 1);
  --motion-easing-decelerate: cubic-bezier(0, 0, 0, 1);
  --motion-easing-accelerate: cubic-bezier(.3, 0, 1, 1);
}
```

- 只动画 `transform` / `opacity`；共享元素的 `border-radius` 可随 transform 一起过渡（绘制型、短时长）；不要动画 `width/height/top/left/filter/box-shadow`。
- 共享元素用 FLIP：先量起始 rect，再量结束 rect，用 `transform` 补间；或用 `document.startViewTransition`（不可用时降级为方向性转场）。
- 手势动效用 `pointerdown/move/up` + `requestAnimationFrame`；松手用 spring 近似（CSS `linear()` 或 JS 弹簧）。
- React 中用状态驱动 class，不在渲染函数里直接写 `setTimeout` 串联；清理定时器与监听。

### 7.2 减少动态

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
    scroll-behavior: auto !important;
  }
}
```

- 减少动态不是“全部消失”：保留即时状态变化与必要的方向提示，去掉位移、缩放、循环与庆祝。
- 原型要提供可切换的演示开关（评审用，标注“非产品 UI”），或至少能在系统设置下验证。

### 7.3 性能

- 60fps 预算：一帧 16.6ms；同屏同时动画不超过 3–4 组。
- 列表入场只对首屏可见项；长列表滚动时不播放入场。
- 页面隐藏 (`visibilitychange`) 暂停循环动画；离开视口停止。
- 低端设备降级：减少错峰、去掉模糊/粒子、缩短位移。

---

## 8. 原生实现映射

| 动效 | Android | iOS |
|---|---|---|
| 按压/状态层 | `Modifier.clickable` indication / ripple | `UIButton` 高亮 / 自定义 state layer |
| 显隐 | `AnimatedVisibility` | `UIView.animate` / SwiftUI `.transition` |
| 属性动画 | `animate*AsState` | `withAnimation` / `UIViewPropertyAnimator` |
| 手势弹簧 | `Animatable` + `spring()` | `.spring(response:dampingFraction:)` |
| 页面转场 | Navigation Compose transitions / `sharedTransitionLayout` | `UINavigationController` 转场 / `matchedGeometryEffect` |
| 列表增删 | `LazyColumn` `animateItem()` | `List` / Diffable + 动画 |
| 触感 | `HapticFeedback` / `Vibrator` 常量 | `UIImpactFeedbackGenerator` / `UINotificationFeedbackGenerator` |

**交接必须写**：哪些动效由平台默认承担、哪些需要自绘、哪些允许降级；禁用“用系统默认转场替代共享元素”这类廉价替代，除非用户/项目接受。

---

## 9. 验证与证据

| 结论 | 静态截图能证明吗 | 需要什么 |
|---|---|---|
| 有按压/选中反馈 | 不能 | 录屏或前后帧对比 |
| 转场方向与连续性 | 不能 | 录屏 + 首/中/末帧 |
| 动效时长与曲线 | 不能 | 录屏逐帧或 DevTools/性能面板 |
| 可中断/重复触发 | 不能 | 交互脚本：转场中返回、连点、切 tab |
| 减少动态生效 | 不能 | 系统设置/模拟媒体特性下复跑 |
| 性能 | 不能 | 帧率记录或性能面板；卡顿有记录 |

**机械检查**：`python3 scripts/check-motion.py <prototype/index.html>` 只做静态事实采集（是否有 motion token、减少动态、超长/无限/布局属性动画），不判断动效是否好看；语义仍由 ZCode 看录屏判断。

**验收口径**：动效项只能是 PASS / FAIL / NOT TESTED / N/A，并附证据路径；没有录屏或连续帧的动效不得写 PASS。

---

## 10. 反模式

1. 为动画而动画：每个元素都淡入、每个按钮都弹跳。
2. 全屏 cross-fade 代替方向性转场，空间关系丢失。
3. 动画锁输入：用户必须看完才能继续。
4. 1s 以上的 UI 转场；用慢动画伪装性能差。
5. 无限循环装饰动画（光晕、粒子、渐变流动）抢注意力。
6. 用动画掩盖加载失败或假进度。
7. 共享元素中途换图/换尺寸，产生跳变。
8. 忽略 `prefers-reduced-motion`；或把“减少动态”做成整个 App 不可用。
9. 动画 `box-shadow`/`filter`/`width` 导致掉帧。
10. 一次操作触发多层庆祝（震动 + 粒子 + 音效 + 全屏遮罩），把反馈变成打断。
