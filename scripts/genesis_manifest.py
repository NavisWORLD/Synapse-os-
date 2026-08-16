#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_LICENSE = "Cory Davis / NavisWORLD Synapse Source License 1.0"
EXPECTED_ZENODO_DOI = "10.5281/zenodo.17574447"
SCHEMA = "synapse-genesis-manifest/v1"
MIN_TARGET_BYTES = 8 * 1024**3


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_arch(value: str) -> str:
    key = value.strip().lower()
    aliases = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "riscv64": "riscv64",
    }
    if key not in aliases:
        raise ValueError(f"unsupported architecture: {value}")
    return aliases[key]


def build_manifest(image: Path | str, *, version: str, arch: str, commit: str) -> dict[str, Any]:
    image_path = Path(image)
    if not image_path.is_file():
        raise ValueError(f"image does not exist: {image_path}")
    image_size = image_path.stat().st_size
    return {
        "schema": SCHEMA,
        "synapse_version": str(version),
        "architecture": normalize_arch(arch),
        "image_type": "squashfs-rootfs",
        "image_filename": image_path.name,
        "image_size": image_size,
        "image_sha256": sha256_file(image_path),
        "build_commit": str(commit),
        "license": EXPECTED_LICENSE,
        "zenodo_doi": EXPECTED_ZENODO_DOI,
        "required_target_bytes": max(MIN_TARGET_BYTES, image_size * 4),
        "signature": {"scheme": "sha256", "detached_signature": None},
    }


def write_manifest(payload: dict[str, Any], path: Path | str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_manifest_file(manifest_path: Path | str, image_path: Path | str) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    image = Path(image_path)
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    if payload.get("schema") != SCHEMA:
        raise ValueError("wrong GENESIS manifest schema")
    if payload.get("image_type") != "squashfs-rootfs":
        raise ValueError("wrong image type")
    if payload.get("license") != EXPECTED_LICENSE or payload.get("zenodo_doi") != EXPECTED_ZENODO_DOI:
        raise ValueError("license/provenance mismatch")
    if str(payload.get("image_filename")) != image.name:
        raise ValueError("image filename mismatch")
    actual_size = image.stat().st_size
    if int(payload.get("image_size") or -1) != actual_size:
        raise ValueError("image size mismatch")
    actual_sha = sha256_file(image)
    if str(payload.get("image_sha256") or "").lower() != actual_sha:
        raise ValueError("image SHA-256 mismatch")
    normalize_arch(str(payload.get("architecture") or ""))
    return {
        "verified": True,
        "verification": "hash-verified",
        "image_sha256": actual_sha,
        "image_size": actual_size,
        "architecture": payload["architecture"],
        "synapse_version": payload.get("synapse_version"),
        "build_commit": payload.get("build_commit"),
        "zenodo_doi": payload["zenodo_doi"],
        "signature_verified": False,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate or verify a Synapse GENESIS rootfs manifest")
    sub = p.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate")
    generate.add_argument("--image", required=True, type=Path)
    generate.add_argument("--version", required=True)
    generate.add_argument("--arch", required=True)
    generate.add_argument("--commit", required=True)
    generate.add_argument("--output", required=True, type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--image", required=True, type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            payload = build_manifest(args.image, version=args.version, arch=args.arch, commit=args.commit)
            write_manifest(payload, args.output)
            print(json.dumps(payload, sort_keys=True))
            return 0
        result = verify_manifest_file(args.manifest, args.image)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
