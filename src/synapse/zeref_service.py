from __future__ import annotations

import argparse
import json
import os
import signal
import socket
from pathlib import Path
from typing import Any

from .zeref import DEFAULT_CONFIG, load_config, load_ibm_receipt, resolve_resident_state

MAX_REQUEST_BYTES = 65536
MAX_CHAT_CHARS = 32768
RUN = True


def _stop(*_: object) -> None:
    global RUN
    RUN = False


def handle_request(payload: dict[str, Any], manager: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("resident request must be a JSON object")
    action = str(payload.get("action", "")).strip().lower()
    if action == "status":
        return dict(manager.status())
    if action == "doctor":
        return dict(manager.doctor())
    if action == "chat":
        message = payload.get("message")
        if not isinstance(message, str):
            raise ValueError("chat message must be a string")
        if len(message) > MAX_CHAT_CHARS:
            raise ValueError("chat message is too large")
        return dict(manager.chat(message))
    raise ValueError(f"unknown resident action: {action or '<empty>'}")


class ResidentRuntimeManager:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG) -> None:
        self.config_path = Path(config_path)
        self.config = load_config(self.config_path)
        self.runtime: Any | None = None
        self.runtime_error: str | None = None
        self._runtime_receipt_digest: tuple[str, str] | None = None

    def _receipt(self) -> dict[str, Any] | None:
        try:
            return load_ibm_receipt(self.config["receipt"])
        except Exception as exc:
            self.runtime_error = f"receipt:{type(exc).__name__}:{exc}"
            return None

    def _ensure_runtime(self) -> tuple[Any | None, dict[str, Any] | None]:
        receipt = self._receipt()
        if receipt is None:
            return None, None
        identity = (str(receipt["job_id"]), str(receipt["entropy_source_sha256"]))
        if self.runtime is not None and self._runtime_receipt_digest == identity:
            return self.runtime, receipt
        try:
            from beastbox.full_zeref import FullZerefRuntime

            runtime = FullZerefRuntime.from_paths(
                config_path=self.config["runtime_config"],
                native_server=self.config["native_server"],
                checkpoint=self.config["checkpoint"],
                ibm_receipt=self.config["receipt"],
                max_new_tokens=int(self.config.get("max_new_tokens", 192)),
            )
        except Exception as exc:
            self.runtime_error = f"runtime:{type(exc).__name__}:{exc}"
            return None, receipt
        old = self.runtime
        self.runtime = runtime
        self._runtime_receipt_digest = identity
        self.runtime_error = None
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        return self.runtime, receipt

    def status(self) -> dict[str, Any]:
        runtime, receipt = self._ensure_runtime()
        runtime_ok = runtime is not None
        native_ok = False
        runtime_doctor: dict[str, Any] = {}
        if runtime is not None:
            try:
                runtime_doctor = dict(runtime.doctor())
                native_ok = bool(runtime_doctor.get("native_trinity")) and bool(runtime_doctor.get("ok"))
            except Exception as exc:
                self.runtime_error = f"doctor:{type(exc).__name__}:{exc}"
        state = resolve_resident_state(runtime_ok=runtime_ok, native_ok=native_ok, receipt=receipt)
        return {
            "state": state,
            "runtime_ok": runtime_ok,
            "native_ok": native_ok,
            "ibm": None if receipt is None else {
                "backend": receipt["backend"],
                "job_id": receipt["job_id"],
                "job_status": receipt["job_status"],
                "fresh": receipt["fresh"],
                "secret_exposed_to_subject": False,
            },
            "runtime_error": self.runtime_error,
            "runtime_doctor": runtime_doctor,
        }

    def doctor(self) -> dict[str, Any]:
        status = self.status()
        return {
            "ok": status["state"] in {"READY", "READY_STALE_IBM", "READY_NO_IBM"},
            **status,
            "config_path": str(self.config_path),
            "socket": str(self.config["socket"]),
            "receipt_path": str(self.config["receipt"]),
        }

    def chat(self, message: str) -> dict[str, Any]:
        runtime, _ = self._ensure_runtime()
        if runtime is None:
            raise RuntimeError(self.runtime_error or "Full Zeref runtime is not ready")
        return dict(runtime.respond(message))

    def close(self) -> None:
        if self.runtime is not None:
            try:
                self.runtime.close()
            finally:
                self.runtime = None


def _reply(conn: socket.socket, value: dict[str, Any]) -> None:
    conn.sendall(json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8") + b"\n")


def serve(config_path: str | Path = DEFAULT_CONFIG) -> int:
    global RUN
    RUN = True
    manager = ResidentRuntimeManager(config_path)
    sock_path = Path(manager.config["socket"])
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sock_path.unlink(missing_ok=True)
    except OSError:
        pass
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(sock_path))
        os.chmod(sock_path, 0o660)
        server.listen(8)
        server.settimeout(1.0)
        while RUN:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            with conn:
                data = b""
                while b"\n" not in data and len(data) <= MAX_REQUEST_BYTES:
                    chunk = conn.recv(8192)
                    if not chunk:
                        break
                    data += chunk
                if len(data) > MAX_REQUEST_BYTES:
                    _reply(conn, {"ok": False, "error": "request too large"})
                    continue
                try:
                    payload = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
                    result = handle_request(payload, manager)
                    _reply(conn, {"ok": True, **result})
                except Exception as exc:
                    _reply(conn, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        manager.close()
        server.close()
        try:
            sock_path.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synapse resident Full Zeref service")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    return serve(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
