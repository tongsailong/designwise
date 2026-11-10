# ZCode 宿主适配

> **读这份文档的时机**：要在 ZCode 里跑完整流程、要确认某个能力用哪个入口、或同步运行时副本时。
> **一句话立场**：**能力契约见 `references/runtime-adapters.md`；本文只填 ZCode 的具体载体与边界。**

---

## 1. 宿主映射

| 能力 | ZCode 入口 | 边界 |
|---|---|---|
| 工程执行 | 当前 Agent（Read / Write / Edit / Bash / Agent） | 设计与验收由主 Agent 负责；子 Agent 只用于可拆分的并行调查或独立只读复核 |
| 真实生图 | `python3 scripts/zcode_image.py` | 本 skill 自带适配器，不依赖其他 skill |
| 外部 GPT 视觉评审（授权后） | `python3 scripts/zcode_vision.py --confirm-gpt-review` | 只在用户明确授权 GPT 评审通道后使用；不等同 Copilot 正式 REVIEW |
| **方向选择（阶段 3）** | `~/.zcode/skills/copilot/scripts/bridge_evidence.py` + `call_gpt.py --mode CONSULT` | 送选必须带**真实图片**；由 Copilot 裁决，执行方不代选、不代写 |
| 浏览器渲染与截图 | `scripts/verify.py`（需 playwright）或本机 headless Chromium | 见 §3 实测状态 |
| 真机安装与运行 | **只用** `~/.zcode/skills/app-testing/runtime/mi6-verify/adb-auto-install.sh` | **禁止裸 `adb install`**；多台设备在线即停 |
| 全局规则 | `~/.zcode/AGENTS.md` | 安全、授权、Git、委派、记忆、联网纪律以它为准 |

---

## 2. 两个适配器的硬边界

### 2.1 `scripts/zcode_image.py`

```bash
python3 scripts/zcode_image.py --health                       # 零成本探测
python3 scripts/zcode_image.py --prompt "<中文提示词>" --out out.png \
  --size 1024x1536 --fit contain [--ref ref.png] [--n 2]
```

- OpenAI 兼容 `/v1/images/generations`；带 `--ref` 走 `/images/edits`。
- 默认模型以脚本为准（当前 `gpt-image-2.5`）；`--size` 是请求，最终像素用 `--fit cover|contain|stretch` 落地。
- 返回非图片字节、`b64_json` 缺失、魔数或完整性校验失败 → **非零退出，不写占位文件**。
- 凭据：优先 `ZCODE_CPA_BASE_URL` + `ZCODE_CPA_API_KEY`，否则读 `~/.zcode/v2/provider_config.json`（可用 `ZCODE_PROVIDER_CONFIG` 改路径）。**不打印、不落盘、不进 prompt。**

### 2.2 `scripts/zcode_vision.py`

```bash
python3 scripts/zcode_vision.py --health
python3 scripts/zcode_vision.py --confirm-gpt-review \
  --image a.png --image b.png --prompt "<逐张方向 + 推荐 + 依据 + 风险>"
```

- 只接受磁盘真实图片（存在性、大小、magic number 校验）；文字或 base64 字符串直接拒绝。
- 默认路径是**原生视觉自检**；此脚本是用户授权后的外部评审入口，**不是** Copilot 正式 REVIEW。
- 状态非 completed、带 `incomplete_details` 或输出被截断 → 报告「未获得视觉裁决」，按缺证处理。

---

## 3. 能力核验方式（现场探测，不记录快照）

本文件**不记录任何机器的能力快照**：路径、Python 环境、浏览器版本与设备连接状态都随机器与时间变化，写进分发文档会在其他机器上直接误导。执行前按下表核验，结论以当场输出为准。

| 能力 | 核验命令 | 失败时 |
|---|---|---|
| 真实生图 | `python3 scripts/zcode_image.py --health`，再真实出一张 | 报告限制并暂停生图，不换链路冒充 |
| Copilot CONSULT | 证据桥接 + `call_gpt.py` 一次真实调用，看审计 `model_identity_ok` | 停用该判断，按失败关闭处理 |
| HTML 渲染 | `node scripts/check-ui.mjs <file>`；需要 Playwright 时先 `import playwright` 试导入 | 用可用的解释器/浏览器路径，或报告渲染缺口 |
| 图片处理 | `python3 -c "import PIL; print(PIL.__version__)"` | 用 `scripts/` 里不依赖 Pillow 的路径，或报告缺口 |
| 对比度 | `python3 scripts/check-contrast.py <pairs>`（纯 stdlib） | 视为验证工具缺失，不声称已测 |
| 真机 | `adb devices` 现场核对 | 无设备 → `PARTIAL` / `BLOCKED`；装包只走 `adb-auto-install.sh` |
| 视频/音频/PPT 导出 | 不需要核验 | 已移出范围，相关脚本不随本 skill 分发 |

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
| `copilot`（方向选择） | 只按流程要求调用其 CONSULT 接口；不假设其内部实现 |
| huashu 上游仓库 | 只保留 MIT 代码的必要署名与许可证；无同步、无继承、无运行时关联 |

> 其他 skill 的改动、升级或退场不应影响 DesignWise 的流程；若发现隐式依赖，按缺陷处理。
