# ZCode 宿主适配

> **读这份文档的时机**：要在 ZCode 里跑完整流程、要确认某个能力用哪个入口、或同步运行时副本时。
> **一句话立场**：**能力契约见 `references/runtime-adapters.md`；本文只填 ZCode 的具体载体与边界。**

---

## 1. 宿主映射

| 能力 | ZCode 入口 | 边界 |
|---|---|---|
| 工程执行 | 当前 Agent（Read / Write / Edit / Bash / Agent） | 设计与验收由主 Agent 负责；子 Agent 只用于可拆分的并行调查或独立只读复核 |
| 真实生图 | `python3 scripts/zcode_image.py` | 本 skill 自带适配器，不依赖其他 skill |
| **设计判断（阶段 1/3）** | ZCode 主 Agent 读真实图片、渲染截图与运行结果，按 `SKILL.md` §4 判据决策 | 不外包给远程模型；可选派 ZCode 内置子 Agent 做只读复核 |
| 任务治理（可选） | `~/.zcode/skills/copilot/scripts/`（合同/状态/证据/收口） | 本地脚本、不调远程模型；**不做设计裁决**；不是普通开发前置门 |
| 浏览器渲染与截图 | `scripts/verify.py`（需 playwright）或本机 headless Chromium | 见 §3 实测状态 |
| 真机安装与运行 | **只用** `~/.zcode/skills/app-testing/runtime/mi6-verify/adb-auto-install.sh` | **禁止裸 `adb install`**；多台设备在线即停 |
| 全局规则 | `~/.zcode/AGENTS.md` | 安全、授权、Git、委派、记忆、联网纪律以它为准 |

---

## 2. 两个适配器的硬边界

### 2.1 `scripts/zcode_image.py`

```bash
python3 scripts/zcode_image.py --health                       # 零成本探测；默认 2.6 缺失时退出 2
python3 scripts/zcode_image.py --prompt "<中文提示词>" --out out.webp \
  --profile premium --size 1024x1536 --fit cover \
  --output-format webp --compression 82 \
  --meta-out out.meta.json [--ref ref.png] [--n 2]
```

- OpenAI 兼容 `/v1/images/generations`；带 `--ref` 走 `/images/edits`。**baseUrl 契约：配置里的 base 必须已包含 `/v1`**（脚本直接拼 `/images/...` 与 `/models`，不自动补前缀）。
- 默认 `--profile final` = `gpt-image-2.6-sunburst` / complexity `high` / quality `high`；`premium`（xhigh）、`max`、`explore`（Flare）、`draft` 见 `SKILL.md` §6.1。`--model`/`--complexity`/`--quality` 可逐项覆盖。
- `--size` 与 `--output-format` 是请求；当前 CPA 网关可能近似画布、把格式归为 PNG，脚本用 Pillow 适配并回读校验。网关响应 `quality` 与请求不一致会告警，不能当生效证据。
- 返回非图片字节、`b64_json` 缺失、魔数或完整性校验失败 → **非零退出，不写占位文件**；模型失败不静默回退旧模型。
- 凭据：优先 `ZCODE_CPA_BASE_URL` + `ZCODE_CPA_API_KEY`，否则读 `~/.zcode/v2/provider_config.json`（可用 `ZCODE_PROVIDER_CONFIG` 改路径）。**不打印、不落盘、不进 prompt、不进 metadata。**

### 2.2 `scripts/zcode_vision.py`（非流程能力，默认不用）

```bash
python3 scripts/zcode_vision.py --health
python3 scripts/zcode_vision.py --confirm-gpt-review \
  --image a.png --image b.png --prompt "<逐张事实观察 + 疑问 + 依据>"
```

- 只接受磁盘真实图片（存在性、大小、magic number 校验）；文字或 base64 字符串直接拒绝。
- **设计判断仍在 ZCode**：本脚本只在用户点名要外部第二意见时提供补充观察；输出只作为**待核实的观察**，不得直接采纳为方向或评审结论，**不是**设计批准、**不是** Gate、**不是** Copilot 正式 REVIEW，缺它不影响任何阶段推进。
- 状态非 completed、带 `incomplete_details` 或输出被截断 → 报告「未获得外部观察」，按缺证处理。

---

## 3. 能力核验方式（现场探测，不记录快照）

本文件**不记录任何机器的能力快照**：路径、Python 环境、浏览器版本与设备连接状态都随机器与时间变化，写进分发文档会在其他机器上直接误导。执行前按下表核验，结论以当场输出为准。

| 能力 | 核验命令 | 失败时 |
|---|---|---|
| 真实生图 | `python3 scripts/zcode_image.py --health`，再真实出一张 | 报告限制并暂停生图，不换链路冒充 |
| 概念差异实测 | `python3 scripts/direction_divergence.py --help`（需 Pillow） | 缺 Pillow → 报告；改用人工并排比对并标注"未实测" |
| 原生只读复核（可选） | 派 ZCode 内置子 Agent，确认其不修改文件 | 不可用 → 主 Agent 自评并说明"未经独立复核" |
| HTML 渲染 | `node scripts/check-ui.mjs --url file:///path/index.html`（本机 Chrome/Chromium + Node ≥22）；`scripts/verify.py` 才需要 Playwright | 用可用的浏览器路径，或报告渲染缺口 |
| 图片处理 | `python3 -c "import PIL; print(PIL.__version__)"` | 用 `scripts/` 里不依赖 Pillow 的路径，或报告缺口 |
| 对比度 | `python3 scripts/check-contrast.py <pairs>`（纯 stdlib） | 视为验证工具缺失，不声称已测 |
| 真机 | `adb devices` 现场核对 | 无设备 → `PARTIAL` / `BLOCKED`；装包只走 `adb-auto-install.sh` |

---

## 4. 源码仓库与运行时副本

| 角色 | 路径 | 规则 |
|---|---|---|
| **源码（唯一源头）** | 本项目 git 工作区 | 所有修改只在这里做 |
| **运行时副本（构建产物）** | `~/.zcode/skills/designwise` | 只由 `scripts/sync_runtime.py` 单向写入 |

```bash
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --check
python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply
```

- 默认不删除副本多余文件；`--prune` 仅在明确要清理时使用。
- 排除项：`.env*`（保留 `.env.example`）、`.git`、`node_modules`、`design-demos`、`__pycache__`、开发资产（`AGENTS.md`、`scripts/test_*.py`、`.zcode/`）。
- **改副本 = 下次同步被覆盖**：紧急修改先搬回源码再单向同步，不做双向合并。
- 漂移是静默的，只有 `--check` 能看见。

---

## 5. 不依赖其他 skill

DesignWise 的运行只依赖本仓库文件与 ZCode 宿主能力：

| 曾经的外部依赖 | 现状 |
|---|---|
| `huashu-gpt-image`（生图与方法论） | 方法论已吸收进 `references/image-generation.md`；生图走自带 `zcode_image.py`；**不再引用、不注册、不探测** |
| `copilot`（任务治理） | 长任务/跨会话/高风险时可选用其合同、状态与证据脚本；**不做设计裁决、不调远程模型、不是前置门**；不假设其内部实现 |
| huashu 上游仓库 | 只保留 MIT 代码的必要署名与许可证；无同步、无继承、无运行时关联 |

> 其他 skill 的改动、升级或退场不应影响 DesignWise 的流程；若发现隐式依赖，按缺陷处理。
