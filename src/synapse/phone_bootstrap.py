from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import socket
import subprocess
import threading
import time
from typing import Any
from urllib.parse import urlparse

from .genesis import GenesisError, GenesisManager
from .hardware import probe_hardware

API_VERSION = "1.1"
GENESIS_API_VERSION = "2.0"
DEFAULT_PORT = 8787
DEFAULT_COSMOS_REPO = "https://github.com/NavisWORLD/Cosmos.git"
DEFAULT_COSMOS_BRANCH = "main"
COSMOS_PORTS = (11434, 11435, 11501, 8765, 8081, 8090, 8000, 8501)
MAX_BODY = 64 * 1024
GENESIS_FORBIDDEN_REQUEST_FIELDS = frozenset(
    {
        "target",
        "target_path",
        "disk",
        "disk_path",
        "device",
        "image",
        "image_path",
        "manifest",
        "manifest_path",
        "command",
        "commands",
        "shell",
        "argv",
        "repo",
        "repo_url",
    }
)


class BootstrapError(RuntimeError):
    pass


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 900) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "command failed").strip()
        raise BootstrapError(f"{' '.join(args[:3])}: {detail}")
    return proc.stdout.strip()


def _memory_total_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _battery_percent() -> float | None:
    root = Path("/sys/class/power_supply")
    if not root.exists():
        return None
    for item in sorted(root.glob("BAT*")):
        try:
            return float((item / "capacity").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return None


def _network_addresses() -> list[dict[str, str]]:
    ip = shutil.which("ip")
    if not ip:
        return []
    try:
        payload = json.loads(_run([ip, "-j", "-4", "addr", "show"], timeout=5))
    except (BootstrapError, json.JSONDecodeError):
        return []
    out: list[dict[str, str]] = []
    for interface in payload:
        name = str(interface.get("ifname") or "")
        for entry in interface.get("addr_info") or []:
            local = entry.get("local")
            if local and local != "127.0.0.1":
                out.append({"interface": name, "address": str(local)})
    return out


def _port_open(host: str, port: int, timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def device_snapshot() -> dict[str, Any]:
    root = shutil.disk_usage("/")
    uname = platform.uname()
    return {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_release": platform.release(),
        "kernel": uname.release,
        "machine": uname.machine,
        "processor": uname.processor or platform.processor() or "unknown",
        "cpu_logical": os.cpu_count(),
        "memory_total_bytes": _memory_total_bytes(),
        "disk_root": {
            "total_bytes": root.total,
            "used_bytes": root.used,
            "free_bytes": root.free,
        },
        "battery_percent": _battery_percent(),
        "network": _network_addresses(),
        "cosmos_ports": {str(port): _port_open("127.0.0.1", port) for port in COSMOS_PORTS},
        "hardware": probe_hardware(),
        "api_version": API_VERSION,
    }


@dataclass
class InstallState:
    phase: str = "idle"
    message: str = "Ready"
    started_at: float | None = None
    finished_at: float | None = None
    progress: int = 0
    error: str | None = None
    checkout: str | None = None
    activation: str | None = None


class InstallManager:
    def __init__(
        self,
        *,
        repo_url: str = DEFAULT_COSMOS_REPO,
        branch: str = DEFAULT_COSMOS_BRANCH,
        install_root: Path,
        allow_install: bool,
        activate: bool,
    ) -> None:
        self.repo_url = repo_url
        self.branch = branch
        self.install_root = install_root.expanduser().resolve()
        self.allow_install = allow_install
        self.activate = activate
        self._state = InstallState(checkout=str(self.install_root))
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._state)

    def _set(self, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self._state, key, value)

    def start(self) -> dict[str, Any]:
        if not self.allow_install:
            raise BootstrapError("install endpoint is disabled; start with --allow-install")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise BootstrapError("an install job is already running")
            self._state = InstallState(
                phase="queued",
                message="Install queued",
                started_at=time.time(),
                progress=1,
                checkout=str(self.install_root),
            )
            self._thread = threading.Thread(target=self._worker, name="cosmos-phone-install", daemon=True)
            self._thread.start()
            return asdict(self._state)

    def _worker(self) -> None:
        try:
            self._install()
        except Exception as exc:
            self._set(
                phase="failed",
                message="Install failed",
                error=str(exc),
                finished_at=time.time(),
            )

    def _install(self) -> None:
        git = shutil.which("git")
        if not git:
            raise BootstrapError("git is required on the laptop")

        self._set(phase="preflight", message="Reading laptop and checking tools", progress=8)
        self.install_root.parent.mkdir(parents=True, exist_ok=True)

        if self.install_root.exists():
            if not (self.install_root / ".git").exists():
                raise BootstrapError(f"install path exists but is not a git checkout: {self.install_root}")
            dirty = _run([git, "-C", str(self.install_root), "status", "--porcelain"], timeout=30)
            if dirty:
                self._set(
                    phase="source",
                    message="Existing COSMOS checkout has local changes; preserving it without pull",
                    progress=35,
                )
            else:
                self._set(phase="source", message="Updating COSMOS checkout from GitHub", progress=25)
                _run([git, "-C", str(self.install_root), "pull", "--ff-only", "origin", self.branch], timeout=300)
        else:
            self._set(phase="source", message="Cloning COSMOS from GitHub", progress=18)
            _run(
                [git, "clone", "--depth", "1", "--branch", self.branch, self.repo_url, str(self.install_root)],
                timeout=600,
            )

        self._set(phase="source-ready", message="COSMOS source is present", progress=55)

        if not self.activate:
            self._set(
                phase="complete",
                message="COSMOS source installed; service activation is disabled on this daemon",
                progress=100,
                activation="not-requested",
                finished_at=time.time(),
            )
            return

        activation = self._activate_checkout()
        self._set(
            phase="complete",
            message="COSMOS install and service activation complete",
            progress=100,
            activation=activation,
            finished_at=time.time(),
        )

    def _activate_checkout(self) -> str:
        compose = None
        for name in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"):
            candidate = self.install_root / name
            if candidate.is_file():
                compose = candidate
                break

        docker = shutil.which("docker")
        if docker and compose:
            self._set(phase="activate", message="Starting COSMOS with Docker Compose", progress=72)
            _run([docker, "compose", "-f", str(compose), "up", "-d"], cwd=self.install_root, timeout=900)
            return "docker-compose"

        dockerfile = self.install_root / "Dockerfile"
        if docker and dockerfile.is_file():
            image = "synapse-cosmos:phone-bootstrap"
            container = "synapse-cosmos-phone"
            self._set(phase="activate", message="Building COSMOS container", progress=68)
            _run([docker, "build", "-t", image, "."], cwd=self.install_root, timeout=1800)
            inspect = subprocess.run([docker, "inspect", container], capture_output=True, text=True)
            if inspect.returncode == 0:
                running = subprocess.run(
                    [docker, "inspect", "-f", "{{.State.Running}}", container],
                    capture_output=True,
                    text=True,
                ).stdout.strip().lower()
                if running == "true":
                    return "docker-existing-running"
                self._set(phase="activate", message="Starting existing COSMOS container", progress=90)
                _run([docker, "start", container], timeout=120)
                return "docker-existing-started"

            self._set(phase="activate", message="Starting COSMOS container", progress=88)
            _run(
                [
                    docker,
                    "run",
                    "-d",
                    "--name",
                    container,
                    "--restart",
                    "unless-stopped",
                    "-p",
                    "8000:8000",
                    "-p",
                    "8501:8501",
                    image,
                ],
                timeout=180,
            )
            return "docker-created"

        raise BootstrapError(
            "COSMOS source is installed, but no supported activation path was found. "
            "Install Docker or add a compose file/service launcher."
        )


class BootstrapServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        token: str,
        install_manager: InstallManager,
        ui_path: Path | None,
        genesis_manager: GenesisManager | Any | None = None,
        genesis_ui_path: Path | None = None,
    ) -> None:
        super().__init__(address, BootstrapHandler)
        self.token = token
        self.install_manager = install_manager
        self.ui_path = ui_path
        self.genesis_manager = genesis_manager
        self.genesis_ui_path = genesis_ui_path


class BootstrapHandler(BaseHTTPRequestHandler):
    server: BootstrapServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"phone-bootstrap: {self.address_string()} - {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Synapse-Token, Authorization")
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

    def _send_html(self, path: Path | None, *, missing: str) -> None:
        if not path or not path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": missing})
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_ui(self) -> None:
        self._send_html(self.server.ui_path, missing="phone bootstrap UI not installed")

    def _send_genesis_ui(self) -> None:
        self._send_html(self.server.genesis_ui_path, missing="GENESIS UI not installed")

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-Synapse-Token", "")
        if not supplied:
            auth = self.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()
        return bool(supplied) and secrets.compare_digest(supplied, self.server.token)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "pairing token required"})
        return False

    def _require_auth_v2(self) -> bool:
        if self._authorized():
            return True
        self._send_json(
            HTTPStatus.UNAUTHORIZED,
            {"ok": False, "error": {"code": "AUTH_REQUIRED", "message": "pairing token required"}},
        )
        return False

    def _genesis(self) -> Any:
        manager = self.server.genesis_manager
        if manager is None:
            raise GenesisError("GENESIS_UNAVAILABLE", "GENESIS manager is not configured on this daemon")
        return manager

    def _send_genesis_error(self, exc: GenesisError) -> None:
        if exc.code == "AUTH_REQUIRED":
            status = HTTPStatus.UNAUTHORIZED
        elif exc.code in {"INSTALL_ALREADY_RUNNING", "ARM_REPLAYED", "ARM_EXPIRED"}:
            status = HTTPStatus.CONFLICT
        else:
            status = HTTPStatus.BAD_REQUEST
        self._send_json(status, {"ok": False, "error": {"code": exc.code, "message": exc.message}})

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise BootstrapError("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY:
            raise BootstrapError("request body too large")
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BootstrapError("body must be valid JSON") from exc
        if not isinstance(data, dict):
            raise BootstrapError("JSON body must be an object")
        return data

    def _reject_genesis_control_fields(self, data: dict[str, Any], *, allowed: set[str]) -> None:
        forbidden = (set(data) - allowed) | (set(data) & GENESIS_FORBIDDEN_REQUEST_FIELDS)
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise GenesisError(
                "REQUEST_FIELDS_FORBIDDEN",
                f"GENESIS does not accept request-controlled disk, image, or command fields: {names}",
            )

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/phone-bootstrap.html"):
            self._send_ui()
            return
        if path in ("/GENESIS.html", "/genesis"):
            self._send_genesis_ui()
            return
        if path == "/v1/health":
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "service": "synapse-phone-bootstrap", "api_version": API_VERSION},
            )
            return
        if path == "/v2/health":
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "service": "synapse-genesis", "api_version": GENESIS_API_VERSION},
            )
            return

        if path.startswith("/v2/"):
            if not self._require_auth_v2():
                return
            try:
                manager = self._genesis()
                if path == "/v2/device":
                    snapshot = device_snapshot()
                    snapshot["genesis_api_version"] = GENESIS_API_VERSION
                    self._send_json(HTTPStatus.OK, {"ok": True, "device": snapshot})
                    return
                if path == "/v2/preflight":
                    self._send_json(HTTPStatus.OK, {"ok": True, "preflight": manager.preflight()})
                    return
                if path == "/v2/image":
                    self._send_json(HTTPStatus.OK, {"ok": True, "image": manager.image_status()})
                    return
                if path == "/v2/install/status":
                    self._send_json(HTTPStatus.OK, {"ok": True, "install": manager.status()})
                    return
                if path == "/v2/install/receipt":
                    self._send_json(HTTPStatus.OK, {"ok": True, "receipt": manager.receipt()})
                    return
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": {"code": "ROUTE_NOT_FOUND", "message": "route not found"}},
                )
            except GenesisError as exc:
                self._send_genesis_error(exc)
            return

        if not self._require_auth():
            return
        if path == "/v1/device":
            self._send_json(HTTPStatus.OK, {"ok": True, "device": device_snapshot()})
            return
        if path == "/v1/install/status":
            self._send_json(HTTPStatus.OK, {"ok": True, "install": self.server.install_manager.snapshot()})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "route not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/v2/"):
            if not self._require_auth_v2():
                return
            try:
                data = self._read_json()
                manager = self._genesis()
                if path == "/v2/hello":
                    self._reject_genesis_control_fields(data, allowed={"message"})
                    message = str(data.get("message") or "hey, I'm here")[:200]
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "received": message,
                            "reply": "Synapse GENESIS laptop here.",
                            "hostname": socket.gethostname(),
                        },
                    )
                    return
                if path == "/v2/install/arm":
                    self._reject_genesis_control_fields(data, allowed=set())
                    self._send_json(HTTPStatus.OK, {"ok": True, "arm": manager.arm()})
                    return
                if path == "/v2/install/start":
                    self._reject_genesis_control_fields(data, allowed={"challenge_id", "acknowledgement"})
                    challenge_id = str(data.get("challenge_id") or "")
                    acknowledgement = str(data.get("acknowledgement") or "")
                    if not challenge_id or not acknowledgement:
                        raise GenesisError("ARM_MISMATCH", "challenge_id and acknowledgement are required")
                    state = manager.start(challenge_id, acknowledgement)
                    self._send_json(HTTPStatus.ACCEPTED, {"ok": True, "install": state})
                    return
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": {"code": "ROUTE_NOT_FOUND", "message": "route not found"}},
                )
            except BootstrapError as exc:
                self._send_genesis_error(GenesisError("BAD_REQUEST", str(exc)))
            except GenesisError as exc:
                self._send_genesis_error(exc)
            return

        if not self._require_auth():
            return
        try:
            data = self._read_json()
            if path == "/v1/hello":
                message = str(data.get("message") or "hey, I'm here")[:200]
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "received": message,
                        "reply": "Synapse laptop here.",
                        "hostname": socket.gethostname(),
                    },
                )
                return
            if path == "/v1/install/start":
                state = self.server.install_manager.start()
                self._send_json(HTTPStatus.ACCEPTED, {"ok": True, "install": state})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "route not found"})
        except BootstrapError as exc:
            status = HTTPStatus.CONFLICT if "already running" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_json(status, {"ok": False, "error": str(exc)})


def resolve_ui_path(value: str | None) -> Path | None:
    if value:
        return Path(value).expanduser().resolve()
    installed = Path("/usr/share/synapse/phone-bootstrap.html")
    if installed.is_file():
        return installed
    source = Path(__file__).resolve().parents[2] / "phone-bootstrap" / "phone-bootstrap.html"
    return source if source.is_file() else None


def resolve_genesis_ui_path(value: str | None) -> Path | None:
    if value:
        return Path(value).expanduser().resolve()
    installed = Path("/usr/share/synapse/GENESIS.html")
    if installed.is_file():
        return installed
    source = Path(__file__).resolve().parents[2] / "phone-bootstrap" / "GENESIS.html"
    return source if source.is_file() else None


def write_token_file(path: Path | None, token: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synapse-phone-bootstrap",
        description="Authenticated local API and phone UI for Synapse/COSMOS bootstrap and GENESIS installation",
    )
    parser.add_argument("--listen", default="127.0.0.1", help="bind address; use 0.0.0.0 for a trusted USB/local link")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=os.environ.get("SYNAPSE_PHONE_TOKEN"))
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--ui")
    parser.add_argument("--allow-install", action="store_true")
    parser.add_argument("--activate", action="store_true", help="activate COSMOS after checkout when a supported launcher is found")
    parser.add_argument("--cosmos-repo", default=DEFAULT_COSMOS_REPO)
    parser.add_argument("--cosmos-branch", default=DEFAULT_COSMOS_BRANCH)
    parser.add_argument("--install-root", type=Path, default=Path.home() / "COSMOS")
    parser.add_argument("--genesis-ui")
    parser.add_argument("--genesis-manifest", type=Path)
    parser.add_argument("--genesis-image", type=Path)
    parser.add_argument(
        "--genesis-staging-dir",
        type=Path,
        default=Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "synapse-genesis",
    )
    parser.add_argument("--genesis-installer-mode", action="store_true")
    parser.add_argument("--genesis-simulation", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (1 <= args.port <= 65535):
        print("synapse-phone-bootstrap: port must be in 1..65535")
        return 2
    token = args.token or secrets.token_urlsafe(24)
    write_token_file(args.token_file, token)
    manager = InstallManager(
        repo_url=args.cosmos_repo,
        branch=args.cosmos_branch,
        install_root=args.install_root,
        allow_install=args.allow_install,
        activate=args.activate,
    )
    genesis_manager = GenesisManager(
        manifest_path=args.genesis_manifest,
        image_path=args.genesis_image,
        staging_dir=args.genesis_staging_dir,
        installer_mode=args.genesis_installer_mode,
        simulation=args.genesis_simulation,
    )
    server = BootstrapServer(
        (args.listen, args.port),
        token=token,
        install_manager=manager,
        ui_path=resolve_ui_path(args.ui),
        genesis_manager=genesis_manager,
        genesis_ui_path=resolve_genesis_ui_path(args.genesis_ui),
    )
    print(f"Synapse Phone Bootstrap listening on http://{args.listen}:{args.port}")
    print(f"Pairing token: {token}")
    print("v1 endpoints: /v1/health /v1/device /v1/hello /v1/install/start /v1/install/status")
    print("v2 endpoints: /v2/health /v2/device /v2/preflight /v2/image /v2/install/arm /v2/install/start /v2/install/status /v2/install/receipt")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
