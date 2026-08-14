#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

MAGIC = b"CSMOB1\0\0"
EXPECTED_PACKAGE_SHA = "8ead952e3d14f00027a4017e4c891854eb99dcce025b6415f12c2765950f106d"
EXPECTED_WEIGHTS_SHA = "b6bb2e91f86b90a7f6fcbdf7d070cbb4120f70633f07e1d8a3bbc41ef46dbde7"
EXPECTED_TOKENIZER_SHA = "ba7c88eb0e210fa69f503c526a8ff96f5d0b5f58c614c8e74bb73ff1d34bbaea"
EXPECTED_PARENT_SHA = "bb551d68980bdd5f1f0d20fb25c1974340420439b4dc8462b2b2f154a4b6a553"


class VerificationError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_package(path: Path) -> dict:
    raw = path.read_bytes()
    package_sha = sha256(raw)
    if package_sha != EXPECTED_PACKAGE_SHA:
        raise VerificationError(f"package SHA mismatch: {package_sha}")
    if len(raw) < 20 or raw[:8] != MAGIC:
        raise VerificationError("invalid package magic/header")

    manifest_length, tokenizer_length, weights_length = struct.unpack("<III", raw[8:20])
    if min(manifest_length, tokenizer_length, weights_length) <= 0:
        raise VerificationError("invalid component length")
    if 20 + manifest_length + tokenizer_length + weights_length != len(raw):
        raise VerificationError("component lengths do not match package size")

    manifest_end = 20 + manifest_length
    tokenizer_end = manifest_end + tokenizer_length
    manifest_bytes = raw[20:manifest_end]
    tokenizer = raw[manifest_end:tokenizer_end]
    weights = raw[tokenizer_end:]

    try:
        manifest = json.loads(manifest_bytes)
    except Exception as exc:
        raise VerificationError(f"invalid manifest JSON: {exc}") from exc

    if manifest.get("schema") != "cst-mobile-q8-v1":
        raise VerificationError("wrong manifest schema")
    if manifest.get("lineage") != "Zeref-Mobile-v1":
        raise VerificationError("wrong lineage")
    if manifest.get("parent_checkpoint_sha256") != EXPECTED_PARENT_SHA:
        raise VerificationError("wrong parent checkpoint")
    if manifest.get("tokenizer_sha256") != EXPECTED_TOKENIZER_SHA or sha256(tokenizer) != EXPECTED_TOKENIZER_SHA:
        raise VerificationError("tokenizer SHA mismatch")

    weights_sha = sha256(weights)
    if manifest.get("weights_bytes") != len(weights) or len(weights) != 132932:
        raise VerificationError("q8 payload size mismatch")
    if manifest.get("weights_sha256") != EXPECTED_WEIGHTS_SHA or weights_sha != EXPECTED_WEIGHTS_SHA:
        raise VerificationError("q8 payload SHA mismatch")

    return {
        "lineage": manifest["lineage"],
        "parent_lineage": manifest.get("parent_lineage"),
        "package_bytes": len(raw),
        "package_sha256": package_sha,
        "tokenizer_sha256": sha256(tokenizer),
        "weights_bytes": len(weights),
        "weights_sha256": weights_sha,
        "tensor_count": len(manifest.get("tensors", [])),
        "verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the frozen Zeref-Mobile-v1 .cosmosmodel artifact.")
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        result = verify_package(args.package)
    except (OSError, VerificationError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
