from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from BEASTOS_WEB_MACHINE.bridge.server import (
    BridgeState,
    origin_allowed,
    safe_static_path,
    validate_payload,
)
from BEASTOS_WEB_MACHINE.bridge.vm import InMemoryVMBackend, MachineSpec


class OriginPolicyTests(unittest.TestCase):
    def test_same_loopback_origin_is_allowed(self) -> None:
        self.assertTrue(origin_allowed("http://127.0.0.1:8790", listen_port=8790))
        self.assertTrue(origin_allowed("http://localhost:8790", listen_port=8790))

    def test_malicious_or_wrong_port_origin_is_rejected(self) -> None:
        self.assertFalse(origin_allowed("https://evil.example", listen_port=8790))
        self.assertFalse(origin_allowed("http://127.0.0.1:9999", listen_port=8790))


class PayloadPolicyTests(unittest.TestCase):
    def test_arbitrary_shell_and_path_fields_are_rejected(self) -> None:
        for field in ("shell", "exec", "command", "argv", "path", "repo", "url"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    validate_payload({field: "boom"}, allowed={"brain"})

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_payload({"brain": "a", "surprise": True}, allowed={"brain"})


class StaticPathTests(unittest.TestCase):
    def test_path_traversal_never_escapes_web_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "index.html").write_text("ok", encoding="utf-8")
            self.assertEqual(safe_static_path(root, "/"), root / "index.html")
            self.assertIsNone(safe_static_path(root, "/../../etc/passwd"))
            self.assertIsNone(safe_static_path(root, "/%2e%2e/%2e%2e/etc/passwd"))


class BridgeStateTests(unittest.TestCase):
    def test_model_swap_revokes_authority_and_destroys_old_body(self) -> None:
        backend = InMemoryVMBackend()
        state = BridgeState(vm_backend=backend)
        state.clock_in("brain-a")
        state.grant("vm.control")
        state.machine_create(MachineSpec(memory_mb=1024, cpus=1))
        self.assertTrue(backend.running)
        result = state.clock_in("brain-b")
        self.assertFalse(backend.running)
        self.assertEqual(result["active_brain"], "brain-b")
        self.assertEqual(result["grants"], [])
        self.assertEqual(result["machine"]["state"], "DESTROYED")

    def test_master_privacy_stops_vm_and_revokes_all_authority(self) -> None:
        backend = InMemoryVMBackend()
        state = BridgeState(vm_backend=backend)
        state.clock_in("brain-a")
        state.grant("vm.control")
        state.grant("filesystem.write")
        state.machine_create(MachineSpec(memory_mb=1024, cpus=1))
        result = state.master_privacy_stop()
        self.assertFalse(backend.running)
        self.assertEqual(result["grants"], [])
        self.assertEqual(result["machine"]["state"], "DESTROYED")

    def test_unrecognized_grant_is_rejected(self) -> None:
        state = BridgeState(vm_backend=InMemoryVMBackend())
        state.clock_in("brain-a")
        with self.assertRaises(ValueError):
            state.grant("arbitrary.shell")


if __name__ == "__main__":
    unittest.main()
