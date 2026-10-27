#!/usr/bin/env python3
"""sync_runtime.py — 仓库源码 → 已安装 skill 副本的单向同步工具。

背景：DesignWise 曾同时在仓库和 ~/.zcode/skills/designwise 手改，导致两份
版本互相漂移。这里把「运行时副本」明确为构建产物：默认只检查（--check），
确认后再用 --apply 单向写入；--prune 才会删除副本中源码不存在的文件。

用法：
    python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --check
    python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply
    python3 scripts/sync_runtime.py --to ~/.zcode/skills/designwise --apply --prune

退出码：0 = 一致或写入成功；1 = 检测到漂移/写入失败；2 = 参数或目标目录错误。
不读取、不写入 .env；不触碰 .git / node_modules / design-demos / __pycache__。
"""

import argparse
import hashlib
import os
import shutil
import sys
import tempfile

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_DIRS = {".git", "node_modules", ".reasonix", "design-demos",
                "__pycache__", ".pytest_cache", ".mypy_cache", ".vscode", ".idea"}
EXCLUDE_FILES = {".last-update-check", ".DS_Store",
                 "assets/personal-asset-index.json"}
EXCLUDE_PREFIXES = (".sync-", ".video-tmp-", ".seek-tmp-")
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".swp", ".tmp")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def skip_dir(name):
    return name in EXCLUDE_DIRS


def skip_file(rel):
    name = os.path.basename(rel)
    if rel in EXCLUDE_FILES:
        return True
    if name == ".env.example":
        return False          # 模板可以同步
    if name == ".env" or name.startswith(".env."):
        return True           # .env / .env.local / .env.* 都可能含密钥
    if name.startswith(EXCLUDE_PREFIXES):
        return True
    return name.endswith(EXCLUDE_SUFFIXES)


def manifest(root):
    """Return {relpath: sha256} for syncable files under root."""
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not skip_dir(d))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if skip_file(rel):
                continue
            result[rel] = sha256(path)
    return result


def compare(source, target):
    src = manifest(source)
    dst = manifest(target)
    missing = sorted(set(src) - set(dst))
    different = sorted(k for k in set(src) & set(dst) if src[k] != dst[k])
    extra = sorted(set(dst) - set(src))
    return src, missing, different, extra


def copy_atomic(src, dst):
    dst_dir = os.path.dirname(dst)
    os.makedirs(dst_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sync-", dir=dst_dir)
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        shutil.copymode(src, tmp)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    ap = argparse.ArgumentParser(description="源码 → 运行时 skill 副本单向同步")
    ap.add_argument("--to", required=True, help="目标 skill 目录（如 ~/.zcode/skills/designwise）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只检查漂移（默认）")
    mode.add_argument("--apply", action="store_true", help="写入缺失/不同的文件")
    ap.add_argument("--prune", action="store_true",
                    help="配合 --apply：删除目标里源码不存在的文件（危险，默认关闭）")
    args = ap.parse_args()

    source = os.path.abspath(SOURCE)
    target = os.path.abspath(os.path.expanduser(args.to))
    if not os.path.isdir(target):
        print(f"❌ 目标不是目录：{target}")
        return 2
    source_real = os.path.realpath(source)
    target_real = os.path.realpath(target)
    try:
        common = os.path.commonpath([source_real, target_real])
    except ValueError:
        common = ""
    # 拒绝相同目录，以及互为祖先/后代（否则 --prune 可能删掉源码或仓库）。
    if source_real == target_real or common in (source_real, target_real):
        print("❌ 源码目录与目标目录相同或互为祖先/后代，拒绝同步")
        return 2

    src, missing, different, extra = compare(source, target)
    print(f"源码：{source}（{len(src)} 个可同步文件）")
    print(f"目标：{target}")
    print(f"缺失：{len(missing)} · 不同：{len(different)} · 目标多出：{len(extra)}")
    for rel in missing:
        print(f"  + {rel}")
    for rel in different:
        print(f"  ~ {rel}")
    for rel in extra:
        print(f"  - {rel}")

    if not args.apply:
        if missing or different or extra:
            print("\n结论：存在漂移。确认后用 --apply 单向写入；--prune 才会删除目标多出的文件。")
            return 1
        print("\n结论：一致。")
        return 0

    for rel in missing + different:
        copy_atomic(os.path.join(source, rel), os.path.join(target, rel))
    if args.prune:
        for rel in extra:
            os.remove(os.path.join(target, rel))
        print(f"\n已删除目标多出文件：{len(extra)}")
    print(f"\n已写入：{len(missing) + len(different)} 个文件"
          + ("（含 prune）" if args.prune else "；目标多出文件未删除"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
