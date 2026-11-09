# 组件与产物规范

> **读这份文档的时机**：要选起手组件、决定产物命名与目录、或做交付前自检时。
> **路径约定**：`assets/`、`scripts/` 均相对本 skill 根目录。

---

## 1. 起手组件（`assets/`）

| 文件 | 何时用 | 提供 |
|---|---|---|
| `ios_frame.jsx` | iOS App 原型 | iPhone 15 Pro 精确规格：bezel、Dynamic Island（124×36）、status bar、Home Indicator、content 安全区 |
| `android_frame.jsx` | Android App 原型 | 设备 bezel、状态栏、导航栏、圆角与安全区 |
| `design_canvas.jsx` | 并排展示 ≥2 个静态变体 | 带 label 的网格布局 |

**动效不依赖组件库**：加载、过渡、反馈用 CSS transition/animation 或平台原生动效实现；必须尊重 `prefers-reduced-motion`，不引入时间轴引擎。

**用法**：Read 对应资产文件 → 整段 inline 进 HTML 的 `<script type="text/babel">` → 你的屏组件放进设备框。

**硬规则**：iOS / Android 设备框**必须**用对应组件，**禁止手写** Dynamic Island、status bar、home indicator、bezel 与圆角外壳；自己写 99% 会撞位置 bug（详见 `references/app-prototype.md` §5）。

**范围**：本 skill 只服务 App UI。浏览器窗口、macOS 窗口、光标叙事组件不在此列。

---

## 2. 产物与命名

- 原型主文件：`prototype/index.html`；命名描述性（`onboarding-v2.html`），不用 `final-final`。
- 大改版保留旧版：`index.html` → `index-v1.html`，便于并排比较。
- 单文件超过 ~1000 行再拆 `components.jsx` + `data.js`，并在交付说明里给启动命令。
- 产物放项目目录，不散落到 `~/Downloads`。
- 状态位置（当前屏、Tab、开关）需要刷新不丢时存 `localStorage`。
- 交付前必须真实渲染并截图（`scripts/verify.py` 或 Playwright），**不靠读源码判断视觉效果**。

### 2.1 交付物数量与设计方向数量无关

方向固定 **3 个**（流程要求），方向选定后的交付物数量由**任务范围与验收要求**决定：

- 多个页面与完整流程：入口、列表、详情、状态页、异常页
- 多尺寸与多设备适配：手机 / 平板 / 折叠屏，按真实断点
- 多个状态：加载、空、错误、禁用、选中、超长文本、键盘弹出
- 组件与变体：按钮/输入/卡片的实际使用档位
- 素材导出：图标多尺寸、商店素材、各端切图
- 交付格式：HTML 原型 / PNG 基准图 / 交付包（`handoff/`）

**反向约束**：不因方向多就扩大范围，也不把多页面、多状态当成「多个设计方向」。

---

## 3. 水印

**默认不加任何第三方 skill 水印。** 原型、截图、素材默认是干净成品，不附加「Created by …」或工具署名——那是交付污染。

- 仅用户明确要求署名时才加（用户自己的品牌/作者名）。
- 第三方品牌的非官方致敬作品，可加「非官方出品 ·」前缀防 IP 争议——属用户决策，不默认。
- 版权与许可信息不受影响：本 skill 的 MIT 与致谢见 `LICENSE` / `README.md`；产出物版权归用户。

---

## 4. 版本自检（静默）

读本 skill 目录下的 `.last-update-check`（一行 `YYYY-MM-DD`）。存在且距今 <30 天 → 直接干活，不提更新。

到期或不存在时：

1. 本目录不是 git 克隆 → 写入今天日期，跳过。
2. 只检查**本仓库**状态：`git -C <本目录> status --short` 与 `git -C <本目录> rev-parse HEAD`。
3. 把今天日期写入 `.last-update-check`。
4. **不做上游版本对比、不提示合并上游**——本 skill 独立维护，无上游同步关系；发现对外部仓库的隐式依赖按缺陷处理。

> 运行时副本的同步状态由 `scripts/sync_runtime.py --check` 判定，与本自检无关。
