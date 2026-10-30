# 宿主环境适配（ZCode · 自 Reasonix 迁移）

> **ZCode 适配（自 Reasonix 迁移 · 2026-10-24）**：本文件收纳 `SKILL.md` 原「跨 Agent 环境适配说明」
> 「弱 runtime 降级模式」两节（**内容逐字保留**），并追加 ZCode 宿主的具体映射。迁入 ZCode 时因
> SKILL.md 有 100,000 字节读取上限，这两节整体搬到此处，正文留指针。

---

## 跨 Agent 环境适配说明

本 skill 设计为 **agent-agnostic**——Claude Code、Codex、Cursor、Trae、OpenClaw、Hermes Agent 或任何支持 markdown-based skill 的 agent 都可以使用。以下是和原生「设计型 IDE」（如 Claude.ai Artifacts）对比时的通用差异处理方式：

- **没有内置的 fork-verifier agent**：用 `scripts/verify.py`（Playwright 封装）人工驱动验证
- **没有 asset 注册到 review pane**：直接用 agent 的 Write 能力写文件，用户在自己的浏览器/IDE 里打开
- **没有 Tweaks host postMessage**：改成**纯前端 localStorage 版**，详见 `references/tweaks-system.md`
- **没有 `window.claude.complete` 免配置 helper**：若 HTML 里要调 LLM，用一个可复用的 mock 或让用户填自己的 API key，详见 `references/react-setup.md`
- **没有结构化问题 UI**：在对话里用 markdown 清单问问题，参考 `references/workflow.md` 的模板

Skill 路径引用均采用**相对本 skill 根目录**的形式（`references/xxx.md`、`assets/xxx.jsx`、`scripts/xxx.sh`）——agent 或用户按自身安装位置解析，不依赖任何绝对路径。

### 源码仓库 vs 运行时副本（唯一源头与单向同步）

| 角色 | 路径 | 谁改 |
|---|---|---|
| **Git 源码（唯一源头）** | 项目的 git 工作区（如 `/media/vdb/projects/designwise`） | 所有修改**只在这里**做；提交也在这里 |
| **运行时副本（构建产物）** | agent 的 skills 目录（ZCode 下为 `~/.zcode/skills/designwise`） | **只由 `scripts/sync_runtime.py` 单向写入**；不直接编辑 |

**同步命令**（在源码仓库根目录执行）：

```bash
# 默认只检查：有漂移时退出码 1，并列出缺失 / 不同 / 目标多出的文件
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --check

# 确认后单向写入缺失/不同的文件；默认不删除目标多出的文件
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply

# 仅在明确要删除副本多余文件时加 --prune（危险）
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply --prune
```

脚本排除 `.env` / `.env.*`（保留 `.env.example`）、`assets/personal-asset-index.json`、`.git`、
`node_modules`、`.reasonix`、`design-demos`、`__pycache__` 与字节码；写入使用临时文件 + 原子替换。
目标必须含 `SKILL.md` 的 `name: designwise`；首次安装到空目录时加 `--force`。
**ZCode 宿主适配（frontmatter、100 KB 拆分、适配器、路径改写）本身已进仓库**，所以同步不再需要
手工合并，也不会冲掉适配。

**纪律**：**改副本 = 下次同步被覆盖**。若在副本上做了紧急修改，先把它搬回源码仓库（`git diff` 核对）
再走单向同步，**不做双向合并**。漂移是静默的，只有 `--check` 能看见。

> 🔧 **不确定某个能力在当前环境有没有？** 别凭印象自我降级。按 `references/runtime-adapters.md` 的「能力 → 载体」映射表**试一次**，缺失时用表里的替代方案。那张表把工具名与平台名解耦，所以换任何 agent 都不必改 skill——这正是本节的落地细则。

### 弱 runtime 降级模式

**触发判定**（按**已观察到的能力/资源限制**，不按模型品牌）：无 spawn subagent 能力 / 实测上下文不足以完成当前任务 / 已多次因窗口耗尽中断。为什么：按满血流程跑，弱 runtime 中途爆上下文或偷工，产出反而更差（issue #2/#6/#41 用户复现不出效果的根因）。**不得仅因驱动模型不是 Claude 就降级。**

**降级动作（按吃紧程度逐级启用）**：
1. **L2 例外通路**的多套并行 → 串行（N 按方案数量，默认 1 套）：按上文 Phase 4「不支持 spawn subagent 的 runtime」规则执行（已有规则，直接引用）
2. 多方案分支串行仍吃紧 → 收成 1 个主版 + 1 个变体；变体必须在**布局骨架或信息组织**上有一处真实结构差异，不得只换色板/排印冒充「方向」（为什么：布局重写最耗上下文，但只换皮不构成用户可比较的方向；**单一方案默认路径不受本条影响**）
3. references 只读当前任务对应的 1 个文件，不全读（为什么：路由表的意义就是按需加载，全读必爆窗口）
4. deck 默认单文件架构（`assets/deck_stage.js`）（为什么：多文件 + 概览墙依赖多轮文件操作，弱 runtime 容易半途而废留下坏 deck）
5. 检查点问答**不可整体跳过**：只可把可自行补齐的低风险假设写入 assumption 清单。**方向选择（多方案分支）、授权边界、真实视觉确认仍必须由用户完成**，不因上下文紧张而降级；单一方案由 agent 定方向并标注 `agent 决策`，用户看完真实视觉可否决（见 `SKILL.md`「项目规则优先」）。

**原则一句话**：降级牺牲多样性和流程，绝不牺牲反 slop 底线和真实资产协议。
---

## ZCode 宿主映射（迁移实测 · 2026-10-24）

本节是原「跨 Agent 环境适配说明」在 ZCode 上的落地。**原表照旧生效**，下表只是把 ZCode 的实际
载体填进去；两者冲突时以这里的实测为准。

| 能力 | Reasonix 载体（原文） | ZCode 载体（已实测） |
|---|---|---|
| 并行多方向 / 子代理 | `task` / `fleet` | **ZCode Agent 工具**（单条消息内并发派发多个 `Agent`） |
| 计划模式 | Reasonix Plan | **ZCode plan 权限模式**（`EnterPlanMode`） |
| 浏览器验证 / 截图 | 内置 browser 工具 | `scripts/verify.py`（需 playwright）或 headless Chromium 直调（见下） |
| 真实生图 | `huashu-gpt-image` 的 `gen_via_cpa.py` | **`scripts/zcode_image.py`**（本 skill 自带；方法论按已迁移的 `~/.zcode/skills/huashu-gpt-image/` 执行） |
| 真实像素评审（Gate 1/2） | `copilot` 的 REVIEW 通道 | **默认原生视觉自检**（主模型直接读真实图片）；**外部 GPT** 仅用户明确授权后走 `scripts/zcode_vision.py --confirm-gpt-review`（直连 CPA Responses API 的 `input_image`，只收真实图片；无台账/审计，非 copilot 正式 REVIEW）；**仅点名 Copilot 时**才用完整 `copilot` 技能（REVIEW + 证据桥接 + 台账 + 审计） |
| 全局规则来源 | Reasonix 自有规则 | `~/.zcode/AGENTS.md` |

### 评审与生图的默认路由（2026-10-29 收口）

原 skill 依赖 `huashu-gpt-image`（生图）与 `copilot`（视觉评审）两个全局技能。两者已于 2026-10-24
迁入 ZCode（`~/.zcode/skills/huashu-gpt-image/`、`~/.zcode/skills/copilot/`）。

- **Gate 1 / Gate 2 默认做原生视觉自检**：主模型直接读真实候选图 / 渲染截图，按 Gate 清单判断，结论标注「自检」，**不得写成独立 GPT 裁决**。
- **外部 GPT 视觉评审**：仅当用户明确授权 GPT 评审通道（点名 GPT / GPT 视觉评审 / Copilot / 正式 REVIEW）时启用；调用必须带 `--confirm-gpt-review`。**未授权时不得用它绕过 Copilot 的启用限制**。
- **Copilot 正式 REVIEW**：仅用户点名 Copilot / `copilot` Skill / 正式 REVIEW 时。
- 若任务强制要求独立 GPT 裁决而本轮无授权 → **报告阻塞**，不用原生自检冒充。

```bash
# 仅在用户明确授权 GPT 评审通道后
python3 scripts/zcode_vision.py --confirm-gpt-review \
  --image candidate-1.png --image candidate-2.png \
  --prompt "<每张图对应的方向 / 角色 + 推荐 + 依据 + 风险>"
```

  它只接受磁盘上的真实图片（png/jpeg/webp/gif，按魔数校验），一次可送多张；默认模型
  `gpt-6-astra-high`。**没有复核台账、审计日志与轮次限制，不构成 copilot 的正式 REVIEW**；
  使用时如实标注证据范围，不得把它说成完整 REVIEW。

- **用户明确点名 Copilot 时才走 copilot 正式 REVIEW**：

```bash
COP=~/.zcode/skills/copilot/scripts
# 1) 证据桥接：真实图片只落元数据 + 机器可读引用（不落 base64）
python3 "$COP/bridge_evidence.py" \
  --image 'rendered.png::Gate2 渲染截图' --image 'concept.png::已确认概念图' \
  --out /tmp/copilot/evidence.md --manifest /tmp/copilot/evidence.json
# 2) 零工具 GPT 评审：一次性视觉评审免台账；多轮/文本评审必须 --review-ledger
python3 "$COP/call_gpt.py" --mode REVIEW --one-shot-visual-review \
  --prompt-file /tmp/copilot/task.md --evidence /tmp/copilot/evidence.md \
  --audit-log ~/.zcode/skills/copilot/.audit/copilot.jsonl --out /tmp/copilot/reply.md
```

  没有用户点名时，**不得**因进入 Gate 1 / Gate 2、需要视觉审核、任务复杂、`zcode_vision.py`
  失败或宿主认为 Copilot 更合适而自动切到这条通路。

- **失败与缺证**：`zcode_vision.py` 非 0 退出、响应状态非 completed、带 `incomplete_details` 或
  输出被截断时，如实报告「本轮未获得视觉裁决」，按缺证处理（Gate 1 交候选图让用户直接选），
  不伪造 PASS、不静默换链路、不自动重试；不得用代码复核子智能体或其他不支持图像输入的通道冒充视觉评审。

- **代码 / 变更的独立复核**仍按 `~/.zcode/AGENTS.md` §5《委派与独立复核》由原生子智能体的独立上下文承担；它不具备视觉评审能力，
  不用于 Gate 1 / Gate 2。

### 生图适配器（本 skill 自带，已实测出图）

生图方法论按已迁移的 `~/.zcode/skills/huashu-gpt-image/` 执行（prompt 方法论、风格库、单图/批量、
错误处理全部沿用）；本 skill 的 `scripts/zcode_image.py` 仍是 ZCode 默认出图入口：

```bash
# 零成本探测（不出图、不计额度）
python3 scripts/zcode_image.py --health

# 真实生图（拿回真 PNG；失败非零退出，不返回假图）
python3 scripts/zcode_image.py --prompt "<英文提示词>" --out candidate-1.png
python3 scripts/zcode_image.py --prompt "<提示词>" --out v.png --n 2      # → v-1.png v-2.png
python3 scripts/zcode_image.py --prompt "<提示词>" --out refined.png --ref concept.png
```

### 两个 ZCode 适配器（本 skill 自带，已实测出图 / 已实测评图）

原 skill 依赖 `huashu-gpt-image`（生图）与 `copilot`（视觉评审）两个全局技能。两者已于 2026-10-24
迁入 ZCode（见上节路由）；本 skill 自带的两个适配器**继续保留**——`zcode_image.py` 仍是默认
生图入口，`zcode_vision.py` 是 **用户授权后的外部 GPT 评审入口**（默认路径是原生视觉自检）。
它们都是真的调用接口，不是占位实现：

```bash
# 零成本探测（不出图、不计额度）
python3 scripts/zcode_image.py --health
python3 scripts/zcode_vision.py --health

# 真实生图（拿回真 PNG；失败非零退出，不返回假图）
python3 scripts/zcode_image.py --prompt "<英文提示词>" --out candidate-1.png
python3 scripts/zcode_image.py --prompt "<提示词>" --out v.png --n 2      # → v-1.png v-2.png
python3 scripts/zcode_image.py --prompt "<提示词>" --out refined.png --ref concept.png

# 外部 GPT 评审（仅用户明确授权后；注明无台账/审计，非 copilot 正式 REVIEW）
python3 scripts/zcode_vision.py --confirm-gpt-review --image a.png --image b.png --prompt "<评审要求>"
```

**两个适配器的硬边界（不可绕过）**：
- `zcode_vision.py` **只接受磁盘上的真实图片文件**（校验文件存在、大小、图片 magic number）。
  只给文字、给 base64 字符串、给不存在的路径 → 直接拒绝并非零退出。
  **禁止用文字描述冒充视觉评审**——这是原 skill「不得把搜索图片/文字提示词冒充真图」规则的 ZCode 落地。
  copilot 正式 REVIEW 路径（用户点名时）同样只收真实像素（`bridge_evidence.py` 只落元数据，`call_gpt.py` 校验 sha256+魔数后内联）。
- `zcode_image.py` 拿不到 `b64_json` 或以非图片字节返回 → 非零退出，**不写占位文件**。
- 两者凭据优先读 `ZCODE_CPA_BASE_URL` + `ZCODE_CPA_API_KEY`（两者都设置时，无需本机配置文件）；
  否则读 `~/.zcode/v2/provider_config.json`（可用 `ZCODE_PROVIDER_CONFIG` 改路径）。
  **不打印、不落盘、不进 prompt**；
  迁移后的 copilot 凭据解析链为：环境变量 `CUSTOM_127_API_KEY` → Reasonix `.env`（同机兼容）→ 同一份 provider 配置。

### 本机能力现状（2026-10-24 实测）

| 能力 | 状态 |
|---|---|
| HTML → PNG 渲染 | ✅ 可用（`~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome --headless=new --screenshot`） |
| 真实图像生成 | ✅ 已出图（`gpt-image-2.5`，1536×1024 PNG，1.1 MB，sha256 校验） |
| 真实像素评审 | ✅ 已出结论（`scripts/zcode_vision.py`，`gpt-6-astra-high`，两张图逐项描述 + 推荐 + 风险） |
| PDF / PPTX 导出脚本 | ⚠️ **未验证**——本机缺 `playwright`(py+node)、`pdf-lib`、`pptxgenjs`、`sharp`、`python-pptx`。`scripts/verify.py` 同样受缺 `playwright` 影响 |
| 动画渲染 / 音频链路 | ⚠️ **未验证**——`ffmpeg` 有（`/usr/bin/ffmpeg`）、`PIL`/`numpy` 有；但 TTS key（豆包）未配、HyperFrames CLI 未装 |
| 对比度校验 `check-contrast.py` | ✅ **已验证**（纯 stdlib，实测拦下过一次 3.40:1 的阻断项） |
| `check-skill.py` 结构自检 | ✅ **已验证**（结构完整、无悬空引用；文档/引用数随内容变化，以实际输出为准） |

### 宿主适配分层与同步约束

**通用方法论（所有 runtime 共用）**：`SKILL.md`、`references/*`、以及渲染 / 导出 / 校验脚本。
它们不依赖 ZCode 专有配置，其他 runtime 按 `references/runtime-adapters.md` 映射能力即可。

**ZCode 宿主适配（可选，不是其他 runtime 的运行要求）**：

1. `SKILL.md` frontmatter 增加 `when_to_use`，`description` 控制在 1024 字符以内
2. `SKILL.md` 保持在 100,000 字节以内；超出部分整块搬到 `references/`，正文留指针
3. 宿主专属路径改写（`~/.reasonix`、`~/.claude` → 当前 runtime 的 skills 目录）
4. `scripts/zcode_image.py` / `scripts/zcode_vision.py`：默认读取 ZCode provider 配置；
   也可用 `ZCODE_CPA_BASE_URL` + `ZCODE_CPA_API_KEY` 完全覆盖，**不要求本机存在 `~/.zcode`**。
   适配器不打印、不落盘、不写入 prompt 任何密钥；不把本机配置路径写成通用运行要求。

**没有等价生图 / 视觉评审能力的 runtime**：按 `runtime-adapters.md` 找替代；替代也没有时，
如实报告该环节未验证并暂停（可交付完整 prompt 或候选图给用户），**不得把缺证写成 PASS**。

**同步**：只使用 `scripts/sync_runtime.py`（`--check` / `--apply`），不手工改副本。
ZCode 适配文件本身也在仓库中，因此整树单向同步是安全的。

### 为 100 KB 上限移入 references 的内容

下列内容**已随源码提交**，并由 `scripts/sync_runtime.py` 一起同步到运行时：

| 搬到哪 | 原文来自 SKILL.md 的哪一节 | 是否逐字 |
|---|---|---|
| `references/routing-table.md` | `## References路由表`（完整路由表） | 逐字 + ZCode 路由更新 |
| `references/components-and-output.md` | `## Starter Components` + `## 产出要求` + `## 水印` + `## 版本自检` | 逐字 |
| `references/zcode-host.md`（本文件） | `## 跨 Agent 环境适配说明` + `## 弱 runtime 降级模式` | 逐字 + 追加 ZCode 映射 |
| `references/direction-gpt-path.md` | Phase 3.7 起的逐条 GPT 通路硬规则 | 规则保留，措辞按 ZCode 通道更新 |

2026-10-27 体积收口又把以下速查/细节**逐字移入**对应 references（SKILL.md 现约 89 KB）：
App/iOS → `app-prototype.md`；产品价值 → `product-value.md`；异常处理 → `workflow.md`；
反 slop 速查 → `content-guidelines.md`；技术红线 → `react-setup.md`；工作室/探索心态 →
`design-philosophy.md`。入口保留硬约束摘要与指针。

另外，SKILL.md 里 Step 1 的 GPT 通路大段（约 3.3 KB）与 Phase 3.6 的重复描述做了**压缩**（转为指针 +
关键约束重申），**规则本身没有删除**——完整版都在 `references/gpt-visual-workflow.md` 与
`references/direction-gpt-path.md`。
