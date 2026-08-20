from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SCHEMA = "synapse.zeref.ibm-receipt.v1"
_SECRET_FRAGMENTS = ("token", "secret", "password", "passwd", "api_key", "apikey", "credential")
_ALLOWED_SECRET_KEYS = {"secret_exposed_to_subject"}


def _secret_like_path(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if key not in _ALLOWED_SECRET_KEYS and any(fragment in lowered for fragment in _SECRET_FRAGMENTS):
                return f"{path}.{key}"
            found = _secret_like_path(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _secret_like_path(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _sha256_hex(value: Any, name: str) -> str:
    digest = str(value).lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"{name} must be SHA-256 hex")
    return digest


def validate_receipt(value: dict[str, Any], *, now: int | float | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("IBM receipt must be an object")
    secret_path = _secret_like_path(value)
    if secret_path:
        raise ValueError(f"secret-like receipt key rejected: {secret_path}")
    required = {
        "schema",
        "authenticated",
        "backend",
        "job_id",
        "job_status",
        "source",
        "generated_at",
        "expires_at",
        "entropy12",
        "entropy_source_sha256",
        "counts_sha256",
        "secret_exposed_to_subject",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError("IBM receipt missing: " + ", ".join(missing))
    if value["schema"] != SCHEMA:
        raise ValueError("unsupported IBM receipt schema")
    if value["authenticated"] is not True:
        raise ValueError("IBM receipt is not authenticated")
    if value["secret_exposed_to_subject"] is not False:
        raise ValueError("IBM receipt indicates secret exposure")
    backend = str(value["backend"])
    lower = backend.lower()
    if not backend or "simulator" in lower or lower.startswith(("aer", "fake")):
        raise ValueError("IBM receipt must identify a hardware backend")
    entropy = [float(x) for x in value["entropy12"]]
    if len(entropy) != 12:
        raise ValueError("IBM receipt entropy12 must contain 12 values")
    generated = int(value["generated_at"])
    expires = int(value["expires_at"])
    if expires < generated:
        raise ValueError("IBM receipt expires before generation")
    clean = dict(value)
    clean["entropy12"] = entropy
    clean["entropy_source_sha256"] = _sha256_hex(value["entropy_source_sha256"], "entropy_source_sha256")
    clean["counts_sha256"] = _sha256_hex(value["counts_sha256"], "counts_sha256")
    current = int(time.time() if now is None else now)
    clean["fresh"] = current <= expires
    return clean


def load_receipt(path: str | Path, *, now: int | float | None = None) -> dict[str, Any]:
    source = Path(path)
    value = json.loads(source.read_text(encoding="utf-8"))
    return validate_receipt(value, now=now)
