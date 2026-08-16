from pathlib import Path
import http.client
import json
import tempfile
import threading
import unittest
from unittest import mock

from synapse.genesis import GenesisError
from synapse.phone_bootstrap import BootstrapServer, InstallManager, device_snapshot, resolve_ui_path


ROOT = Path(__file__).resolve().parents[1]


class FakeGenesisManager:
    def __init__(self):
        self.start_args = None

    def preflight(self):
        return {
            "ready": True,
            "device_fingerprint": "sha256:device",
            "hardware": {"arch": "amd64", "profile_id": "asus-cx1700cka-gallop"},
            "target": {"path": "/dev/mmcblk0", "fingerprint": "sha256:target", "size": 128_000_000_000},
            "image": {"verified": True, "image_sha256": "a" * 64},
            "power": {"ac_online": True, "battery_percent": 100.0},
            "boot": {"mode": "uefi", "genesis_kernel_marker": True},
            "checks": [],
            "installer_mode": True,
            "simulation": True,
        }

    def image_status(self):
        return {"verified": True, "image_sha256": "a" * 64, "verification": "hash-verified"}

    def status(self):
        return {"phase": "idle", "progress": 0, "message": "ready", "error": None}

    def receipt(self):
        return {"schema": "synapse-genesis-receipt/v1", "zenodo_doi": "10.5281/zenodo.17574447"}

    def arm(self):
        return {
            "challenge_id": "challenge-1",
            "device_fingerprint": "sha256:device",
            "target_disk_id": "sha256:target",
            "image_sha256": "a" * 64,
            "issued_at": 1,
            "expires_at": 121,
            "acknowledgement": "ERASE:sha256:target:INSTALL:" + "a" * 64,
        }

    def start(self, challenge_id, acknowledgement):
        self.start_args = (challenge_id, acknowledgement)
        return {"phase": "staging", "progress": 20, "message": "started", "error": None}


class PhoneBootstrapTests(unittest.TestCase):
    def test_device_snapshot_has_required_shape(self):
        hardware = {"arch": "amd64", "profile_id": "asus-cx1700cka-gallop", "certification_state": "physical-target"}
        with mock.patch("synapse.phone_bootstrap._network_addresses", return_value=[]), mock.patch(
            "synapse.phone_bootstrap._port_open", return_value=False
        ), mock.patch("synapse.phone_bootstrap.probe_hardware", return_value=hardware):
            data = device_snapshot()
        self.assertIn("hostname", data)
        self.assertIn("machine", data)
        self.assertIn("disk_root", data)
        self.assertIn("cosmos_ports", data)
        self.assertIn("11434", data["cosmos_ports"])
        self.assertEqual(data["hardware"]["profile_id"], "asus-cx1700cka-gallop")
        self.assertEqual(data["hardware"]["certification_state"], "physical-target")

    def test_install_is_disabled_without_explicit_flag(self):
        manager = InstallManager(install_root=Path("/tmp/unused-cosmos"), allow_install=False, activate=False)
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            manager.start()

    def test_existing_non_git_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "COSMOS"
            root.mkdir()
            manager = InstallManager(install_root=root, allow_install=True, activate=False)
            with mock.patch("synapse.phone_bootstrap.shutil.which", return_value="/usr/bin/git"):
                with self.assertRaisesRegex(RuntimeError, "not a git checkout"):
                    manager._install()

    def test_resolve_explicit_ui_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ui.html"
            path.write_text("<html></html>", encoding="utf-8")
            self.assertEqual(resolve_ui_path(str(path)), path.resolve())


class GenesisV2HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.v1_ui = root / "phone.html"
        self.v1_ui.write_text("<html>v1</html>", encoding="utf-8")
        self.genesis_ui = root / "GENESIS.html"
        self.genesis_ui.write_text("<html>GENESIS INSTALL SYNAPSE OS</html>", encoding="utf-8")
        self.genesis = FakeGenesisManager()
        self.server = BootstrapServer(
            ("127.0.0.1", 0),
            token="test-token",
            install_manager=InstallManager(install_root=root / "COSMOS", allow_install=False, activate=False),
            ui_path=self.v1_ui,
            genesis_manager=self.genesis,
            genesis_ui_path=self.genesis_ui,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method, path, body=None, *, auth=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["X-Synapse-Token"] = "test-token"
        raw = None if body is None else json.dumps(body)
        conn.request(method, path, body=raw, headers=headers)
        res = conn.getresponse()
        payload = res.read()
        content_type = res.getheader("Content-Type") or ""
        conn.close()
        if "application/json" in content_type:
            return res.status, json.loads(payload.decode("utf-8"))
        return res.status, payload.decode("utf-8")

    def test_v2_health_is_public(self):
        status, payload = self.request("GET", "/v2/health", auth=False)
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        self.assertEqual("2.0", payload["api_version"])
        self.assertEqual("synapse-genesis", payload["service"])

    def test_v2_read_endpoints_require_auth_with_structured_error(self):
        status, payload = self.request("GET", "/v2/preflight", auth=False)
        self.assertEqual(401, status)
        self.assertEqual("AUTH_REQUIRED", payload["error"]["code"])

    def test_v2_preflight_image_status_and_receipt(self):
        status, payload = self.request("GET", "/v2/preflight")
        self.assertEqual(200, status)
        self.assertTrue(payload["preflight"]["ready"])
        status, payload = self.request("GET", "/v2/image")
        self.assertEqual(200, status)
        self.assertTrue(payload["image"]["verified"])
        status, payload = self.request("GET", "/v2/install/status")
        self.assertEqual("idle", payload["install"]["phase"])
        status, payload = self.request("GET", "/v2/install/receipt")
        self.assertEqual("10.5281/zenodo.17574447", payload["receipt"]["zenodo_doi"])

    def test_v2_arm_and_start_pass_only_challenge_and_acknowledgement(self):
        status, payload = self.request("POST", "/v2/install/arm", {})
        self.assertEqual(200, status)
        armed = payload["arm"]
        status, payload = self.request(
            "POST",
            "/v2/install/start",
            {"challenge_id": armed["challenge_id"], "acknowledgement": armed["acknowledgement"]},
        )
        self.assertEqual(202, status)
        self.assertEqual((armed["challenge_id"], armed["acknowledgement"]), self.genesis.start_args)
        self.assertEqual("staging", payload["install"]["phase"])

    def test_v2_rejects_request_controlled_disk_image_or_command_fields(self):
        status, payload = self.request(
            "POST",
            "/v2/install/start",
            {
                "challenge_id": "challenge-1",
                "acknowledgement": "ack",
                "target": "/dev/sda",
                "image_path": "/tmp/evil.img",
                "command": "rm -rf /",
            },
        )
        self.assertEqual(400, status)
        self.assertEqual("REQUEST_FIELDS_FORBIDDEN", payload["error"]["code"])
        self.assertIsNone(self.genesis.start_args)

    def test_v2_genesis_errors_use_stable_error_shape(self):
        self.genesis.preflight = mock.Mock(side_effect=GenesisError("PREFLIGHT_FAILED", "blocked for test"))
        status, payload = self.request("GET", "/v2/preflight")
        self.assertEqual(400, status)
        self.assertEqual({"code": "PREFLIGHT_FAILED", "message": "blocked for test"}, payload["error"])

    def test_genesis_html_route_is_separate_from_v1_ui(self):
        status, body = self.request("GET", "/GENESIS.html", auth=False)
        self.assertEqual(200, status)
        self.assertIn("GENESIS INSTALL SYNAPSE OS", body)
        status, body = self.request("GET", "/phone-bootstrap.html", auth=False)
        self.assertEqual(200, status)
        self.assertIn("v1", body)


class GenesisHtmlSourceTests(unittest.TestCase):
    def test_genesis_html_source_and_image_copy_are_identical(self):
        source = ROOT / "phone-bootstrap" / "GENESIS.html"
        installed = ROOT / "rootfs" / "usr" / "share" / "synapse" / "GENESIS.html"
        self.assertTrue(source.is_file())
        self.assertTrue(installed.is_file())
        self.assertEqual(source.read_bytes(), installed.read_bytes())

    def test_genesis_html_contains_fixed_v2_flow_and_hold_confirmation(self):
        text = (ROOT / "phone-bootstrap" / "GENESIS.html").read_text(encoding="utf-8")
        for marker in (
            "/v2/health",
            "/v2/device",
            "/v2/preflight",
            "/v2/install/arm",
            "/v2/install/start",
            "/v2/install/status",
            "/v2/install/receipt",
            "HOLD_MS = 2500",
            "pointerdown",
            "pointerup",
            "THIS WILL REPLACE CHROMEOS",
            "INSTALL SYNAPSE OS",
            "target_disk_id",
            "image_sha256",
            "ERASE:${arm.target_disk_id}:INSTALL:${arm.image_sha256}",
            "localStorage",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("/shell", text)
        self.assertNotIn("/exec", text)

    def test_genesis_html_surfaces_hardware_image_target_and_receipt(self):
        text = (ROOT / "phone-bootstrap" / "GENESIS.html").read_text(encoding="utf-8")
        for marker in (
            "profile_id",
            "certification_state",
            "target.path",
            "image_sha256",
            "zenodo_doi",
            "receipt",
            "preflight.checks",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
