#!/usr/bin/env python3
"""DesignWise asset manifest tool.

Commands:
  register  add/update one asset entry, compute sha256, keep other entries intact
  verify    check manifest integrity: ids, files, sha256, temp residue, consumers
  list      query entries by consumer / type / status

Manifest format: see references/image-assets.md §5.
Exit code: 0 = pass, 1 = hard failure, 2 = usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_FIELDS = ("id", "file", "type", "source", "license", "status")
VALID_STATUS = {"temp", "final"}
VALID_SOURCE = {"real", "generated", "vector", "css", "user-provided"}
SCHEME_PREFIXES = ("android:", "ios:", "web:", "native:")
CREDENTIAL_KEY = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|secret|password|passwd|cookie)")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ManifestError(Exception):
    """清单文件本身不可用（截断、非 JSON、结构不符）：按用法/环境错误返回 2。"""


def load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "task": "", "updated_at": "", "assets": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid manifest: {path} ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise ManifestError(f"invalid manifest: {path} (expected object with 'assets' list)")
    return data


def save(path: Path, data: dict) -> None:
    """原子写：先写同目录临时文件再 os.replace，避免中断留下半截 JSON。"""
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def resolve(path_str: str, base: Path) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (base / p)


def image_meta(path: Path) -> dict:
    """读图片尺寸/格式；Pillow 缺失返回空，文件损坏返回 {"error": ...}（不静默放行）。"""
    meta: dict = {}
    try:
        from PIL import Image  # optional
    except ImportError:
        return meta
    try:
        with Image.open(path) as im:
            meta["size"] = f"{im.width}x{im.height}"
            meta["format"] = (im.format or "").lower()
    except Exception as exc:  # 损坏/伪装成图片的文件
        meta["error"] = str(exc)
    return meta


def credential_paths(obj, prefix="") -> list[str]:
    """列出疑似凭据的字段路径；值不读取、不回显。"""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if CREDENTIAL_KEY.search(str(key)):
                found.append(path)
            found.extend(credential_paths(value, path))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found.extend(credential_paths(value, f"{prefix}[{i}]"))
    return found


def load_generation_meta(path: str, file_str: str, file_path: Path) -> tuple[dict, dict, str]:
    """读取 zcode_image.py --meta-out，返回 (meta, 匹配的 asset, 错误说明)。"""
    try:
        with open(path, encoding="utf-8") as fh:
            meta = json.load(fh)
    except OSError as exc:
        return {}, {}, f"meta not readable: {path} ({type(exc).__name__})"
    except ValueError as exc:
        return {}, {}, f"meta is not valid JSON: {path} ({type(exc).__name__})"
    if not isinstance(meta, dict):
        return {}, {}, f"meta must be an object: {path}"
    bad = credential_paths(meta)
    if bad:
        return {}, {}, f"meta contains credential-like fields: {', '.join(bad)}"
    assets = meta.get("assets")
    if not isinstance(assets, list) or not assets:
        return meta, {}, "meta has no assets"
    match = None
    file_name = Path(file_str).name
    for item in assets:
        if not isinstance(item, dict):
            continue
        if item.get("file") == file_str or Path(str(item.get("file", ""))).name == file_name:
            match = item
            break
    if match is None and len(assets) == 1:
        match = assets[0]
    if match is None:
        return meta, {}, f"meta has no asset matching --file {file_str}"
    actual = sha256_file(file_path)
    if match.get("sha256") and match["sha256"] != actual:
        return meta, {}, (f"meta sha256 {str(match['sha256'])[:12]}… does not match "
                          f"actual {actual[:12]}…")
    actual_meta = image_meta(file_path)
    if match.get("format") and actual_meta.get("format") \
            and match["format"] != actual_meta["format"]:
        return meta, {}, (f"meta format {match['format']} does not match "
                          f"actual {actual_meta['format']}")
    if match.get("width") and match.get("height"):
        expected = f"{match['width']}x{match['height']}"
        if actual_meta.get("size") and actual_meta["size"] != expected:
            return meta, {}, (f"meta size {expected} does not match "
                              f"actual {actual_meta['size']}")
    return meta, match, ""


def cmd_register(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    base = manifest_path.parent
    data = load(manifest_path)
    file_path = resolve(args.file, base)
    if not file_path.is_file():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        return 1
    variants = []
    for v in args.variant or []:
        vp = resolve(v, base)
        if not vp.is_file():
            print(f"ERROR: variant not found: {vp}", file=sys.stderr)
            return 1
        entry = {"file": v, "sha256": sha256_file(vp)}
        vm = image_meta(vp)
        entry.update({k: val for k, val in vm.items() if k in ("size", "format")})
        variants.append(entry)
    meta = {}
    meta_asset = {}
    if args.meta:
        meta, meta_asset, err = load_generation_meta(args.meta, args.file, file_path)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
    req = meta.get("request") or {}
    resp = meta.get("response") or {}
    provenance = {
        "model": args.model if args.model is not None else req.get("model"),
        "api": args.api if args.api is not None else meta.get("endpoint"),
        "profile": args.profile if args.profile is not None else req.get("profile"),
        "complexity": args.complexity if args.complexity is not None else req.get("complexity"),
        "quality": args.quality if args.quality is not None else req.get("quality"),
        "requested_size": (args.requested_size if args.requested_size is not None
                           else req.get("size")),
        "output_format": (args.output_format if args.output_format is not None
                          else req.get("output_format")),
        "compression": (args.compression if args.compression is not None
                        else req.get("compression")),
        "background": (args.background if args.background is not None
                       else req.get("background")),
        "prompt_file": args.prompt_file,
        "prompt_sha256": (args.prompt_sha256 if args.prompt_sha256 is not None
                          else req.get("prompt_sha256")),
        "ref": args.ref,
        "refs": req.get("refs") or [],
        "created_at": (args.generated_at or meta.get("generated_at")
                       or datetime.now().astimezone().isoformat(timespec="seconds")),
        "usage": resp.get("usage"),
        "purpose": args.purpose or req.get("profile_purpose"),
    }
    if args.source == "generated" and not provenance["model"]:
        print("WARNING: generated asset has no model provenance "
              "(use --model or --meta)", file=sys.stderr)
    entry = {
        "id": args.id,
        "file": args.file,
        "sha256": sha256_file(file_path),
        "type": args.type,
        "source": args.source,
        "provenance": provenance,
        "variants": variants,
        "consumers": args.consumer or [],
        "crop": None,
        "license": args.license,
        "attribution": args.attribution,
        "status": args.status,
    }
    assets = [a for a in data["assets"] if a.get("id") != args.id]
    replaced = len(assets) != len(data["assets"])
    assets.append(entry)
    data["assets"] = assets
    if args.task:
        data["task"] = args.task
    save(manifest_path, data)
    print(f"{'updated' if replaced else 'registered'} {args.id} -> {args.file}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    data = load(manifest_path)
    base = manifest_path.parent
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    checked = 0
    for path in credential_paths(data):
        errors.append(f"manifest contains credential-like field: {path}")

    def prov_issue(msg: str) -> None:
        (errors if args.strict_provenance else warnings).append(msg)

    for idx, asset in enumerate(data["assets"]):
        label = asset.get("id") or f"#{idx}"
        missing = [f for f in REQUIRED_FIELDS if not asset.get(f)]
        if missing:
            errors.append(f"{label}: missing fields {', '.join(missing)}")
        if asset.get("id") in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(asset.get("id"))
        if asset.get("status") not in VALID_STATUS:
            errors.append(f"{label}: invalid status {asset.get('status')!r}")
        elif asset.get("status") == "temp" and not args.allow_temp:
            errors.append(f"{label}: status=temp cannot ship (use --allow-temp for work in progress)")
        if asset.get("source") and asset["source"] not in VALID_SOURCE:
            warnings.append(f"{label}: unknown source {asset['source']!r}")
        f = asset.get("file")
        actual_meta = {}
        if f:
            fp = resolve(f, base)
            if not fp.is_file():
                errors.append(f"{label}: file missing: {fp}")
            else:
                actual_meta = image_meta(fp)
                if actual_meta.get("error"):
                    errors.append(f"{label}: image unreadable: {actual_meta['error']}")
                if asset.get("sha256"):
                    checked += 1
                    actual = sha256_file(fp)
                    if actual != asset["sha256"]:
                        errors.append(f"{label}: sha256 mismatch (manifest {asset['sha256'][:12]}… actual {actual[:12]}…)")
        prov = asset.get("provenance") or {}
        if asset.get("source") == "generated":
            if not prov.get("model"):
                prov_issue(f"{label}: generated asset has no provenance.model")
            if not prov.get("created_at"):
                prov_issue(f"{label}: generated asset has no provenance.created_at")
            if prov.get("prompt_file") and not resolve(prov["prompt_file"], base).is_file():
                prov_issue(f"{label}: prompt_file not found: {prov['prompt_file']}")
        if prov.get("output_format") and actual_meta.get("format") \
                and prov["output_format"] != actual_meta["format"]:
            errors.append(f"{label}: provenance.output_format {prov['output_format']} "
                          f"does not match actual {actual_meta['format']}")
        for v in asset.get("variants") or []:
            vf = v.get("file")
            if not vf:
                continue
            vp = resolve(vf, base)
            if not vp.is_file():
                errors.append(f"{label}: variant missing: {vp}")
            elif v.get("sha256") and sha256_file(vp) != v["sha256"]:
                errors.append(f"{label}: variant sha256 mismatch: {vf}")
        for consumer in asset.get("consumers") or []:
            if consumer.startswith(SCHEME_PREFIXES):
                continue
            if not resolve(consumer, base).exists():
                msg = f"{label}: consumer not found: {consumer}"
                (errors if args.strict_consumers else warnings).append(msg)

    result = {
        "manifest": str(manifest_path),
        "assets": len(data["assets"]),
        "hashes_checked": checked,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"OK: {len(data['assets'])} asset(s), {checked} hash(es) verified", file=sys.stderr)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = load(Path(args.manifest))
    rows = []
    for a in data["assets"]:
        if args.type and a.get("type") != args.type:
            continue
        if args.status and a.get("status") != args.status:
            continue
        if args.consumer and args.consumer not in (a.get("consumers") or []):
            continue
        rows.append(a)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for a in rows:
            print(f"{a.get('id')}\t{a.get('type')}\t{a.get('status')}\t{a.get('file')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DesignWise asset manifest tool")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("register", help="add or update one asset")
    r.add_argument("--manifest", required=True)
    r.add_argument("--file", required=True, help="asset path (relative to manifest)")
    r.add_argument("--id", required=True, help="stable semantic id")
    r.add_argument("--type", required=True)
    r.add_argument("--source", required=True)
    r.add_argument("--license", required=True)
    r.add_argument("--status", default="final", choices=sorted(VALID_STATUS))
    r.add_argument("--consumer", action="append", help="consumer path or platform:<name>; repeatable")
    r.add_argument("--variant", action="append", help="variant file path; repeatable")
    r.add_argument("--model", default=None)
    r.add_argument("--profile", default=None, help="zcode_image.py profile (final/premium/max/explore/draft)")
    r.add_argument("--api", default=None, help="e.g. images/generations or images/edits")
    r.add_argument("--complexity", default=None, help="low / medium / high")
    r.add_argument("--quality", default=None, help="auto / low / medium / high / xhigh / max")
    r.add_argument("--requested-size", default=None, help="requested WxH before local fitting")
    r.add_argument("--output-format", default=None, choices=sorted(("png", "jpeg", "webp")))
    r.add_argument("--compression", type=int, default=None, help="JPEG/WebP quality 0-100")
    r.add_argument("--background", default=None, help="auto / opaque / transparent")
    r.add_argument("--prompt-sha256", default=None)
    r.add_argument("--generated-at", default=None, help="ISO timestamp from the generation record")
    r.add_argument("--purpose", default=None, help="asset purpose / profile rationale")
    r.add_argument("--meta", default=None, help="zcode_image.py --meta-out JSON")
    r.add_argument("--prompt-file", default=None)
    r.add_argument("--ref", default=None)
    r.add_argument("--attribution", default=None)
    r.add_argument("--task", default=None)
    r.set_defaults(func=cmd_register)

    v = sub.add_parser("verify", help="verify manifest integrity")
    v.add_argument("--manifest", required=True)
    v.add_argument("--allow-temp", action="store_true", help="tolerate status=temp (work in progress)")
    v.add_argument("--strict-consumers", action="store_true", help="missing consumer path is an error")
    v.add_argument("--strict-provenance", action="store_true",
                   help="missing generated provenance is an error")
    v.set_defaults(func=cmd_verify)

    l = sub.add_parser("list", help="query entries")
    l.add_argument("--manifest", required=True)
    l.add_argument("--type")
    l.add_argument("--status")
    l.add_argument("--consumer")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
