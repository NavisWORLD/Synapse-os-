from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
from typing import Any
from urllib.parse import urlparse

from .usb_flash import UsbFlashError, UsbFlashManager


API_VERSION = "1.0"
DEFAULT_PORT = 8788
MAX_BODY = 64 * 1024
FORBIDDEN_REQUEST_FIELDS = frozenset(
    {
        "target",
        "target_path",
        "disk",
        "disk_path",
        "device",
        "device_path",
        "image",
        "image_path",
        "checksum_path",
        "manifest",
        "manifest_path",
        "repo",
        "repo_url",
        "url",
        "command",
        "commands",
        "shell",
        "argv",
        "exec",
    }
)


class FlashServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        token: str,
        manager: Any,
        ui_path: Path | None,
    ) -> None:
        super().__init__(address, FlashHandler)
        self.token = token
        self.manager = manager
        self.ui_path = ui_path


class FlashHandler(BaseHTTPRequestHandler):
    server: FlashServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"usb-flasher: {self.address_string()} - {fmt % args}")

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

    def _send_ui(self) -> None:
        path = self.server.ui_path
        if path is None or not path.is_file():
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": {"code": "UI_MISSING", "message": "FLASH_USB.html is not installed"}},
            )
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

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
        self._send_json(
            HTTPStatus.UNAUTHORIZED,
            {"ok": False, "error": {"code": "AUTH_REQUIRED", "message": "pairing token required"}},
        )
        return False

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise UsbFlashError("BAD_REQUEST", "invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY:
            raise UsbFlashError("BAD_REQUEST", "request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UsbFlashError("BAD_REQUEST", "body must be valid JSON") from exc
        if not isinstance(data, dict):
            raise UsbFlashError("BAD_REQUEST", "JSON body must be an object")
        return data

    def _reject_control_fields(self, data: dict[str, Any], *, allowed: set[str]) -> None:
        forbidden = (set(data) - allowed) | (set(data) & FORBIDDEN_REQUEST_FIELDS)
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise UsbFlashError(
                "REQUEST_FIELDS_FORBIDDEN",
                f"USB flasher does not accept request-controlled disk, image, URL, or command fields: {names}",
            )

    def _send_error(self, exc: UsbFlashError) -> None:
        if exc.code == "AUTH_REQUIRED":
            status = HTTPStatus.UNAUTHORIZED
        elif exc.code in {"FLASH_ALREADY_RUNNING", "ARM_REPLAYED", "ARM_EXPIRED"}:
            status = HTTPStatus.CONFLICT
        else:
            status = HTTPStatus.BAD_REQUEST
        self._send_json(status, {"ok": False, "error": {"code": exc.code, "message": exc.message}})

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/FLASH_USB.html", "/flash-usb"}:
            self._send_ui()
            return
        if path == "/v1/health":
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "service": "synapse-usb-flasher", "api_version": API_VERSION},
            )
            return
        if not path.startswith("/v1/"):
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": {"code": "ROUTE_NOT_FOUND", "message": "route not found"}},
            )
            return
        if not self._require_auth():
            return
        try:
            manager = self.server.manager
            if path == "/v1/capabilities":
                self._send_json(HTTPStatus.OK, {"ok": True, "capabilities": manager.capabilities()})
                return
            if path == "/v1/devices":
                self._send_json(HTTPStatus.OK, {"ok": True, "devices": manager.devices()})
                return
            if path == "/v1/image":
                self._send_json(HTTPStatus.OK, {"ok": True, "image": manager.image_status()})
                return
            if path == "/v1/preflight":
                self._send_json(HTTPStatus.OK, {"ok": True, "preflight": manager.preflight()})
                return
            if path == "/v1/flash/status":
                self._send_json(HTTPStatus.OK, {"ok": True, "flash": manager.status()})
                return
            if path == "/v1/flash/receipt":
                self._send_json(HTTPStatus.OK, {"ok": True, "receipt": manager.receipt()})
                return
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": {"code": "ROUTE_NOT_FOUND", "message": "route not found"}},
            )
        except UsbFlashError as exc:
            self._send_error(exc)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/v1/"):
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": {"code": "ROUTE_NOT_FOUND", "message": "route not found"}},
            )
            return
        if not self._require_auth():
            return
        try:
            data = self._read_json()
            manager = self.server.manager
            if path == "/v1/hello":
                self._reject_control_fields(data, allowed={"message"})
                message = str(data.get("message") or "hey, I'm here")[:200]
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "received": message,
                        "reply": "Synapse USB flasher here.",
                        "hostname": socket.gethostname(),
                    },
                )
                return
            if path == "/v1/image/prepare":
                self._reject_control_fields(data, allowed=set())
                self._send_json(HTTPStatus.OK, {"ok": True, "image": manager.prepare_image()})
                return
            if path == "/v1/flash/arm":
                self._reject_control_fields(data, allowed=set())
                self._send_json(HTTPStatus.OK, {"ok": True, "arm": manager.arm()})
                return
            if path == "/v1/flash/start":
                self._reject_control_fields(data, allowed={"challenge_id", "acknowledgement"})
                challenge_id = str(data.get("challenge_id") or "")
                acknowledgement = str(data.get("acknowledgement") or "")
                if not challenge_id or not acknowledgement:
                    raise UsbFlashError("ARM_MISMATCH", "challenge_id and acknowledgement are required")
                state = manager.start(challenge_id, acknowledgement)
                self._send_json(HTTPStatus.ACCEPTED, {"ok": True, "flash": state})
                return
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": {"code": "ROUTE_NOT_FOUND", "message": "route not found"}},
            )
        except UsbFlashError as exc:
            self._send_error(exc)


def resolve_ui_path(value: str | None) -> Path | None:
    if value:
        return Path(value).expanduser().resolve()
    installed = Path("/usr/share/synapse/FLASH_USB.html")
    if installed.is_file():
        return installed
    source = Path(__file__).resolve().parents[2] / "phone-bootstrap" / "FLASH_USB.html"
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


def digest_from_file(path: Path) -> str:
    try:
        first = path.read_text(encoding="utf-8").strip().split()[0].lower()
    except (OSError, IndexError) as exc:
        raise UsbFlashError("IMAGE_DIGEST_INVALID", f"cannot read SHA-256 file: {path}") from exc
    return first


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synapse-usb-flash-server",
        description="Authenticated fixed-purpose Synapse OS removable USB flasher",
    )
    parser.add_argument("--listen", default="127.0.0.1", help="bind address; use 0.0.0.0 only on a trusted local link")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=os.environ.get("SYNAPSE_USB_FLASH_TOKEN"))
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--ui")
    parser.add_argument("--image", type=Path, required=True)
    digest = parser.add_mutually_exclusive_group(required=True)
    digest.add_argument("--sha256")
    digest.add_argument("--sha256-file", type=Path)
    parser.add_argument("--simulation", action="store_true")
    parser.add_argument("--arm-ttl", type=float, default=120.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (1 <= args.port <= 65535):
        print("synapse-usb-flash-server: port must be in 1..65535")
        return 2
    expected = str(args.sha256 or "").strip().lower()
    if args.sha256_file:
        expected = digest_from_file(args.sha256_file)
    token = args.token or secrets.token_urlsafe(24)
    write_token_file(args.token_file, token)
    manager = UsbFlashManager(
        image_path=args.image,
        expected_sha256=expected,
        simulation=args.simulation,
        arm_ttl=args.arm_ttl,
    )
    server = FlashServer(
        (args.listen, args.port),
        token=token,
        manager=manager,
        ui_path=resolve_ui_path(args.ui),
    )
    print(f"Synapse USB Flasher listening on http://{args.listen}:{args.port}/FLASH_USB.html")
    print(f"Pairing token: {token}")
    print("Target policy: unique removable USB disk only; internal disks are ineligible.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
