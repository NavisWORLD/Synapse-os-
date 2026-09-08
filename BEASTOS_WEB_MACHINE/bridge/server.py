from __future__ import annotations

import argparse
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
from typing import Any
from urllib.parse import unquote, urlparse
import webbrowser

from .adapter import BeastAdapter, BeastExchangeAdapter, BeastRelease
from .authority import AuthorityLedger
from .provenance import ProvenanceLog
from .vm import MachineSpec, QemuVMBackend, VMBackend, VMController

API_VERSION = "1.1"
DEFAULT_PORT = 8790
MAX_BODY = 64 * 1024
SESSION_COOKIE = "Synapse-BeastOS-Session"
FORBIDDEN_FIELDS = frozenset({
    "shell", "exec", "command", "commands", "argv", "path", "target", "target_path",
    "repo", "repo_url", "url", "device_path", "image", "image_path", "password", "secret",
    "authorization", "api_key", "credential",
})
GRANTABLE = frozenset({
    "camera", "microphone", "filesystem.read", "filesystem.write", "repo.write",
    "vm.control", "vm.network", "network.status", "network.control", "usb", "serial", "bluetooth",
})


def origin_allowed(origin: str | None, *, listen_port: int) -> bool:
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
        if parsed.scheme != "http" or parsed.username or parsed.password or parsed.path not in {"", "/"}:
            return False
        if parsed.query or parsed.fragment or parsed.port != listen_port:
            return False
        host = parsed.hostname or ""
        if host == "localhost":
            return True
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, OSError):
        return False


def validate_payload(data: dict[str, Any], *, allowed: set[str]) -> None:
    forbidden = (set(data) - allowed) | (set(data) & FORBIDDEN_FIELDS)
    if forbidden:
        raise ValueError("forbidden request fields: " + ", ".join(sorted(forbidden)))


def safe_static_path(root: Path, request_path: str) -> Path | None:
    root = root.resolve()
    decoded = unquote(urlparse(request_path).path)
    candidate = root / ("index.html" if decoded == "/" else decoded.lstrip("/"))
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (ValueError, OSError):
        return None
    return resolved


class UnavailableVMBackend:
    running = False

    def create(self, spec: MachineSpec) -> dict:
        raise RuntimeError("VM engine is not configured; set a verified guest image and SHA-256")

    def destroy(self) -> dict:
        return {"state": "UNAVAILABLE", "engine": "qemu", "reason": "guest image not configured"}


class BridgeState:
    """Synapse authority state wrapped around an external Beast continuity runtime."""

    def __init__(
        self,
        *,
        vm_backend: VMBackend | None = None,
        beast_endpoint: str = "http://127.0.0.1:8088",
        beast_provider: str = "LOCAL_HOST",
        beast_exchange: BeastExchangeAdapter | Any | None = None,
    ) -> None:
        backend = vm_backend or UnavailableVMBackend()
        self.authority = AuthorityLedger()
        self.provenance = ProvenanceLog()
        self.vm = VMController(backend, self.authority)
        self.machine: dict[str, Any]
        if isinstance(backend, UnavailableVMBackend):
            self.machine = {
                "state": "UNAVAILABLE",
                "engine": "qemu",
                "reason": "guest image not configured",
            }
        else:
            self.machine = {
                "state": "STOPPED",
                "engine": "qemu" if isinstance(backend, QemuVMBackend) else "test-double",
                "reason": "disposable guest is not running",
            }
        self.beast = BeastAdapter(endpoint=beast_endpoint, provider=beast_provider)
        self.beast_exchange = beast_exchange

    def clock_in(self, brain: str) -> dict[str, Any]:
        if self.machine.get("state") == "RUNNING":
            self.authority.master_privacy_stop()
            self.machine = self.vm.destroy()
            self.provenance.append("machine_destroy_model_swap", self.machine)
        revoked = self.authority.clock_in(brain)
        self.provenance.append("brain_clock_in", {"brain": brain, "revoked": sorted(revoked)})
        return self.status()

    def grant(self, capability: str) -> dict[str, Any]:
        if capability not in GRANTABLE:
            raise ValueError(f"capability is not grantable: {capability}")
        self.authority.grant(capability)
        self.provenance.append(
            "authority_grant",
            {"brain": self.authority.active_brain, "capability": capability},
        )
        return self.status()

    def revoke(self, capability: str) -> dict[str, Any]:
        self.authority.revoke(capability)
        self.provenance.append(
            "authority_revoke",
            {"brain": self.authority.active_brain, "capability": capability},
        )
        return self.status()

    def chat(self, text: str) -> dict[str, Any]:
        if self.authority.active_brain is None:
            raise PermissionError("clock in a brain before sending Beast conversation turns")
        if self.beast_exchange is None:
            raise RuntimeError("Beast runtime exchange is not configured")
        text = str(text)
        if not text.strip():
            raise ValueError("chat text is required")
        response = self.beast_exchange.chat(text)
        result = response.get("result") if isinstance(response, dict) else None
        keys = sorted(str(key) for key in result) if isinstance(result, dict) else []
        self.provenance.append(
            "beast_chat",
            {
                "brain": self.authority.active_brain,
                "schema": response.get("schema") if isinstance(response, dict) else None,
                "result_keys": keys,
                "prompt_bytes": len(text.encode("utf-8")),
            },
        )
        return response

    def inspect_beast(self) -> dict[str, Any]:
        if self.beast_exchange is None:
            raise RuntimeError("Beast runtime exchange is not configured")
        response = self.beast_exchange.inspect()
        result = response.get("result") if isinstance(response, dict) else None
        keys = sorted(str(key) for key in result) if isinstance(result, dict) else []
        self.provenance.append(
            "beast_inspect",
            {
                "schema": response.get("schema") if isinstance(response, dict) else None,
                "result_keys": keys,
            },
        )
        return response

    def machine_create(self, spec: MachineSpec) -> dict[str, Any]:
        if spec.network_mode != "none" and not self.authority.allowed("vm.network"):
            raise PermissionError("vm.network authority required for networked guest")
        self.machine = self.vm.create(spec)
        self.provenance.append("machine_create", self.machine)
        return dict(self.machine)

    def machine_destroy(self) -> dict[str, Any]:
        self.machine = self.vm.destroy()
        self.provenance.append("machine_destroy", self.machine)
        return dict(self.machine)

    def master_privacy_stop(self) -> dict[str, Any]:
        revoked = self.authority.master_privacy_stop()
        if self.machine.get("state") == "RUNNING":
            self.machine = self.vm.destroy()
        self.provenance.append(
            "master_privacy_stop",
            {"revoked": sorted(revoked), "machine": self.machine},
        )
        return self.status()

    def status(self) -> dict[str, Any]:
        release = BeastRelease.v060()
        exchange = self.beast_exchange
        return {
            "active_brain": self.authority.active_brain,
            "grants": sorted(self.authority.grants()),
            "machine": dict(self.machine),
            "beast": {
                "release": release.tag,
                "commit": release.commit,
                "asset_sha256": release.sha256,
                "prerelease": release.prerelease,
                "provider_location": self.beast.provider,
                "endpoint": self.beast.endpoint,
                "exchange_configured": exchange is not None,
                "runtime_provider": getattr(exchange, "provider", None),
                "runtime_model": getattr(exchange, "model", None),
                "executable": getattr(exchange, "executable", None),
            },
        }


def _loopback_probe(url: str, timeout: float = 0.08) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _exchange_executable_available(state: BridgeState) -> bool:
    exchange = state.beast_exchange
    executable = getattr(exchange, "executable", None)
    if not exchange or not executable:
        return False
    candidate = Path(str(executable)).expanduser()
    if candidate.is_absolute():
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(str(executable)) is not None


class BeastOSServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], *, state: BridgeState, web_root: Path, token: str) -> None:
        super().__init__(address, BeastOSHandler)
        self.state = state
        self.web_root = web_root.resolve()
        self.token = token


class BeastOSHandler(BaseHTTPRequestHandler):
    server: BeastOSServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"beastos-web: {self.address_string()} - {fmt % args}")

    def _origin_ok(self) -> bool:
        return origin_allowed(self.headers.get("Origin"), listen_port=self.server.server_port)

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and self._origin_ok():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Synapse-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-Synapse-Token", "")
        if not supplied:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookie.get(SESSION_COOKIE)
            supplied = morsel.value if morsel else ""
        return bool(supplied) and secrets.compare_digest(supplied, self.server.token)

    def _require_api(self) -> bool:
        if not self._origin_ok():
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": {"code": "ORIGIN_DENIED"}})
            return False
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": {"code": "AUTH_REQUIRED"}})
            return False
        return True

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY:
            raise ValueError("request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _resolve_asset(self, path: str) -> Path | None:
        mapping = {
            "/": "public/index.html",
            "/index.html": "public/index.html",
            "/styles.css": "public/styles.css",
            "/app.webmanifest": "public/app.webmanifest",
            "/sw.js": "public/sw.js",
            "/icon.svg": "public/icon.svg",
        }
        relative = mapping.get(path, path.lstrip("/") if path.startswith("/src/") else "")
        if not relative:
            return None
        return safe_static_path(self.server.web_root, "/" + relative)

    def _serve_asset(self, path: str) -> bool:
        target = self._resolve_asset(path)
        if target is None or not target.is_file():
            return False
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".mjs": "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".webmanifest": "application/manifest+json; charset=utf-8",
            ".svg": "image/svg+xml; charset=utf-8",
        }.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:* https:; "
            "img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self'; script-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        if path == "/sw.js":
            self.send_header("Service-Worker-Allowed", "/")
        if path in {"/", "/index.html"}:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={self.server.token}; HttpOnly; SameSite=Strict; Path=/",
            )
        self.end_headers()
        self.wfile.write(body)
        return True

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, PermissionError):
            status, code = HTTPStatus.FORBIDDEN, "AUTHORITY_DENIED"
        elif isinstance(exc, (ValueError, TypeError, json.JSONDecodeError)):
            status, code = HTTPStatus.BAD_REQUEST, "BAD_REQUEST"
        else:
            status, code = HTTPStatus.CONFLICT, "CAPABILITY_UNAVAILABLE"
        self._send_json(status, {"ok": False, "error": {"code": code, "message": str(exc)}})

    def do_OPTIONS(self) -> None:
        if not self._origin_ok():
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": {"code": "ORIGIN_DENIED"}})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/v1/health":
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "service": "synapse-beastos-web", "api_version": API_VERSION},
            )
            return
        if path.startswith("/v1/"):
            if not self._require_api():
                return
            try:
                if path == "/v1/status":
                    payload = self.server.state.status()
                    payload["bridge"] = "CONNECTED"
                    payload["beast"]["exchange_available"] = _exchange_executable_available(self.server.state)
                    payload["beast"]["service_connected"] = _loopback_probe(payload["beast"]["endpoint"])
                    payload["beast"]["connected"] = payload["beast"]["exchange_available"]
                    payload["ollama"] = {
                        "endpoint": "http://127.0.0.1:11434",
                        "connected": _loopback_probe("http://127.0.0.1:11434"),
                    }
                    self._send_json(HTTPStatus.OK, {"ok": True, "status": payload})
                    return
                if path == "/v1/beast/inspect":
                    self._send_json(
                        HTTPStatus.OK,
                        {"ok": True, "response": self.server.state.inspect_beast()},
                    )
                    return
                if path == "/v1/provenance":
                    self._send_json(
                        HTTPStatus.OK,
                        {"ok": True, "records": self.server.state.provenance.records()},
                    )
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "ROUTE_NOT_FOUND"}})
                return
            except (PermissionError, ValueError, TypeError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
                self._handle_error(exc)
                return
        if not self._serve_asset(path):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "NOT_FOUND"}})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/v1/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "ROUTE_NOT_FOUND"}})
            return
        if not self._require_api():
            return
        try:
            data = self._read_json()
            state = self.server.state
            if path == "/v1/brain/clock-in":
                validate_payload(data, allowed={"brain"})
                result = state.clock_in(str(data.get("brain") or ""))
            elif path == "/v1/beast/chat":
                validate_payload(data, allowed={"text"})
                result = state.chat(str(data.get("text") or ""))
            elif path == "/v1/authority/grant":
                validate_payload(data, allowed={"capability"})
                result = state.grant(str(data.get("capability") or ""))
            elif path == "/v1/authority/revoke":
                validate_payload(data, allowed={"capability"})
                result = state.revoke(str(data.get("capability") or ""))
            elif path == "/v1/privacy/stop":
                validate_payload(data, allowed=set())
                result = state.master_privacy_stop()
            elif path == "/v1/machine/create":
                validate_payload(data, allowed={"memory_mb", "cpus", "network_mode"})
                spec = MachineSpec(
                    memory_mb=int(data.get("memory_mb", 2048)),
                    cpus=int(data.get("cpus", 2)),
                    network_mode=str(data.get("network_mode", "none")),
                )
                result = state.machine_create(spec)
            elif path == "/v1/machine/destroy":
                validate_payload(data, allowed=set())
                result = state.machine_destroy()
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "ROUTE_NOT_FOUND"}})
                return
            self._send_json(HTTPStatus.OK, {"ok": True, "result": result})
        except (PermissionError, ValueError, TypeError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
            self._handle_error(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authenticated localhost BeastOS Web Machine cockpit")
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=os.environ.get("SYNAPSE_BEASTOS_TOKEN"))
    parser.add_argument("--web-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--beast-endpoint",
        default=os.environ.get("SYNAPSE_BEAST_ENDPOINT", "http://127.0.0.1:8088"),
    )
    parser.add_argument(
        "--beast-provider-location",
        choices=["BROWSER", "LOCAL_HOST", "LAN", "CLOUD"],
        default=os.environ.get("SYNAPSE_BEAST_PROVIDER_LOCATION", "LOCAL_HOST"),
    )
    parser.add_argument(
        "--beast-executable",
        default=os.environ.get("SYNAPSE_BEAST_EXECUTABLE", "beastbox"),
    )
    parser.add_argument(
        "--beast-data-dir",
        type=Path,
        default=Path(os.environ.get("SYNAPSE_BEAST_DATA_DIR", "~/.local/share/beastbox/beastos-web")).expanduser(),
    )
    parser.add_argument(
        "--beast-runtime-provider",
        choices=["reference", "ollama", "compatible"],
        default=os.environ.get("SYNAPSE_BEAST_RUNTIME_PROVIDER", "reference"),
    )
    parser.add_argument(
        "--beast-model",
        default=os.environ.get("SYNAPSE_BEAST_MODEL", "COSMOS reference"),
    )
    parser.add_argument("--beast-provider-url", default=os.environ.get("SYNAPSE_BEAST_PROVIDER_URL"))
    parser.add_argument("--beast-allow-remote", action="store_true")
    parser.add_argument("--beast-api-key-env", default=os.environ.get("SYNAPSE_BEAST_API_KEY_ENV"))
    parser.add_argument(
        "--vm-image",
        type=Path,
        default=(Path(os.environ["SYNAPSE_BEASTOS_VM_IMAGE"]) if os.environ.get("SYNAPSE_BEASTOS_VM_IMAGE") else None),
    )
    parser.add_argument("--vm-sha256", default=os.environ.get("SYNAPSE_BEASTOS_VM_SHA256"))
    parser.add_argument("--open", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.listen not in {"127.0.0.1", "::1", "localhost"}:
        print("beastos-web: privileged bridge is loopback-only")
        return 2
    if not (1 <= args.port <= 65535):
        print("beastos-web: port must be in 1..65535")
        return 2
    if bool(args.vm_image) != bool(args.vm_sha256):
        print("beastos-web: --vm-image and --vm-sha256 must be provided together")
        return 2
    backend: VMBackend = UnavailableVMBackend()
    if args.vm_image and args.vm_sha256:
        backend = QemuVMBackend(image=args.vm_image, image_sha256=args.vm_sha256)
    try:
        exchange = BeastExchangeAdapter(
            data_dir=args.beast_data_dir,
            executable=args.beast_executable,
            provider=args.beast_runtime_provider,
            model=args.beast_model,
            provider_url=args.beast_provider_url,
            allow_remote=args.beast_allow_remote,
            api_key_env=args.beast_api_key_env,
        )
        state = BridgeState(
            vm_backend=backend,
            beast_endpoint=args.beast_endpoint,
            beast_provider=args.beast_provider_location,
            beast_exchange=exchange,
        )
    except ValueError as exc:
        print(f"beastos-web: invalid runtime configuration: {exc}")
        return 2
    token = args.token or secrets.token_urlsafe(32)
    server = BeastOSServer((args.listen, args.port), state=state, web_root=args.web_root, token=token)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"BeastOS Web listening on {url}")
    print("Authority: session-authenticated, origin-validated, capability-scoped, loopback-only")
    print(
        "Beast: fixed runtime exchange; "
        f"provider={exchange.provider} model={exchange.model!r} release={BeastRelease.v060().tag}"
    )
    if args.open:
        import threading
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if state.machine.get("state") == "RUNNING":
            state.master_privacy_stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
