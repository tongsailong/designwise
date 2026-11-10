#!/usr/bin/env python3
"""DesignWise 产物一致性自检（只读）。

只检查**机器可读的声明与绑定**：阶段产物是否存在、指纹是否与真实文件一致、
方向记录的决策出口与状态是否合法（实施基线唯一性按当前任务判定，不跨任务比较）、
素材清单是否可验、报告是否给出双验收结论。
不判断设计好坏，不改任何文件，不产生第二套质量结论。

明确不做：自然语言语义判断、文案与像素比较、对比度豁免裁定、
按修改时间推断「过期」、把一致等同于设计通过。

用法：
    python3 scripts/check-deliverables.py --task-dir design-demos/<task>
    python3 scripts/check-deliverables.py --task-dir design-demos/<task> --stage 7
    python3 scripts/check-deliverables.py --task-dir design-demos/<task> --stage 4 --skip-artifacts
    python3 scripts/check-deliverables.py --task-dir design-demos/<task> --json --strict

退出码：0 = 无不一致（warning 不影响）；1 = 有不一致；2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STAGE_ARTIFACTS = {
    0: ["design-brief.md"],
    2: ["concept-prompts.md", "concept-index.json"],
    3: ["direction-approved.md"],
    4: ["prototype/index.html", "prototype-notes.md"],
    # 阶段 5 的 asset-manifest.json 按规则「有素材才必需」，存在即校验，不作为缺项
    6: ["handoff/README.md", "verification-report.md"],
    7: ["verification-report.md"],
}

EXIT_CHOICES = ("采用", "融合", "全部拒绝")
STATUS_CHOICES = ("实施基线", "实验推荐")
SHA_RE = re.compile(r"\b[0-9a-f]{64}\b")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class Report:
    def __init__(self) -> None:
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.checked: list[str] = []

    def error(self, code: str, where: str, message: str) -> None:
        self.errors.append({"code": code, "where": where, "message": message})

    def warn(self, code: str, where: str, message: str) -> None:
        self.warnings.append({"code": code, "where": where, "message": message})

    def mark(self, item: str) -> None:
        self.checked.append(item)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def png_size(path: Path) -> tuple[int, int] | None:
    """只读 PNG 头；非 PNG 返回 None（不引入图像库依赖）。"""
    try:
        with path.open("rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    if len(head) < 24 or not head.startswith(PNG_MAGIC) or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return int(width), int(height)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def resolve(root: Path, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else root / p


def resolve_artifact(root: Path, task: Path, rel: str, where: str, rep: Report) -> Path:
    """记录里的路径以仓库根为规范基准；旧记录按任务目录写相对路径时兼容解析并提示。"""
    canonical = resolve(root, rel)
    if canonical.exists() or Path(rel).is_absolute():
        return canonical
    fallback = task / rel
    if fallback.exists():
        rep.warn("path-base-ambiguous", where,
                 f"路径按任务目录解析到 {rel}；规范基准是仓库根，建议改写为仓库根相对路径")
        return fallback
    return canonical


def check_artifacts(root: Path, task: Path, stage: int, rep: Report) -> None:
    for s in sorted(STAGE_ARTIFACTS):
        if s > stage:
            continue
        for rel in STAGE_ARTIFACTS[s]:
            target = task / rel
            rep.mark(rel)
            if not target.exists():
                rep.error("missing-artifact", str(target), f"阶段 {s} 声明要求的产物不存在")


def check_concept_index(root: Path, task: Path, min_concepts: int, rep: Report) -> None:
    path = task / "concept-index.json"
    if not path.exists():
        return
    rep.mark("concept-index.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        rep.error("concept-index-invalid", str(path), f"JSON 无法解析：{exc}")
        return
    concepts = data.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        rep.error("concept-index-invalid", str(path), "缺少非空 concepts 数组")
        return
    if len(concepts) < min_concepts:
        rep.error("concept-count", str(path),
                  f"只有 {len(concepts)} 个方向，低于要求的 {min_concepts} 个")
    seen_sha: dict[str, str] = {}
    sizes: dict[tuple[int, int], list[str]] = {}
    for i, c in enumerate(concepts):
        if not isinstance(c, dict):
            rep.error("concept-index-invalid", str(path), f"concepts[{i}] 不是对象")
            continue
        cid = str(c.get("id") or f"#{i}")
        for field in ("file", "sha256"):
            if not c.get(field):
                rep.error("concept-field-missing", str(path), f"方向 {cid} 缺少 {field}")
        if c.get("prompt_file") and not resolve_artifact(
                root, task, c["prompt_file"], str(path), rep).exists():
            rep.error("prompt-file-missing", str(path),
                      f"方向 {cid} 的 prompt 文件不存在：{c['prompt_file']}")
        rel = c.get("file")
        if not rel:
            continue
        image = resolve_artifact(root, task, rel, str(path), rep)
        if not image.exists():
            rep.error("concept-file-missing", str(path), f"方向 {cid} 的图不存在：{rel}")
            continue
        actual_sha = sha256_file(image)
        declared = str(c.get("sha256") or "").lower()
        if declared and declared != actual_sha:
            rep.error("concept-sha-mismatch", str(path),
                      f"方向 {cid} 声明的 sha256 与文件不一致（文件现为 {actual_sha[:12]}…）")
        if actual_sha in seen_sha:
            rep.error("concept-duplicate", str(path),
                      f"方向 {cid} 与 {seen_sha[actual_sha]} 是同一张图（sha256 相同）")
        seen_sha[actual_sha] = cid
        size = png_size(image)
        if size:
            sizes.setdefault(size, []).append(cid)
            if c.get("width") and c.get("height") and (c["width"], c["height"]) != size:
                rep.error("concept-size-mismatch", str(path),
                          f"方向 {cid} 声明 {c.get('width')}x{c.get('height')}，实际 {size[0]}x{size[1]}")
        elif not (c.get("width") and c.get("height")):
            rep.warn("concept-size-unknown", str(path),
                     f"方向 {cid} 既非 PNG 也未声明宽高，无法校验尺寸一致性")
    if len(sizes) > 1:
        rep.error("concept-size-variance", str(path),
                  "三方向图尺寸不一致：" + "，".join(f"{s[0]}x{s[1]}" for s in sizes))


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


def _field(text: str, name: str) -> str | None:
    m = re.search(rf"{name}[：:]\s*(.+)", text)
    return m.group(1).strip() if m else None


def _decision_exit(text: str) -> str | None:
    """显式「决策出口」字段优先；旧模板用「## 采用 / ## 融合 / ## 拒绝」分节表达同一结论。"""
    line = _field(text, "决策出口")
    if line:
        for choice in EXIT_CHOICES:
            if choice in line:
                return choice
        return line
    if re.search(r"^#+\s*融合", text, re.M):
        return "融合"
    if re.search(r"^#+\s*采用", text, re.M) and _field(text, "采用方向"):
        return "采用"
    if "全部拒绝" in text:
        return "全部拒绝"
    return None


def check_direction(root: Path, task: Path, rep: Report) -> None:
    path = task / "direction-approved.md"
    if not path.exists():
        return
    rep.mark("direction-approved.md")
    text = read_text(path)
    if not text:
        rep.error("direction-unreadable", str(path), "文件为空或不可读")
        return

    status = _field(text, "状态")
    if not status or not any(s in status for s in STATUS_CHOICES):
        rep.warn("direction-status-missing", str(path),
                 "未声明「实施基线 / 实验推荐」；旧记录兼容，新任务必须写")
    elif "实验推荐" in status and "晋升" not in text:
        rep.warn("direction-promotion-untracked", str(path),
                 "实验推荐缺少晋升为实施基线的裁决记录")

    exit_value = _decision_exit(text)
    if not exit_value or not any(e in exit_value for e in EXIT_CHOICES):
        rep.error("direction-exit-invalid", str(path),
                  "决策出口必须是「采用 / 融合 / 全部拒绝」之一（字段或分节均可）")
    elif "采用" in exit_value:
        adopted = (_field(text, "采用方向") or _field(text, "目标方案") or "").strip()
        if not adopted or adopted in ("-", "…", "..."):
            rep.error("direction-adopt-empty", str(path), "出口为采用，但「采用方向 / 目标方案」为空")
    elif "融合" in exit_value:
        if "整合概念图" not in text:
            rep.warn("direction-fusion-unverified", str(path),
                     "出口为融合但未记录整合概念图；若融合改变了结构骨架，须补真实整合图")
        elif not re.search(r"整合概念图[^\n]*[0-9a-f]{64}", text):
            rep.warn("direction-fusion-sha-missing", str(path),
                     "整合概念图未附 sha256，无法绑定送检文件")

    candidates = 0
    for cells in _table_rows(text):
        if len(cells) < 3:
            continue
        rel, declared = cells[1], cells[2].lower()
        if not rel.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        if not SHA_RE.fullmatch(declared):
            continue
        candidates += 1
        image = resolve_artifact(root, task, rel, str(path), rep)
        if not image.exists():
            rep.error("direction-candidate-missing", str(path), f"候选图不存在：{rel}")
        elif sha256_file(image) != declared:
            rep.error("direction-candidate-sha-mismatch", str(path),
                      f"候选图 sha256 与记录不一致：{rel}")
    if candidates == 0:
        rep.error("direction-candidates-missing", str(path),
                  "未找到带路径与 sha256 的候选图表（无法绑定送检像素）")


def check_baselines(task: Path, rep: Report) -> None:
    """同一任务内只能有一个实施基线。

    不同任务各自有实施基线是合法状态，不互相排斥；因此作用域是本任务目录
    （含其下嵌套的方向记录，如实验子目录），不扫描仓库内其他任务。
    """
    baselines = []
    for path in sorted(task.rglob("direction-approved.md")):
        status = _field(read_text(path), "状态") or ""
        if "实施基线" in status:
            baselines.append(str(path.relative_to(task)))
    rep.mark("direction-baseline-uniqueness")
    if len(baselines) > 1:
        rep.error("multiple-baselines", str(task / "direction-approved.md"),
                  "同一任务内同时存在多个「实施基线」：" + "，".join(sorted(baselines)))


def check_manifest(root: Path, task: Path, rep: Report) -> None:
    path = task / "asset-manifest.json"
    if not path.exists():
        return
    rep.mark("asset-manifest.json")
    proc = subprocess.run(
        [sys.executable, str(HERE / "asset_manifest.py"), "verify", "--manifest", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-4:]
        rep.error("manifest-verify-failed", str(path), "asset_manifest.py verify 未通过：" + " / ".join(tail))


def check_prototype_notes(root: Path, task: Path, rep: Report) -> None:
    notes = task / "prototype-notes.md"
    if not notes.exists():
        return
    rep.mark("prototype-notes.md")
    text = read_text(notes)
    index: dict[str, int] = {}
    for path in task.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            sha = sha256_file(path)
            index[sha] = index.get(sha, 0) + 1
    for line in text.splitlines():
        if "截图" not in line and ".png" not in line.lower():
            continue
        for sha in SHA_RE.findall(line.lower()):
            if sha not in index:
                rep.error("screenshot-fingerprint-unmatched", str(notes),
                          f"记录的截图指纹在任务目录里找不到对应文件：{sha[:12]}…")


def check_report(task: Path, stage: int, rep: Report) -> None:
    report = task / "verification-report.md"
    if not report.exists() or stage < 7:
        return
    rep.mark("verification-report.md")
    text = read_text(report)
    missing = [k for k in ("工程验收", "设计验收") if k not in text]
    if missing:
        rep.error("dual-acceptance-missing", str(report),
                  "阶段 7 需分开给出工程验收与设计验收结论，缺少：" + "、".join(missing))


def check_duplicate_baselines(task: Path, rep: Report) -> None:
    shots = {sha256_file(p): p for p in (task / "prototype" / "screenshots").glob("*.png")} \
        if (task / "prototype" / "screenshots").is_dir() else {}
    base_dir = task / "handoff" / "baselines"
    if not shots or not base_dir.is_dir():
        return
    rep.mark("baseline-duplication")
    for p in base_dir.glob("*.png"):
        sha = sha256_file(p)
        if sha in shots:
            rep.warn("duplicate-baseline", str(p),
                     f"与原型截图逐字节相同（{shots[sha].name}）；确认不是重复存储")


def main() -> int:
    ap = argparse.ArgumentParser(description="DesignWise 产物一致性自检（只读）")
    ap.add_argument("--task-dir", required=True, help="任务目录，如 design-demos/<task>")
    ap.add_argument("--root", default=".", help="仓库根（解析记录里的相对路径用），默认当前目录")
    ap.add_argument("--stage", type=int, default=7, help="已完成的最高阶段（0-7），默认 7")
    ap.add_argument("--min-concepts", type=int, default=3, help="完整流程要求的方向数，默认 3")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--skip-artifacts", action="store_true",
                    help="跳过阶段产物存在性检查（局部迭代或只需校验已存在记录时）")
    ap.add_argument("--strict", action="store_true", help="warning 也计入失败")
    args = ap.parse_args()

    if not 0 <= args.stage <= 7:
        print("check-deliverables: --stage 必须在 0-7", file=sys.stderr)
        return 2
    root = Path(args.root).resolve()
    task = Path(args.task_dir)
    task = task if task.is_absolute() else root / task
    if not task.is_dir():
        print(f"check-deliverables: 任务目录不存在：{task}", file=sys.stderr)
        return 2

    rep = Report()
    if not args.skip_artifacts:
        check_artifacts(root, task, args.stage, rep)
    check_concept_index(root, task, args.min_concepts, rep)
    check_direction(root, task, rep)
    check_baselines(task, rep)
    check_manifest(root, task, rep)
    check_prototype_notes(root, task, rep)
    check_report(task, args.stage, rep)
    check_duplicate_baselines(task, rep)

    ok = not rep.errors and not (args.strict and rep.warnings)
    result = {
        "task": str(task),
        "stage": args.stage,
        "ok": ok,
        "checked": rep.checked,
        "errors": rep.errors,
        "warnings": rep.warnings,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"一致性自检：{task}")
        print(f"  已检查：{'、'.join(rep.checked) if rep.checked else '（无可检查产物）'}")
        for item in rep.errors:
            print(f"  ❌ [{item['code']}] {item['where']}\n     {item['message']}")
        for item in rep.warnings:
            print(f"  ⚠️  [{item['code']}] {item['where']}\n     {item['message']}")
        if ok:
            print("结论：机械一致性通过（**不等于设计通过**）")
        else:
            print("结论：存在不一致，先修产物或记录；不改设计判断")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
