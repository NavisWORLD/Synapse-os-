from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from synapse.usb_flash import UsbFlashError
from synapse.usb_flash_server import FlashServer, FlashHandler


class FakeManager:
    def __init__(self) -> None:
        self.arm_value = {
            "challenge_id": "challenge-1",
            "acknowledgement": "FLASH:target:IMAGE:hash:SIZE:1",
            "target_fingerprint": "target",
            "image_sha256": "hash",
            "expires_at": 9999999999,
        }
        self.started = None

    def capabilities(self):
        return {"helper": True, "raw_write": True, "verification": "full-sha256-readback"}

    def devices(self):
        return [{"path": "/dev/sdb", "eligible": True, "fingerprint": "target"}]

    def image_status(self):
        return {"verified": True, "sha256": "hash", "size": 1, "filename": "SynapseOS-Nebula-amd64.iso"}

    def preflight(self):
        return {"ready": True, "target": {"fingerprint": "target"}, "image": self.image_status()}

    def prepare_image(self):
        return self.image_status()

    def arm(self):
        return dict(self.arm_value)

    def start(self, challenge_id: str, acknowledgement: str):
        self.started = (challenge_id, acknowledgement)
        return {"phase": "queued", "progress": 1}

    def status(self):
        return {"phase": "idle", "progress": 0, "message": "Ready", "error": None}

    def receipt(self):
        return None


class UsbFlashHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.ui = root / "FLASH_USB.html"
        self.ui.write_text("<!doctype html><title>FLASH USB</title>", encoding="utf-8")
        self.manager = FakeManager()
        self.server = FlashServer(("127.0.0.1", 0), token="secret", manager=self.manager, ui_path=self.ui)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
        self.td.cleanup()

    def request(self, path: str, *, method: str = "GET", body: dict | None = None, token: str | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Synapse-Token"] = token
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=2) as res:
                raw = res.read()
                ctype = res.headers.get("Content-Type", "")
                return res.status, raw, ctype
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers.get("Content-Type", "")

    def json_request(self, *args, **kwargs):
        status, raw, _ = self.request(*args, **kwargs)
        return status, json.loads(raw.decode("utf-8"))

    def test_health_and_ui_are_public(self) -> None:
        status, payload = self.json_request("/v1/health")
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        self.assertEqual("synapse-usb-flasher", payload["service"])
        status, raw, ctype = self.request("/FLASH_USB.html")
        self.assertEqual(200, status)
        self.assertIn("text/html", ctype)
        self.assertIn(b"FLASH USB", raw)

    def test_authenticated_reads_require_pairing_token(self) -> None:
        for path in (
            "/v1/capabilities",
            "/v1/devices",
            "/v1/image",
            "/v1/preflight",
            "/v1/flash/status",
            "/v1/flash/receipt",
        ):
            status, payload = self.json_request(path)
            self.assertEqual(401, status, path)
            self.assertEqual("AUTH_REQUIRED", payload["error"]["code"], path)

    def test_authenticated_read_routes(self) -> None:
        for path in (
            "/v1/capabilities",
            "/v1/devices",
            "/v1/image",
            "/v1/preflight",
            "/v1/flash/status",
            "/v1/flash/receipt",
        ):
            status, payload = self.json_request(path, token="secret")
            self.assertEqual(200, status, path)
            self.assertTrue(payload["ok"], path)

    def test_forbidden_request_control_fields_are_rejected(self) -> None:
        forbidden = [
            {"disk_path": "/dev/nvme0n1"},
            {"target": "/dev/sdb"},
            {"image_path": "/tmp/evil.iso"},
            {"repo_url": "https://example.invalid/repo"},
            {"shell": "rm -rf /"},
            {"command": ["dd", "if=x", "of=/dev/sda"]},
        ]
        for body in forbidden:
            status, payload = self.json_request("/v1/flash/arm", method="POST", body=body, token="secret")
            self.assertEqual(400, status, body)
            self.assertEqual("REQUEST_FIELDS_FORBIDDEN", payload["error"]["code"], body)

    def test_arm_and_start_only_pass_bound_challenge(self) -> None:
        status, payload = self.json_request("/v1/flash/arm", method="POST", body={}, token="secret")
        self.assertEqual(200, status)
        arm = payload["arm"]
        status, payload = self.json_request(
            "/v1/flash/start",
            method="POST",
            body={"challenge_id": arm["challenge_id"], "acknowledgement": arm["acknowledgement"]},
            token="secret",
        )
        self.assertEqual(202, status)
        self.assertEqual((arm["challenge_id"], arm["acknowledgement"]), self.manager.started)

    def test_prepare_image_has_no_request_controlled_path(self) -> None:
        status, payload = self.json_request("/v1/image/prepare", method="POST", body={}, token="secret")
        self.assertEqual(200, status)
        self.assertTrue(payload["image"]["verified"])
        status, payload = self.json_request(
            "/v1/image/prepare",
            method="POST",
            body={"image": "/tmp/other.iso"},
            token="secret",
        )
        self.assertEqual(400, status)
        self.assertEqual("REQUEST_FIELDS_FORBIDDEN", payload["error"]["code"])


if __name__ == "__main__":
    unittest.main()
