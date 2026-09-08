from __future__ import annotations

import unittest

from BEASTOS_WEB_MACHINE.bridge.adapter import BeastAdapter, BeastRelease
from BEASTOS_WEB_MACHINE.bridge.authority import AuthorityLedger
from BEASTOS_WEB_MACHINE.bridge.files import FileScope, FileScopePolicy
from BEASTOS_WEB_MACHINE.bridge.network import NetworkAuthority
from BEASTOS_WEB_MACHINE.bridge.provenance import ProvenanceLog
from BEASTOS_WEB_MACHINE.bridge.secrets import redact_secrets
from BEASTOS_WEB_MACHINE.bridge.vm import InMemoryVMBackend, MachineSpec, VMController
from BEASTOS_WEB_MACHINE.bridge.capabilities import CapabilityRegistry, CapabilityState


class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_never_upgrades_unsupported_capability(self) -> None:
        registry = CapabilityRegistry()
        registry.observe("webusb", supported=False)
        self.assertEqual(registry.state("webusb"), CapabilityState.UNAVAILABLE)
        with self.assertRaises(ValueError):
            registry.authorize("webusb")

    def test_permission_flow_is_explicit(self) -> None:
        registry = CapabilityRegistry()
        registry.observe("camera", supported=True, permission_required=True)
        self.assertEqual(registry.state("camera"), CapabilityState.PERMISSION_REQUIRED)
        registry.deny("camera")
        self.assertEqual(registry.state("camera"), CapabilityState.DENIED)
        registry.observe("camera", supported=True, permission_required=True)
        registry.authorize("camera")
        self.assertEqual(registry.state("camera"), CapabilityState.AUTHORIZED)


class AuthorityLedgerTests(unittest.TestCase):
    def test_model_swap_revokes_all_brain_scoped_authority(self) -> None:
        ledger = AuthorityLedger()
        ledger.clock_in("brain-a")
        ledger.grant("camera")
        ledger.grant("vm.control")
        self.assertTrue(ledger.allowed("camera"))
        ledger.clock_in("brain-b")
        self.assertEqual(ledger.active_brain, "brain-b")
        self.assertFalse(ledger.allowed("camera"))
        self.assertFalse(ledger.allowed("vm.control"))
        self.assertEqual(ledger.grants(), set())

    def test_master_privacy_revokes_active_grants(self) -> None:
        ledger = AuthorityLedger()
        ledger.clock_in("brain-a")
        ledger.grant("microphone")
        ledger.grant("filesystem.write")
        revoked = ledger.master_privacy_stop()
        self.assertEqual(revoked, {"microphone", "filesystem.write"})
        self.assertEqual(ledger.grants(), set())

    def test_grant_without_brain_fails_closed(self) -> None:
        ledger = AuthorityLedger()
        with self.assertRaises(PermissionError):
            ledger.grant("camera")


class FileBoundaryTests(unittest.TestCase):
    def test_upload_does_not_silently_become_persistent(self) -> None:
        policy = FileScopePolicy()
        self.assertEqual(policy.initial_upload_scope(), FileScope.TEMPORARY_ATTACHMENT)
        self.assertFalse(
            policy.can_transfer(FileScope.TEMPORARY_ATTACHMENT, FileScope.PERSISTENT_BEAST_MEMORY)
        )

    def test_explicit_transfer_token_is_single_path(self) -> None:
        policy = FileScopePolicy()
        token = policy.authorize_transfer(FileScope.VM_EPHEMERAL_STORAGE, FileScope.WORKSPACE_KNOWLEDGE)
        self.assertTrue(
            policy.can_transfer(
                FileScope.VM_EPHEMERAL_STORAGE,
                FileScope.WORKSPACE_KNOWLEDGE,
                token=token,
            )
        )
        self.assertFalse(
            policy.can_transfer(
                FileScope.VM_EPHEMERAL_STORAGE,
                FileScope.PERSISTENT_BEAST_MEMORY,
                token=token,
            )
        )


class SecretRedactionTests(unittest.TestCase):
    def test_common_secret_forms_are_redacted(self) -> None:
        text = "Authorization: Bearer abc.def.ghi OPENAI_API_KEY=sk-test-123 password=hunter2"
        redacted = redact_secrets(text)
        self.assertNotIn("abc.def.ghi", redacted)
        self.assertNotIn("sk-test-123", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED]"), 3)


class BeastAdapterTests(unittest.TestCase):
    def test_release_pin_is_reproducible(self) -> None:
        release = BeastRelease.v060()
        self.assertEqual(release.commit, "331f03c5d6a4aab0b2e32314293e36c7a94be393")
        self.assertEqual(
            release.sha256,
            "c2a5bf5e3cb972ec3e5f1aa45f06d7e77e9b6de115e049f06e830a1f4c312ad2",
        )
        self.assertTrue(release.prerelease)

    def test_adapter_has_no_silent_provider_fallback(self) -> None:
        adapter = BeastAdapter(endpoint="http://127.0.0.1:8766", provider="LOCAL_HOST")
        request = adapter.build_request("hello")
        self.assertEqual(request["provider"], "LOCAL_HOST")
        self.assertFalse(request["allow_fallback"])


class NetworkAuthorityTests(unittest.TestCase):
    def test_network_status_does_not_imply_control(self) -> None:
        authority = NetworkAuthority()
        authority.update_status(online=True, interface="wlan0")
        self.assertTrue(authority.status()["online"])
        self.assertFalse(authority.can_control())
        with self.assertRaises(PermissionError):
            authority.request_control("scan")

    def test_network_control_requires_explicit_grant(self) -> None:
        authority = NetworkAuthority()
        authority.grant_control({"status", "scan"})
        self.assertTrue(authority.can_control("scan"))
        self.assertFalse(authority.can_control("join"))


class VMControllerTests(unittest.TestCase):
    def test_disposable_vm_requires_authority_and_dies_cleanly(self) -> None:
        ledger = AuthorityLedger()
        ledger.clock_in("brain-b")
        backend = InMemoryVMBackend()
        vm = VMController(backend, ledger)
        with self.assertRaises(PermissionError):
            vm.create(MachineSpec(memory_mb=1024, cpus=1))
        ledger.grant("vm.control")
        receipt = vm.create(MachineSpec(memory_mb=1024, cpus=1))
        self.assertEqual(receipt["state"], "RUNNING")
        destroyed = vm.destroy()
        self.assertEqual(destroyed["state"], "DESTROYED")
        self.assertFalse(backend.running)
        self.assertFalse(ledger.allowed("vm.control"))

    def test_vm_controller_exposes_no_arbitrary_shell_method(self) -> None:
        ledger = AuthorityLedger()
        vm = VMController(InMemoryVMBackend(), ledger)
        self.assertFalse(hasattr(vm, "shell"))
        self.assertFalse(hasattr(vm, "exec"))


class ProvenanceTests(unittest.TestCase):
    def test_records_are_redacted_and_hash_chained(self) -> None:
        log = ProvenanceLog()
        first = log.append("grant", {"capability": "camera", "token": "sk-secret"})
        second = log.append("revoke", {"capability": "camera"})
        self.assertEqual(second["previous_hash"], first["hash"])
        self.assertNotIn("sk-secret", str(first))


if __name__ == "__main__":
    unittest.main()
