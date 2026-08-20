from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from typing import Any

_SCHEMA = "synapse.zeref.ibm-receipt.v1"
_SECRET_FRAGMENTS = ("token", "secret", "password", "passwd", "api_key", "apikey", "credential")
_ALLOWED_SECRET_METADATA_KEYS = {"secret_exposed_to_subject"}
DEFAULT_CONFIG = Path("/etc/synapse/zeref.json")
DEFAULT_SOCKET = Path("/run/synapse/zeref/zeref.sock")
DEFAULT_RECEIPT = Path("/run/synapse/zeref/ibm-receipt.json")


def _secret_like_key(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if key not in _ALLOWED_SECRET_METADATA_KEYS and any(fragment in lowered for fragment in _SECRET_FRAGMENTS):
                return f"{path}.{key}"
            found = _secret_like_key(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _secret_like_key(child, f"{path}[{index}]")
            if found:
                return found
    return None


def validate_ibm_receipt(value: dict[str, Any], *, now: int | float | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("IBM receipt must be a JSON object")
    secret_key = _secret_like_key(value)
    if secret_key:
        raise ValueError(f"secret-like receipt key rejected: {secret_key}")
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
    if value["schema"] != _SCHEMA:
        raise ValueError("unsupported IBM receipt schema")
    if value["authenticated"] is not True:
        raise ValueError("IBM receipt must be authenticated")
    if value["secret_exposed_to_subject"] is not False:
        raise ValueError("secret_exposed_to_subject must be false")
    backend = str(value["backend"])
    if not backend or "simulator" in backend.lower() or backend.lower().startswith(("aer", "fake")):
        raise ValueError("IBM receipt requires a real hardware backend")
    vector = [float(x) for x in value["entropy12"]]
    if len(vector) != 12:
        raise ValueError("IBM receipt entropy12 must contain exactly 12 values")
    for key in ("entropy_source_sha256", "counts_sha256"):
        digest = str(value[key]).lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError(f"{key} must be a SHA-256 hex digest")
    generated = int(value["generated_at"])
    expires = int(value["expires_at"])
    if expires < generated:
        raise ValueError("IBM receipt expires_at precedes generated_at")
    stamp = int(time.time() if now is None else now)
    out = dict(value)
    out["entropy12"] = vector
    out["fresh"] = stamp <= expires
    return out


def load_ibm_receipt(path: str | Path = DEFAULT_RECEIPT, *, now: int | float | None = None) -> dict[str, Any] | None:
    receipt_path = Path(path)
    if not receipt_path.is_file():
        return None
    raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    return validate_ibm_receipt(raw, now=now)


def resolve_resident_state(*, runtime_ok: bool, native_ok: bool, receipt: dict[str, Any] | None) -> str:
    if not runtime_ok or not native_ok:
        return "DEGRADED"
    if receipt is None:
        return "READY_NO_IBM"
    return "READY" if bool(receipt.get("fresh")) else "READY_STALE_IBM"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        return {
            "socket": str(DEFAULT_SOCKET),
            "receipt": str(DEFAULT_RECEIPT),
            "runtime_config": "/var/lib/synapse/zeref/beastbox.json",
            "native_server": "/var/lib/synapse/zeref/qc67/serving/cosmos_native_server.py",
            "checkpoint": "/var/lib/synapse/zeref/qc67/qc67_cosmo.pt",
            "max_new_tokens": 192,
        }
    value = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Zeref config must be a JSON object")
    allowed = {"socket", "receipt", "runtime_config", "native_server", "checkpoint", "max_new_tokens"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError("unknown Zeref config fields: " + ", ".join(unknown))
    return {**load_config(Path("/__synapse_missing_default__")), **value}


def request_resident(payload: dict[str, Any], *, socket_path: str | Path = DEFAULT_SOCKET, timeout: float = 15.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    if len(body) > 65536:
        raise ValueError("resident request is too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path))
        client.sendall(body)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > 4 * 1024 * 1024:
                raise RuntimeError("resident response exceeded limit")
            if b"\n" in chunk:
                break
    raw = b"".join(chunks).split(b"\n", 1)[0]
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("resident response was not a JSON object")
    return value
