# 素材管理 · 选择、复用、清单与溯源

> **读这份文档的时机**：判断视觉主角该用什么、决定某张图取真图/生成/程序化、登记或替换素材、跨 HTML 与原生复用同一批资产时。
> **一句话立场**：**先决定主角素材是什么，再决定怎么把它做出来；素材清单是唯一事实源。**
> **不重复的规则**：生图 prompt 与失败处理见 `references/image-generation.md`；原生交付包见 `references/design-handoff.md`。

---

## 1. 先选主角素材

一个界面通常只有一个视觉主角。先定它属于哪一类：

| 内容特征 | 主角素材 | 该用 | 反例 |
|---|---|---|---|
| 真实物体/人物/地点/产品 | **真实摄影** | 主体清晰、可裁切、许可可查 | stock「微笑握手」凑数；AI 图冒充真机 |
| 抽象概念/情绪/叙事背景 | **原创插画/场景/氛围图** | 生成即最优载体 | 硬找「大概相关」的 stock 图 |
| 数值/趋势/对比/结构 | **数据可视化** | 真实数据与明确刻度 | 装饰性 3D 球代替数据 |
| 材质/光泽/纹理 | **程序化材质**（CSS/SVG/Canvas） | 可调、可响应、零版权风险 | 大位图铺满导致体积暴涨 |
| 一句话/名字/数字 | **字即图**（排版主视觉） | 字号跨度、字重对比、留白服务那一句 | 给大字配一堆无关装饰 |
| 实体包装/卡片 | **实物仿制**（纸感/阴影/3D） | 材质线索真实 | 拿 mockup 模板截图当成品 |
| 使用情境 | **场景/人物** | 真实场景或明确标注为演示的合成 | 明显摆拍的商务图讲工程师故事 |

**顺序**：内容 → 主角素材 → 载体（真图/生成/程序化）→ 实现。主角定不下来，通常说明产品要传达什么还没想清，回 `references/product-value.md`。

---

## 2. 内容必需 vs 装饰

沿用真图诚实性测试：

> **去掉这张图，信息是否有损？** 有损 → 内容必需；无损 → 装饰。

- 内容必需：必须取真图或生成；**绝不用 CSS 色块 / SVG 几何 / stock 氛围图糊弄**。
- 装饰：默认不生成；可以程序化，也可以不加。
- 拿不准：按内容必需处理。

**取图来源**：Wikimedia Commons、Met/AIC Open Access（公共领域/免版权）；Unsplash/Pexels（免版权）；用户自己的产品/品牌走 `references/brand-asset-protocol.md`；具名产品/品牌必须取官方 logo。

---

## 3. 素材三态

| 状态 | 定义 | 能否进产品 | 去哪 |
|---|---|---|---|
| **参考图** | 判断输入，可作 `--ref` | 否 | `.designwise/refs/` 或项目 `refs/` |
| **概念图** | 方向比较，探索态 | **否** | `design-demos/<task>/concepts/` |
| **正式素材** | 最终产品资产 | 是 | `assets/`，登记 manifest |

**概念图不是正式素材**：图内文字是幻觉、控件是伪的、效果可能不可实现。只能提取视觉语言，不能直接切片交付。

---

## 4. 复用优先

### 4.1 复用顺序

1. 查 `asset-manifest.json`：是否已有同用途/同视觉语言的资产
2. 查项目已有素材、设计系统、品牌资产
3. 查原型里已经使用的资产（可能只是没登记）
4. 能矢量化/程序化实现的，不生成位图
5. 确认没有可复用项，才生成

### 4.2 跨阶段复用

概念图（阶段 2）→ HTML（阶段 4）→ 原生（阶段 6）应尽量复用同一素材或同一矢量化实现：

- 概念图里可提取的纹理/背景/插画语言 → 生成或矢量化成正式素材
- HTML 里验证过的素材 → 阶段 6 直接按原生密度导出，不重新设计
- 同一素材的 HTML/CSS 版本与原生 drawable/Asset Catalog 版本登记为同一 id 的变体

### 4.3 不重复生成

- 同一素材只差尺寸/裁切/格式 → 用转换生成变体，不重新生图
- 只差主题色 → 程序化调色优先
- 已有合格素材 → 不因「想再看看」重复生成

---

## 5. `asset-manifest.json` 契约

### 5.1 结构

```json
{
  "version": 1,
  "task": "<项目>-<功能>",
  "updated_at": "2026-11-09T00:00:00+08:00",
  "assets": [
    {
      "id": "bg-home-hero",
      "file": "assets/images/<asset-id>.png",
      "sha256": "<64 hex>",
      "type": "background",
      "source": "generated",
      "provenance": {
        "model": "gpt-image-2.5",
        "prompt_file": "assets/prompts/<asset-id>.md",
        "ref": null,
        "created_at": "..."
      },
      "variants": [
        {"file": "assets/images/<asset-id>@2x.png", "size": "2160x3840", "crop": "center", "format": "png", "theme": "light"},
        {"file": "assets/images/<asset-id>-dark.webp", "size": "1080x1920", "crop": "center", "format": "webp", "theme": "dark"}
      ],
      "consumers": ["prototype/index.html", "android:home", "ios:HomeView"],
      "crop": {"focus": [0.5, 0.35], "safe_area": "center 60%"},
      "license": "generated-for-project",
      "attribution": null,
      "status": "final"
    }
  ]
}
```

### 5.2 字段纪律

| 字段 | 规则 |
|---|---|
| `id` | 稳定、语义化、唯一；变体共用同一 id |
| `file` | 工程可直接引用的路径；不写临时目录 |
| `sha256` | **主文件**的指纹；变体各自在 `variants[].sha256` 记录（可选但推荐） |
| `type` | background / illustration / icon / texture / photo / logo / decoration / mask |
| `source` | real / generated / vector / css / user-provided |
| `provenance` | 生成物必须有模型 + prompt 文件；真实图必须有来源 URL/作者/许可 |
| `variants` | 尺寸/裁切/格式/主题变体；记录转换方式 |
| `consumers` | 谁在用；删除/替换前必须核对 |
| `crop` | 焦点与安全区；CSS `cover` 与原生 `CENTER_CROP` 的差异在此说明 |
| `license` | real-license / generated-for-project / brand-asset / unknown |
| `status` | temp / final；**temp 不得进交付包** |

### 5.3 一致性校验

```bash
# 校验清单：文件存在、sha256 匹配、消费者存在、无 temp 残留
python3 scripts/asset_manifest.py verify --manifest asset-manifest.json
```

`sha256` 只证明「文件没变」，**不证明许可正确、视觉正确或裁切正确**；这三件事分别记录。

---

## 6. 变体、裁切与单位

### 6.1 变体

| 变体类型 | 做法 | 注意 |
|---|---|---|
| 尺寸 | 从同一母版导出；Android density buckets；iOS @2x/@3x | 不反复有损放大 |
| 裁切 | 记录焦点/安全区；按端分别导出 | CSS cover 不等于原生 CENTER_CROP |
| 格式 | PNG（透明/无损）/ WebP（体积）/ JPEG（照片） | 透明与压缩会改变观感，需复验 |
| 主题 | 亮/暗两套；或程序化调色 | 暗色不是简单反相 |
| 状态 | 空/加载/错误占位图 | 占位图也要登记 |

### 6.2 px 与 dp/sp

- HTML 的 CSS px **不能直接当** Android dp 或 iOS pt。
- 换算按目标设备密度与设计基准（如 360dp 宽基准）计算，并在真机核对。
- 触控目标：Android ≥48dp，iOS ≥44pt；图标视觉尺寸小不代表触控区小。
- 字体：Android `sp`（跟随系统缩放），iOS Dynamic Type；不要用固定 px 锁死。

### 6.3 深层链接与路径

- 单文件 HTML 交付：图片 base64 内嵌，避免挪目录裂图。
- 多文件/原生：相对路径或资源引用；manifest 里写工程可解析的路径。
- 不把 `prototype/assets/img/` 的验证态路径直接写进原生交付清单。

---

## 7. 许可与溯源

| 素材来源 | 许可记录 | 交付注意 |
|---|---|---|
| 公共领域/免版权 | 来源 URL、作者、许可名、获取日期 | 保留署名（若要求） |
| 用户提供 | 用户授权范围 | 不超出授权使用 |
| 品牌官方资产 | 官方来源、使用边界 | 不冒充、不改 logo |
| 生成物 | 模型、prompt、生成日期 | 标 generated；不声称是真实产品图 |
| 矢量化/程序化 | 原创说明 | 不复制他人矢量资产 |

**MIT 边界**：本仓库保留的 MIT 代码与版权声明必须保留；**生成素材不自动继承 MIT**，其许可按项目与生成服务条款记录。不要把「仓库是 MIT」误写成「所有生成素材都是 MIT」。

**秘密**：prompt 日志、manifest、证据包不得包含 API key、Cookie、内部链接、真实用户隐私数据。

---

## 8. 失败模式

| 症状 | 根因 | 修正 |
|---|---|---|
| 页面「图很多」但主角不明 | 没做主角选择 | 先定主角，删装饰图 |
| 内容必需的图用色块顶着 | 把「默认不生图」误解成「不许有图」 | 回诚实性测试，取真图/生成 |
| AI 图冒充真实产品/品牌 | 跳过品牌资产协议 | 取官方图；生成物标注 |
| 大图铺满导致体积巨大 | 位图做本可程序化的材质 | CSS/SVG 渐变/噪点/光效 |
| 挪目录就裂图 | 相对路径 | 单文件改 base64 内嵌 |
| 同一素材多个孤儿副本 | 复制后改一版不登记 | 变体登记 + 消费者 |
| 删除素材后界面裂图 | 没查消费者 | 删除前 `asset_manifest.py verify` |
| 原生裁切丢主体 | 只按 CSS cover 居中 | 记录焦点/安全区，逐端核对 |
| 暗色模式素材发灰 | 简单反相 | 单独生成/调色并复验 |
| 交付包混入 temp 图 | 没跑清单校验 | `status=temp` 阻断交付 |

---

## 9. 与其他文档的分工

| 问题 | 去哪 |
|---|---|
| prompt 怎么写/模型能力/失败树 | `references/image-generation.md` |
| 品牌官方资产取用 | `references/brand-asset-protocol.md` |
| 原生交付包素材清单 | `references/design-handoff.md` |
| 对比度/可读性 | `references/content-guidelines.md` |
| 参考板与外观账本 | `references/design-research.md` |
