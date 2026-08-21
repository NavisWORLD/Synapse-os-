from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .receipt import load_receipt

DEFAULT_CONFIG = Path("/etc/synapse/zeref.json")


@dataclass(frozen=True)
class ResidentConfig:
    full_zeref: str = "full-zeref"
    beastbox_config: str = "~/.local/state/synapse-zeref/beastbox.json"
    native_server: str = "/usr/share/synapse/zeref/qc67/serving/cosmos_serve.py"
    checkpoint: str = "/usr/share/synapse/zeref/qc67/weights/spark_cst.pt"
    ibm_receipt: str = "/var/lib/synapse/zeref/ibm/latest.json"
    socket_path: str = ""
    max_new_tokens: int = 192
    require_fresh_ibm: bool = False
    native_enabled: bool = True

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> "ResidentConfig":
        source = Path(path)
        if not source.exists():
            return cls()
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Zeref config must be a JSON object")
        allowed = set(cls.__dataclass_fields__)
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError("unknown Zeref config keys: " + ", ".join(unknown))
        return cls(**raw)

    def resolved_socket(self, environ: Mapping[str, str] | None = None) -> Path:
        if self.socket_path:
            return Path(self.socket_path).expanduser()
        env = os.environ if environ is None else environ
        runtime = env.get("XDG_RUNTIME_DIR")
        if runtime:
            return Path(runtime) / "synapse" / "zeref.sock"
        return Path(f"/tmp/synapse-zeref-{os.getuid()}.sock")


def sanitized_subject_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environ is None else environ
    return {str(k): str(v) for k, v in source.items() if str(k) != "IBM_QUANTUM_TOKEN"}


def build_full_zeref_argv(
    config: ResidentConfig,
    *,
    command: str,
    socket_path: str | Path | None = None,
    message: str | None = None,
) -> list[str]:
    if command not in {"doctor", "chat", "serve"}:
        raise ValueError(f"unsupported Full Zeref command: {command}")
    argv = [
        config.full_zeref,
        command,
        "--config",
        str(Path(config.beastbox_config).expanduser()),
        "--native-server",
        str(Path(config.native_server).expanduser()),
        "--checkpoint",
        str(Path(config.checkpoint).expanduser()),
        "--ibm-receipt",
        str(Path(config.ibm_receipt).expanduser()),
        "--max-new-tokens",
        str(int(config.max_new_tokens)),
    ]
    if config.require_fresh_ibm:
        argv.append("--require-fresh-ibm")
    if not config.native_enabled:
        argv.append("--native-disabled")
    if command == "serve":
        argv.extend(["--socket", str(socket_path or config.resolved_socket())])
    if command == "chat" and message is not None:
        argv.append(str(message))
    return argv


def derive_readiness(*, model_available: bool, receipt_state: str, socket_ready: bool) -> str:
    if not model_available:
        return "MODEL_UNAVAILABLE"
    if receipt_state == "missing":
        return "IBM_UNAVAILABLE"
    if receipt_state == "invalid":
        return "IBM_INVALID"
    if receipt_state == "stale":
        return "IBM_STALE"
    if receipt_state != "fresh":
        return "DEGRADED"
    if not socket_ready:
        return "STOPPED"
    return "READY"


def _binary_available(binary: str) -> bool:
    path = Path(binary).expanduser()
    if path.is_absolute() or "/" in binary:
        return path.is_file() and os.access(path, os.X_OK)
    return shutil.which(binary) is not None


def _receipt_state(path: str | Path, *, now: int | float | None = None) -> tuple[str, dict[str, Any] | None, str | None]:
    source = Path(path).expanduser()
    if not source.exists():
        return "missing", None, None
    try:
        receipt = load_receipt(source, now=now)
    except Exception as exc:
        return "invalid", None, type(exc).__name__
    return ("fresh" if receipt["fresh"] else "stale"), receipt, None


def resident_request(socket_path: str | Path, request: Mapping[str, Any], *, timeout: float = 120.0) -> dict[str, Any]:
    payload = json.dumps(dict(request), sort_keys=True).encode("utf-8") + b"\n"
    if len(payload) > 1024 * 1024:
        raise ValueError("resident request too large")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(float(timeout))
    try:
        client.connect(str(socket_path))
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > 4 * 1024 * 1024:
                raise RuntimeError("resident response too large")
            chunks.append(chunk)
            if b"\n" in chunk:
                break
    finally:
        client.close()
    if not chunks:
        raise RuntimeError("resident service returned no response")
    value = json.loads(b"".join(chunks).split(b"\n", 1)[0].decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("resident service returned invalid JSON")
    if value.get("ok") is not True:
        raise RuntimeError(str(value.get("message") or value.get("error") or "resident request failed"))
    result = value.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("resident result must be an object")
    return result


def zeref_status(config: ResidentConfig, *, now: int | float | None = None) -> dict[str, Any]:
    sock = config.resolved_socket()
    receipt_state, receipt, receipt_error = _receipt_state(config.ibm_receipt, now=now)
    command_available = _binary_available(config.full_zeref)
    source_available = Path(config.native_server).expanduser().is_file()
    checkpoint_available = Path(config.checkpoint).expanduser().is_file()
    model_available = bool(command_available and source_available and checkpoint_available)
    socket_ready = sock.exists() and sock.is_socket()
    state = derive_readiness(
        model_available=model_available,
        receipt_state=receipt_state,
        socket_ready=socket_ready,
    )
    ibm: dict[str, Any] = {"state": receipt_state, "error": receipt_error}
    if receipt:
        ibm.update(
            {
                "authenticated": receipt["authenticated"],
                "fresh": receipt["fresh"],
                "backend": receipt["backend"],
                "job_id": receipt["job_id"],
                "job_status": receipt["job_status"],
                "entropy_source_sha256": receipt["entropy_source_sha256"],
                "counts_sha256": receipt["counts_sha256"],
                "secret_exposed_to_subject": False,
            }
        )
    return {
        "state": state,
        "ready": state == "READY",
        "integration_ready": True,
        "model": {
            "command": config.full_zeref,
            "command_available": command_available,
            "native_server_available": source_available,
            "checkpoint_available": checkpoint_available,
            "available": model_available,
        },
        "socket": {"path": str(sock), "ready": socket_ready},
        "ibm": ibm,
        "config": {k: v for k, v in asdict(config).items() if k != "socket_path"},
        "subject_environment_safe": "IBM_QUANTUM_TOKEN" not in sanitized_subject_env(),
    }


def zeref_doctor(config: ResidentConfig, *, now: int | float | None = None) -> dict[str, Any]:
    status = zeref_status(config, now=now)
    if not status["socket"]["ready"]:
        status["doctor"] = None
        return status
    try:
        status["doctor"] = resident_request(status["socket"]["path"], {"op": "doctor"})
    except Exception as exc:
        status["doctor"] = {"ok": False, "error": type(exc).__name__}
        status["state"] = "RUNTIME_FAULT"
        status["ready"] = False
    return status


def exec_resident(config: ResidentConfig) -> None:
    socket_path = config.resolved_socket()
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    argv = build_full_zeref_argv(config, command="serve", socket_path=socket_path)
    executable = shutil.which(argv[0]) if "/" not in argv[0] else argv[0]
    if not executable:
        raise FileNotFoundError(f"Full Zeref executable not found: {argv[0]}")
    argv[0] = str(executable)
    os.execvpe(argv[0], argv, sanitized_subject_env())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-zeref-runtime")
    parser.add_argument("command", choices=["serve", "status", "doctor", "chat"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("message", nargs="?")
    args = parser.parse_args(argv)
    config = ResidentConfig.load(args.config)
    if args.command == "serve":
        exec_resident(config)
        return 0
    if args.command == "status":
        print(json.dumps(zeref_status(config), indent=2, sort_keys=True))
        return 0
    if args.command == "doctor":
        print(json.dumps(zeref_doctor(config), indent=2, sort_keys=True))
        return 0
    if not args.message:
        parser.error("chat requires a message")
    result = resident_request(config.resolved_socket(), {"op": "chat", "text": args.message})
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
