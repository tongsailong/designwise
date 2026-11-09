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
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_FIELDS = ("id", "file", "type", "source", "license", "status")
VALID_STATUS = {"temp", "final"}
VALID_SOURCE = {"real", "generated", "vector", "css", "user-provided"}
SCHEME_PREFIXES = ("android:", "ios:", "web:", "native:")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "task": "", "updated_at": "", "assets": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise SystemExit(f"invalid manifest: {path} (expected object with 'assets' list)")
    return data


def save(path: Path, data: dict) -> None:
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resolve(path_str: str, base: Path) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (base / p)


def image_meta(path: Path) -> dict:
    meta: dict = {}
    try:
        from PIL import Image  # optional

        with Image.open(path) as im:
            meta["size"] = f"{im.width}x{im.height}"
            meta["format"] = (im.format or "").lower()
    except Exception:
        pass
    return meta


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
        entry.update(image_meta(vp))
        variants.append(entry)
    entry = {
        "id": args.id,
        "file": args.file,
        "sha256": sha256_file(file_path),
        "type": args.type,
        "source": args.source,
        "provenance": {
            "model": args.model,
            "prompt_file": args.prompt_file,
            "ref": args.ref,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
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
        if f:
            fp = resolve(f, base)
            if not fp.is_file():
                errors.append(f"{label}: file missing: {fp}")
            elif asset.get("sha256"):
                checked += 1
                actual = sha256_file(fp)
                if actual != asset["sha256"]:
                    errors.append(f"{label}: sha256 mismatch (manifest {asset['sha256'][:12]}… actual {actual[:12]}…)")
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
    r.add_argument("--prompt-file", default=None)
    r.add_argument("--ref", default=None)
    r.add_argument("--attribution", default=None)
    r.add_argument("--task", default=None)
    r.set_defaults(func=cmd_register)

    v = sub.add_parser("verify", help="verify manifest integrity")
    v.add_argument("--manifest", required=True)
    v.add_argument("--allow-temp", action="store_true", help="tolerate status=temp (work in progress)")
    v.add_argument("--strict-consumers", action="store_true", help="missing consumer path is an error")
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
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
