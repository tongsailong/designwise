# DesignWise 项目规则

> **作用域**：本文件只约束 **DesignWise 源码仓库**的维护工作，不描述 agent 执行设计任务的流程。
> **分发目标**：本文件与开发测试资产**不进入运行时 Skill 副本**（由 §2 的同步排除规则实现）。
> **现状提示**：排除规则生效前已存在于副本中的开发资产不会自动消失，处置见 §2 末尾。
> 全局 `~/.zcode/AGENTS.md` 的安全、授权、Git、委派、记忆与联网纪律照常生效；本文件只补项目特有约束，不重复、不放宽。

## 1. 定位与边界

- 本仓库是上游项目（huashu-design，MIT）的**独立二次开发分支**：保留其视觉方法论、风格库与资产协议，
  重构为 **GPT-first 的 App UI 单一标准流程**（产品理解 → 三方向概念图 → Copilot 方向选择 → HTML 原型 →
  素材 → 原生实现 → 真机验收）。**独立维护**：不跟随上游发布、不做运行时同步、不依赖其他 skill。
- **规则效力的完整排序只在 `SKILL.md`「项目规则优先」维护一处**，本文件不复述完整分层，只记维护侧结论：
  全局安全与授权硬约束**不得**被本项目规则或 DesignWise 放宽；使用方项目的产品原则与用户关键决策
  **优先于** DesignWise 的一般设计偏好；`references/` 只展开 `SKILL.md`，不另立独立规则；
  真冲突按规则所属职责判断，不机械套用单一排序。改效力关系时只改 `SKILL.md` 一处并同步本结论，
  其他文件（含 `references/product-value.md`、`references/routing-table.md`）只指向此处，不另立一套。
  **本节不编号，编号只存在 `SKILL.md` 的那一处**，避免出现第二套排序。
- **产品原则的权威在使用方项目，不在本仓库**。DesignWise 是通用能力，不替任何使用方项目定义产品原则
  （业务目标、优先级、商业化、广告、隐私、安全与合规边界都归使用方项目）；`references/product-value.md` 只在项目
  未定义原则时充当**默认方法**，项目定义后按项目执行且可更严。**不把其他项目的产品规则搬进本仓库**，
  也不在本文件增设产品原则条目。
- 非目标：幻灯片 / PPT / deck、视频 / 动画成片、配音 / 音频 / 音乐 / SFX、信息图 / 海报 / 封面等静态平面载体、
  生产级 Web App、需后端的系统、纯代码重构、图层级可编辑 PPTX。**App UI 是唯一载体**；HTML 是原型不是产品。

## 2. 真源与分发边界

- **真源 = 本仓库**。宿主 skills 目录下的 designwise 是**构建产物**，只由 `scripts/sync_runtime.py` 单向下发。
  不手改副本；副本上的紧急修改先搬回仓库再重新下发，**不做双向合并**。
- 仓库根、当前分支、远端列表、目标 skill 目录**每次执行现场核实**（`git rev-parse` / `git remote -v` /
  宿主 skills 目录），不沿用历史值。
- **开发资产不随分发**：`AGENTS.md`、`scripts/test_*.py` 与 `.zcode/` 是开发资产，由同步工具的排除规则挡在
  副本之外；`LICENSE`、`SKILL.md`、`README*.md`、`SECURITY.md`、`THIRD_PARTY_NOTICES.md`、`references/`、
  `assets/`、`demos/` 与运行所需的 `scripts/` 保持原有同步行为，**不得顺手扩大排除范围**。
- **排除是对称的**：被排除文件在源与副本两侧都不进入比对清单，因此排除生效前已存在于副本中的同类文件
  既不会触发漂移告警，也不会被 `--prune` 删除。这类历史遗留按类别和路径核实后单独报告，
  **清理需用户单独授权**；不得为了得到"零漂移"而调参、加临时特例或手工删副本文件。

## 3. 上游与许可证

- **上游只作历史来源，不是同步对象**：需要参考上游实现时逐项评估、选择性移植——先核实证据、版本与适用边界。
  **整体合并上游发布必须逐次取得用户明确批准**；不得为"跟上游对齐"引入本分支已下线的载体能力。
- **许可证义务（MIT，法定，不可省略）**：MIT 要求在**所有副本或实质性部分**中保留 `LICENSE` 的版权声明与
  许可文本。运行时副本、Releases、镜像、打包产物等任何分发形态都必须随附 `LICENSE`，不得删除、替换或
  删减其内容；同步排除规则不得把 `LICENSE` 排除在外。
- **移植代码必须单独标注**：从其他 MIT 项目移植的文件在 `THIRD_PARTY_NOTICES.md` 记录来源、版权与许可全文，
  并在文件头保留来源注释。当前移植项：`scripts/extract_grid.py`、`contact_sheet.py`、`chroma_key.py`
  （来自 huashu-gpt-image）。删除或改写这些文件时不得移除许可声明。
- **项目署名政策（本项目自定，不是许可证义务）**：两份 README 保留上游来源与致谢，区分"上游作者"与
  "本分支维护者"，不把上游作者的经验表述改写成本分支原创。此类要求不得被描述成许可证条款，
  也不因未写入 `LICENSE` 而失效。
- 生成的设计素材**不自动继承 MIT**；样张与风格名的使用边界见 `README.md`「上游项目与致谢」。

## 4. 目录职责

| 路径 | 职责 | 边界 |
|---|---|---|
| `SKILL.md` | agent 执行入口 + **流程与路由唯一权威**（0–7 阶段、证据门、质量红线） | 体量受限（§5），细则外置；不写维护规则 |
| `references/` | 方法论细则、阶段展开、宿主适配 | 不与 `SKILL.md` 争流程权 |
| `scripts/` | 可重复执行的工程能力（生图 / 图片处理 / 渲染验证 / 清单 / 同步） | 不放一次性调试脚本、个人数据；随副本分发 |
| `scripts/test_*.py` | **开发测试资产**（unittest，与脚本同目录） | 不承载运行时能力；**不随副本分发** |
| `assets/` | 起手组件（设备框、画布）与风格样张 | 不放个人真实素材（已 gitignore） |
| `demos/` | 能力演示（中英双版，仅 App UI 相关） | 不引入已下线的载体演示 |
| `README*.md` / `SECURITY.md` / `THIRD_PARTY_NOTICES.md` | 面向使用者、安全边界、第三方许可 | 不写内部研发过程 |
| `AGENTS.md`（本文件） | 维护者规则 | **不随副本分发**；不写设计执行流程 |

一句话：**AGENTS.md 管怎么维护，SKILL.md 管怎么执行，references 管怎么做得好，scripts 管能不能重复做对，
`test_*.py` 管改了有没有坏。**

## 5. 修改与验证

- 最小必要范围；不顺手重构、不批量格式化、不改任务外文案。未跟踪文件同受保护。
- **流程与阶段只有 `SKILL.md` 一个权威来源**；`references/routing-table.md`、`references/workflow.md`、
  `references/app-visual-workflow.md` 是其展开，口径冲突时以 `SKILL.md` 为准并修正展开侧。
- 以下改动要在**同一次变更**内同步展开副本与契约测试：
  - 阶段 / 流程 / 证据门 → `SKILL.md` + `references/app-visual-workflow.md` +
    `references/routing-table.md` + `references/workflow.md` + `scripts/test_skill_routing.py`
  - 生图或素材规则 → `references/image-generation.md` / `references/image-assets.md` +
    `scripts/test_asset_manifest.py`（改动清单工具时）+ `test-prompts.json`
  - 验收提示集 → `test-prompts.json` + `scripts/test_prompts_contract.py`
  - 对外可见的能力 / 安装 / 依赖 → `README.md` + `README.en.md`（+ `SECURITY.md` 若涉及出站或凭据）
- **宿主工具映射必须现场验证**：`SKILL.md` 的硬规则不得依赖未经验证的宿主工具名；工具命名与降级差异在
  `SKILL.md` 与 `references/runtime-adapters.md` / `references/zcode-host.md` 内解决。改硬规则时维护者必须
  确认该能力在当前宿主有可执行入口。本文件不复写任何宿主执行流程。
- 不削弱既有质量约束来换流程变短：阶段 2 的三方向、阶段 3 的 Copilot 裁决、48dp / 对比度 / 业务断言等
  硬门不得为了让流程更快而删除；局部迭代只省重新探索，不省验证。

### 验证门（改完必跑，结论写进交付说明）

在仓库根执行；同步目标目录每次现场核实后填入：

```bash
python3 scripts/check-skill.py                                      # 结构与引用：exit 0 才算过
python3 -m unittest discover -s scripts -p 'test_*.py' -t scripts   # 回归：exit 0，skip 需解释
python3 scripts/sync_runtime.py --to <skill 目录> --check           # 0 = 无漂移
```

- **标准是退出码 0 与"skip 有解释"，不是某个用例数**。用例数随开发变化，不得把当期快照写成永久门槛。
- **SKILL.md 体量预算**：当前按 **100,000 字节**（兼容性预算，尚不能宣称是宿主硬限制）与
  **98,000 字节**（项目预警线）两档掌握，以 `scripts/check-skill.py` 的实现为准；新增细则一律进 `references/`。
  修改任一阈值前必须先实测宿主读取行为，再同步修改自检脚本与相关文档，不能只改文案。
- `check-skill.py --strict` 的提示逐条判断：按 `.gitignore` 由 Releases 分发的大文件、以裸文件名互引的
  `references/*.md` 是**已知误报模式**，不构成缺陷，但每条都要有解释。
- **真机与生图的验收必须来自真实运行**：生成图必须是真实文件（可解码、有 sha256），真机证据必须来自授权
  安装入口的实际安装与截图；模拟图、静态示意图、源码推断都不算。设备不在线按 `PARTIAL` / `BLOCKED` 记录。
- 当前**不设 CI / 预提交钩子**，也不注册宿主 hook；验证以本地三条命令为准，门禁靠流程规则与脚本校验。

## 6. 交付

- 提交信息沿用仓库既有风格（如 `docs(designwise): …`、`feat(designwise): …`、`fix(designwise): …`），
  说明写清改了什么、为什么、验证了什么。
- 暂存范围、提交与推送的授权要求按全局规则执行，本文件不另立条款。项目侧补充：上游远端默认不作为推送
  目标；向本仓库之外的远端推送属对外动作，按全局授权处理。
- 交付说明区分"源码已提交 / 副本已同步或未同步"，并列出已知的副本遗留文件类别；副本未同步必须写明。
  设计交付另需区分"HTML 原型已验证 / 原生已构建 / 已装机 / 已真机验收"四个不同状态。
