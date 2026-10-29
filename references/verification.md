# Verification：输出验证流程

一些 design-agent 原生环境（如 Claude.ai Artifacts）有内置的 `fork_verifier_agent` 起 subagent 用 iframe 截图检查。大部分 agent 环境（Claude Code / Codex / Cursor / Trae / 等）里没有这个内置能力——用 Playwright 手动做就能覆盖相同的验证场景。

## 🔴 第 0 条：先验证你的验证工具

**在相信任何渲染结果之前，先确认这个渲染器本身能正确渲染。** 这条排在所有验证之前，
因为工具不可信时，后面每一步都在给你假的绿灯。

两个实测翻车（2026-09，一次带甲方模板的 PPTX 交付）：

- **macOS `qlmanage -t` 生成的缩略图放过了 4 个会导致文字重叠的 bug**。它走的是简化
  渲染路径，对行距的处理比真 PowerPoint 宽容得多——20 页逐页看过去全对，用户在 WPS 里
  一打开就是文字压文字。**缩略图不是渲染，别拿它当验收依据。**
- **LibreOffice 在 macOS 上渲染中文 PPTX 全是豆腐块**，一度让人以为是文件坏了。

**怎么判断是工具的问题还是产物的问题：做对照实验。**
把一个**已知正确的同类文件**丢给同一个渲染器——上面第二例里，把甲方的官方模板原件
拿去渲染，它的中文同样全部消失，当场就能判定这是环境问题、不是你的文件问题。
这一步能省掉几小时在错误方向上的排查。

**可信度排序（macOS）**：

| 工具 | 能不能信 |
|---|---|
| `qlmanage -t` 缩略图 | ❌ 不能当验收依据 |
| LibreOffice headless | ⚠️ 版面可信，字体/中文可能整体丢失 |
| Keynote + AppleScript 导 PDF | ✅ 可自动化的首选，真排版引擎 |
| 目标软件本体（PowerPoint / WPS）打开 | ✅ 最终确认，人工看 |

⚠️ **不要用 System Events 注入按键**去驱动 GUI 翻页截图——按键会打到用户当前正在
输入的窗口里去。要么用 AppleScript 的文档级 API（如 Keynote 的 `export`），要么人工看。

**再配一道不依赖任何渲染器的机械校验**：文字逐字比对（源数据 vs 产物，
`re.sub(r'\s+','')` 后必须完全相等）、元素数量逐页比对。渲染器骗得了眼睛，骗不过计数。

---

## 🔴 UI 验收硬门（HTML 原型 / Android 原生分开判）

**门槛来自项目规格**（project `AGENTS.md` / design spec / `direction-approved.md`）。项目规格更严时取更严值；**执行方不得为了让测试通过而下调门槛**。

| 项 | HTML 原型（CSS px） | Android 原生（dp / 真机） |
|---|---|---|
| 触控目标 | 用 `getBoundingClientRect` 采集，覆盖 `button, a, input, textarea, select, summary, [role=button], [onclick]`，**不是只看 `button`**；阈值按项目规格（无规格时 ≥44px） | `adb shell wm density` 取密度，`uiautomator dump` 读 bounds 换算 **dp**；检查控件**实际可点区域**（不是视觉外框）≥ **48×48dp**；必要时保留真机截图/录屏 |
| 字号 | 叶子文本节点 computed `font-size`，按项目下限；1.0 / 1.3（项目要求时 1.5）各跑一次 | sp 值 + 系统 `fontScale`，按项目规格；真机调大字体后复看关键屏 |
| 对比度 | `scripts/check-contrast.py` 三档（装饰项单独标注） | 同一 token 值；关键项用真机截图复核 |
| 横向溢出 | `scrollWidth <= clientWidth + 1` | 真机/模拟器确认无截断、无被导航栏或键盘遮挡 |
| 交互 | 真实鼠标/触摸事件 + 结果断言；控制台 0 error、0 未捕获异常 | 真机点击/返回/滚动；崩溃、ANR、回退栈证据 |
| 路由 | 每个入口到非空屏，返回路径可达 | 系统返回键与页面返回行为一致 |

🔴 **HTML 的 CSS px 不能直接证明 Android 48dp**：`check-ui.mjs` 报的是 CSS px；只有页面按设计宽度 1:1 渲染（如 412px 视口对应 412dp）时，数值才可作为**近似**。不同屏幕密度、系统字体缩放、状态栏/导航栏 inset 都会改变真实 dp。**HTML 检查通过不得写成「Android 48dp 合规」**；原生交付必须按右列验证，并保留真机证据。

**采集**：`node scripts/check-ui.mjs --url <file:///...|http://...> [--url ...] --tap 48 --font-min 12` 输出 JSON 与退出码，JSON 标注 `unit: css-px`；多字体档用多个 `--url`（如 `?fs=13`）各跑一次。它只做**页面级客观采集**，不替代视觉评审。**边界**：只检查当前 URL 的可见状态；弹层、空态、错误态、折叠区需要先导航/展开，或用项目交互脚本覆盖，不能只看首页。

### 🔴 业务断言必须独立推导

- 测试从**规格 + fixture** 重新计算期望值，**不得复制 UI 里手写的顺序 / 数值 / 文案**当预期。
- 至少有一条断言验证「DOM 顺序 / 数值 = 规格重算结果」，而不只是「两种排序不同」——后者在数据自相矛盾时仍会通过。
- **UI 自报的「通过」不能替代项目级断言**：页面里显示的等级、排序、金额、日期等业务结果，必须由独立测试重算并比对。
- 发现门槛与规格冲突：先改规格或报告，**不静默降低阈值**；测试通过不等于业务正确。

## 验证清单

每次产出HTML后，按这个清单做一遍：**L1 只跑受影响屏/状态的最小矩阵（阈值不变）；L2/L3 按完整清单。**

### 1. 浏览器渲染检查（必做）

最基础：**HTML能不能打开**？在macOS上：

```bash
open -a "Google Chrome" "/path/to/your/design.html"
```

或者用Playwright截图（下一节）。

### 2. 控制台错误检查

HTML文件里最常见的问题是JS报错导致白屏。用Playwright跑一遍：

```bash
# 在 skill 根目录执行（ZCode 下为 ~/.zcode/skills/designwise/）
python3 scripts/verify.py path/to/design.html
```

这个脚本会：
1. 用headless chromium打开HTML
2. 截图保存到项目目录
3. 抓取控制台错误
4. 报告status

详见`scripts/verify.py`。

### 3. 多视口检查

如果是响应式设计，抓多个viewport：

```bash
python verify.py design.html --viewports 1920x1080,1440x900,768x1024,375x667
```

### 4. 交互检查

Tweaks、动画、按钮切换——默认的静态截图看不到。**建议让用户自己开浏览器点一遍**，或者用 Playwright 录屏（录屏在创建 context 时配置，不是 `page.video.record()`）：

```python
context = browser.new_context(
    record_video_dir="videos/",
    record_video_size={"width": 1280, "height": 720},
)
page = context.new_page()
page.goto(url)
page.click("#toggle")
assert page.locator("#panel").is_visible()   # 关键动作 + 结果断言
context.close()  # 关闭 context 后才落盘视频
```

录屏只是证据，不等于功能验证：必须有关键动作与结果断言；没有断言的视频不能作为「交互正常」的证明。

### 5. 幻灯片逐页检查

Deck类HTML，一张张截：

```bash
python verify.py deck.html --slides 10  # 截前10张
```

生成 `deck-slide-01.png`、`deck-slide-02.png`... 方便快速浏览。

## Playwright Setup

首次使用需要：

```bash
# 如果还没装
npm install -g playwright
npx playwright install chromium

# 或者Python版
pip install playwright
playwright install chromium
```

如果用户已经全局安装 Playwright，直接用即可。

## 截图最佳实践

### 截完整页面

```python
page.screenshot(path='full.png', full_page=True)
```

### 截viewport

```python
page.screenshot(path='viewport.png')  # 默认只截可见区域
```

### 截特定元素

```python
element = page.query_selector('.hero-section')
element.screenshot(path='hero.png')
```

### 高清截图

```python
page = browser.new_page(device_scale_factor=2)  # retina
```

### 等动画结束再截

```python
page.wait_for_timeout(2000)  # 等2秒让动画settle
page.screenshot(...)
```

## 把截图发给用户

### 本地截图直接打开

```bash
open screenshot.png
```

用户会在自己的 Preview/Figma/VSCode/浏览器 里看。

### 上传图床分享链接

如果需要给远程协作者看（比如 Slack/飞书/微信），让用户用自己的图床工具或 MCP 上传截图，拿到一个永久链接，可以粘贴到任何地方。

## 验证出错时

### 页面白屏

控制台一定有错。先检查：

1. React+Babel script tag的integrity hash对不对（见`react-setup.md`）
2. 是不是`const styles = {...}`命名冲突
3. 跨文件的组件有没有export到`window`
4. JSX语法错误（babel.min.js不报错，换babel.js非压缩版）

### 动画卡

- 用Chrome DevTools Performance tab录一段
- 找layout thrashing（频繁的reflow）
- 动效优先用`transform`和`opacity`（GPU加速）

### 字体不对

- 检查`@font-face`的url是否可访问
- 检查fallback字体
- 中文字体加载慢：先显示fallback，加载完再切换

### 布局错位

- 检查`box-sizing: border-box`是否全局应用
- 检查`*  margin: 0; padding: 0`reset
- Chrome DevTools里打开gridlines看实际布局

## 验证=设计师的第二双眼

**永远要自己过一遍**。AI写代码时经常出现：

- 看起来对但interaction有bug
- 静态截图好但scroll时错位
- 宽屏好看但窄屏崩
- Dark mode忘了测
- Tweaks切换后某些组件没响应

**最后1分钟的验证可以省1小时的返工**。

## 常用验证脚本命令

```bash
# 基础：打开+截图+抓错
python verify.py design.html

# 多viewport
python verify.py design.html --viewports 1920x1080,375x667

# 多slide
python verify.py deck.html --slides 10

# 输出到指定目录
python verify.py design.html --output ./screenshots/

# headless=false，打开真实浏览器给你看
python verify.py design.html --show
```

## 视频产物硬校验（verify-video.sh）

渲染出的 MP4/成片不靠肉眼过，用脚本硬校验（HTML 合成侧的校验由 `hyperframes check` 五门审计负责，这个脚本只管产物侧）：

```bash
# 成品（默认要求有音轨）
bash scripts/verify-video.sh final.mp4 --duration=22 --fps=60 --width=1920 --height=1080

# 无声中间产物
bash scripts/verify-video.sh raw.mp4 --duration=10 --fps=60 --no-audio

# 刻意黑场开场的电影风
bash scripts/verify-video.sh film.mp4 --duration=30 --fps=60 --allow-black-open
```

检查项：分辨率/帧率、时长误差（±2%）、audio stream 存在性（无音轨=半成品铁律的机器执行）、首尾黑帧（blackdetect，录制起点偏移/loop 回跳的典型症状）、LUFS 响度（成品目标 -14±4）。exit code 非 0 就不许交付。
