# 验证：HTML 原型与原生 App 的证据链

> **读这份文档的时机**：原型要交付、要出基准图、要判「这版能不能过」、或验证工具本身可疑时。
> **一句话立场**：**没跑过的不能叫通过；跑过但没断言的只能叫观察。** 验收矩阵（阶段 7）见 `references/app-visual-workflow.md`；本文给方法、命令与判据。

---

## 0. 先验证你的验证工具

**在相信任何渲染结果之前，先确认渲染器本身能正确渲染。**

- 截图必须来自真实渲染（Playwright / 真机截图），**缩略图、设计稿预览、源码推断都不能当验收依据**。
- 怀疑是工具问题时做**对照实验**：拿一个已知正确的同类页面/同类设备截图过同一条链路，看是否同样异常。
- 渲染器骗得了眼睛，骗不过计数：文字逐字比对（`re.sub(r'\s+','')` 后相等）、元素数量比对，作为机械兜底。

---

## 1. UI 验收硬门（HTML 与 Android 分开判）

门槛来自项目规格（项目 `AGENTS.md` / design spec / `direction-approved.md`）。项目更严取更严；**执行方不得为了让测试通过而下调门槛**。

| 项 | HTML 原型（CSS px） | Android 原生（dp / 真机） |
|---|---|---|
| 触控目标 | `getBoundingClientRect` 覆盖 `button, a, input, textarea, select, summary, [role=button], [onclick]`；阈值按项目规格，无规格时按目标平台取 **Android 原型 ≥48 CSS px / iOS 原型 ≥44 CSS px** | `adb shell wm density` 取密度，`uiautomator dump` 读 bounds 换算 **dp**；实际可点区域 ≥ **48×48dp** |
| 字号 | 叶子文本节点 computed `font-size`：正文 ≥14、标签/注释 ≥12，两档分别跑（见下方命令）；1.0 / 1.3（项目要求时 1.5）各跑一次 | `sp` + 系统 `fontScale`；真机调大字体后复看关键屏 |
| 对比度 | `scripts/check-contrast.py` 三档（装饰项单独标注） | 同一 token 值；关键项用真机截图复核 |
| 横向溢出 | `scrollWidth <= clientWidth + 1` | 真机确认无截断、无被导航栏/键盘遮挡 |
| 交互 | 真实点击/输入 + 结果断言；控制台 0 error、0 未捕获异常 | 真机点击/返回/滚动；崩溃、ANR、回退栈证据 |
| 路由 | 每个入口到非空屏，返回路径可达 | 系统返回键与页面返回行为一致 |

🔴 **CSS px 不能直接证明 Android 48dp**：`check-ui.mjs` 报的是 CSS px；只有页面按设计宽度 1:1 渲染时数值才可作**近似**。密度、字体缩放、系统栏 inset 都会改变真实 dp。**HTML 检查通过不得写成「Android 48dp 合规」**；原生必须按右列验证并留真机证据。

```bash
# 页面级客观采集：触控/字号/对比度/溢出/破图
# ① 正文档（默认 14）：正文、列表项、说明文字都不得低于此值
node scripts/check-ui.mjs --url <file:///...> --tap 48
# ② 标签档（12）：只在 ① 报出 12–13px 的文本时复核，确认它确实是标签/注释而不是正文
node scripts/check-ui.mjs --url <file:///...> --tap 48 --font-min 12
# 非产品文本（设备状态栏/导航条，由设备框渲染）单独排除，命中项会写进 JSON 的 font.ignored
node scripts/check-ui.mjs --url <file:///...> --tap 48 --font-ignore '[data-dw-chrome]'
```

**两档的关系**：② 通过只证明「没有低于 12 的文本」，**不构成正文 ≥14 的证明**；① 报出的正文级失败不得用 ② 洗掉。**低于 12 一律不合格**，不存在「标签可以到 11」的档位。正文档与标签档的实际判定要在报告里分开写（`fontMin` 与报出的文本清单一起留档）。

🔴 **非产品文本不计入产品字号，但不得用「下调全局阈值」处理**：设备状态栏、电池百分比、导航条由 `assets/*_frame.jsx` 渲染，属于设备外框而不是产品文案（`batteryText` 本身就是 11px）。这类文本用 `--font-ignore <选择器>` 排除——脚本会拒绝 `--font-min < 12`，并把命中的选择器与文字回传到 `font.ignored`；报告里必须列出排除项，**只写「阈值 11 通过」不成立**，因为它同时也放过了 11px 的产品正文。

**边界**：只检查当前 URL 的可见状态；弹层、空态、错误态、折叠区要先导航/展开，或用项目交互脚本覆盖，不能只看首页。

**历史原型（本规则生效前产出）实测不通过时按发现记录**：写进报告并标注产出时间，不追认为通过，也不为消红下调阈值；只有该原型仍是当前任务的交付物时才做字号定向修复（直接改字号，不重跑整套流程）。

### 1.1 设计体检（客观项）

| 检查 | 结果形态 | 说明 |
|---|---|---|
| 图片加载失败 | 🔴 红灯（`images.broken`，退出码 1） | `complete && naturalWidth > 0` |
| 文字/背景计算对比度 | 🔴 红灯（`contrast.failures`） | WCAG 公式；正文 ≥4.5:1，大字 ≥3:1 |
| 对比度无法判定 | 🟡 黄灯（`contrast.unknown`） | 文字压在渐变/图片上——必须人工或 DevTools 读实测值 |
| 相对路径引图 | 🟡 黄灯（`relative-asset`） | 单文件交付会 404；多文件确认整目录一起交付 |
| 外观指纹撞族 | 🟡 黄灯（`ledger-family`） | 只提示，见 `references/design-research.md` §5 |

**分工红线**：

- 脚本只出事实，不出结论——「焦点是否在核心任务」「视觉噪音是否过多」交 `references/critique-guide.md`。
- 黄灯不改变退出码，**不能为了全绿去改设计**。
- 图标/边框/分割线归「重要图形（≥3:1）」还是「纯装饰」，脚本不判，人工按 `content-guidelines.md` 三档归类。

### 1.2 业务断言必须独立推导

- 测试从**规格 + fixture** 重算期望值，**不得复制 UI 里手写的顺序/数值/文案**当预期。
- 至少一条断言验证「DOM 顺序 / 数值 = 规格重算结果」，而不只是「两种排序不同」。
- **UI 自报的「通过」不能替代项目级断言**：等级、排序、金额、日期等业务结果必须独立重算。
- 门槛与规格冲突：先改规格或报告，**不静默降阈值**。

### 1.3 机械通过 ≠ 设计通过

`check-ui` / 对比度 / Playwright 全部绿灯，只说明「没有坏」，不说明「设计对了」。阶段 4 结束前必须再用**当前版本真实渲染截图**（含弹层与空/错/大字体）做设计评审（`references/critique-guide.md`「原型设计评审」）；阶段 6–7 必须用旧版 / HTML / 新版三方真实证据判断落地。**不得把脚本退出码 0 写成设计验收通过。**

---

## 2. HTML 原型验证清单

每次产出 HTML 后，按受影响范围执行（局部迭代只跑受影响屏/状态，阈值不变）。项目硬性验收更严时从项目要求。

### 2.1 渲染与控制台

```bash
python3 scripts/verify.py path/to/prototype/index.html
```

用 headless Chromium 打开、截图、抓控制台错误并报告 status。**白屏必然有控制台错误**，先看错误再谈视觉。

### 2.2 多视口

App 原型按目标机型宽度抓，不按桌面断点：

```bash
python3 scripts/verify.py prototype/index.html --viewports 360x800,390x844,412x915,768x1024
```

### 2.3 交互

静态截图看不到 Tab 切换、弹层、选中态。**每条关键交互都要「动作 + 结果断言」**：

```python
context = browser.new_context(
    record_video_dir="videos/",
    record_video_size={"width": 412, "height": 915},
)
page = context.new_page()
page.goto(url)
page.click("#tab-profile")
assert page.locator("#profile-panel").is_visible()   # 动作 + 断言
context.close()  # 关闭 context 后才落盘视频
```

录屏只是证据，不等于功能验证：**没有断言的视频不能作为「交互正常」的证明**。

### 2.4 状态覆盖

至少覆盖：默认、加载、空、错误、数据不足；输入类页面加键盘弹出、校验错误、提交中、提交失败。只截首屏等于没验。

### 2.5 产物一致性自检（只读，不替代设计判断）

```bash
python3 scripts/check-deliverables.py --task-dir design-demos/<task> --stage 7
python3 scripts/check-deliverables.py --task-dir design-demos/<task> --stage 4 --skip-artifacts   # 局部迭代：只校验已存在记录
```

检查：阶段产物是否存在（`asset-manifest.json` 按「有素材才必需」处理，存在才校验）、`concept-index.json` / `direction-approved.md` 里的路径与 sha256 是否对应真实文件、决策出口与基线状态是否合法（实施基线唯一性**按当前任务判定**：同一任务含嵌套记录只能有一个「实施基线」，不同任务各自有基线不互斥）、`asset-manifest.json`（复用 `asset_manifest.py verify`）、`prototype-notes.md` 记录的截图指纹、阶段 7 是否分开给出双验收结论。退出码 0 只表示**机械一致**：一致 ≠ 设计通过，脚本不判断语义、不裁定对比度例外、不按修改时间猜「过期」；发现不一致由执行方改产物或记录，脚本不改任何文件。

---

## 3. 截图与基准图

```python
page.screenshot(path='full.png', full_page=True)      # 整页
page.screenshot(path='viewport.png')                   # 可见区
element.screenshot(path='hero.png')                    # 单元素
browser.new_page(device_scale_factor=2)                 # 2x
page.wait_for_timeout(2000)                             # 等动效 settle
```

- 基准图（`handoff/baselines/`）与页面/状态一一命名，来自真实渲染。
- 发给用户时用 Markdown 图片引用或绝对路径链接；远程协作者需要链接时由用户用自己的图床，**不上传非公开内容**。

---

## 4. 常见问题排查

| 现象 | 先查 |
|---|---|
| 白屏 | 控制台错误；React/Babel 版本与 integrity；`styles` 命名冲突；跨文件组件是否 export 到 `window`；JSX 语法（用非压缩 babel 复现） |
| 动效卡顿 | DevTools Performance；layout thrashing；动效优先 `transform` / `opacity` |
| 字体不对 | `@font-face` 可访问性、fallback、中文加载策略 |
| 布局错位 | `box-sizing`、reset、DevTools gridlines |
| 与基准图不一致 | 先确认截图尺寸/比例一致，再比对六项（`references/design-handoff.md` §6.1） |

---

## 5. 原生端验证

- 装包**只用** `~/.zcode/skills/app-testing/runtime/mi6-verify/adb-auto-install.sh`；**禁止裸 `adb install`**；多台设备在线即停。
- 证据：安装成功、冷启动、首屏截图、关键流程操作截图/录屏、`logcat` 无崩溃/ANR。
- 字体缩放、深色模式、系统返回、安全区（刘海/手势条/键盘）逐项在真机看。
- 设备不在线 → 标 `PARTIAL`/`BLOCKED`，**不写成通过**。
- **构建/安装/启动成功不等于设计落地**：必须逐页说明结构、层级、交互如何实现或有依据保留，并用旧版 / HTML / 新版三方真实证据检查（`references/app-visual-workflow.md` 阶段 6「设计落地映射」）。只看首页不能推断次级页已落地。
- 旧版基线缺失先复用既有截图/记录；**不得为补基线擅自降级安装、清数据或恢复旧包**；仍缺证如实标注。

### 5.1 工程验收与设计验收分开

同一份 `verification-report.md` 给两条结论：工程验收（功能/业务规则/测试/构建/真实运行）与设计验收（产品目标/页面完整/原则/原型意图/真机体验/三方对照）。**两项都达标才是整体 PASS**；一条未达标但可修 → `PARTIAL`。不得用代码修改量、视觉变化百分比、页面改动数量或测试数量替代设计结论。

---

## 6. 验证=设计师的第二双眼

AI 生成的界面经常：看起来对但交互有 bug；静态截图好但滚动错位；宽屏好看但窄屏崩；深色模式忘了测；改了一处没测其他状态。

**最后 1 分钟的验证可以省 1 小时的返工**；但验证也不是无限循环——定向修复后按缺陷影响面复验，不重跑整个设计流程。
