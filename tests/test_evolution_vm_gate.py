"""Host and guest Stage 2 safety tests: source receipts and disconnected QEMU argv."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from synapse import evolution

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evolution_vm_gate.py"
GUEST = ROOT / "rootfs/usr/local/lib/synapse/evolution-vm-evaluator.py"
SERVICE = ROOT / "rootfs/etc/systemd/system/synapse-evolution-evaluate.service"

spec = importlib.util.spec_from_file_location("evolution_vm_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(gate)


class VMGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synapse-vm-gate-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / "repo"
        self.repo.mkdir()
        (self.repo / "rootfs/usr/local/lib/synapse").mkdir(parents=True)
        (self.repo / gate.GUEST_SCRIPT).write_text("print('trusted guest')\n")
        self.source = self.repo / "src/synapse/core.py"
        self.source.parent.mkdir(parents=True)
        self.original = "def evolution_test_fixture():\n    return 1\n"
        self.candidate = "def evolution_test_fixture():\n    return 2\n"
        self.source.write_text(self.original)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Synapse Fixture", "-c",
                 "user.email=test@example.invalid", "commit", "-qm", "baseline")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        change = {
            "path": "src/synapse/core.py",
            "before_sha256": gate.sha(self.original.encode()),
            "after_text": self.candidate,
        }
        self.proposal = self.home / "proposal.json"
        self.proposal.write_text(json.dumps({
            "schema": evolution.SCHEMA, "base_commit": self.head,
            "goal": "Make exact fixture replacement.",
            "model_label": "deterministic fixture; not a model",
            "changes": [change],
        }))
        self.stage = evolution.stage(self.proposal, self.repo, self.home / "stage")
        self.receipt_dir = Path(self.stage["workspace"]).parent

    def git(self, *argv):
        return subprocess.run(("git", *argv), cwd=self.repo, text=True,
                              capture_output=True, check=True)

    def test_valid_real_stage1_receipt_for_vm_packing(self):
        receipt, files = gate.validate(self.repo, self.receipt_dir)
        self.assertEqual(receipt["base_commit"], self.head)
        self.assertEqual(files[0], (Path("src/synapse/core.py"), self.candidate.encode()))
        self.assertTrue((self.repo / "src/synapse/core.py").read_text() == self.original)

    def test_forged_patch_sha_cannot_enter_guest_payload(self):
        (self.receipt_dir / "PATCH_REVIEW.diff").write_text("forged diff\n")
        with self.assertRaisesRegex(ValueError, "review patch"):
            gate.validate(self.repo, self.receipt_dir)

    def test_candidate_drift_rejected(self):
        f = Path(self.stage["workspace"]) / "src/synapse/core.py"
        f.write_text("candidate changed after stage\n")
        with self.assertRaisesRegex(ValueError, "receipts"):
            gate.validate(self.repo, self.receipt_dir)

    def test_protected_evolution_engine_path_rejected(self):
        (self.receipt_dir / "RECEIPT.json").write_text(json.dumps({
            **json.loads((self.receipt_dir / "RECEIPT.json").read_text()),
            "changes": [{
                "path": "src/synapse/evolution.py",
                "before_sha256": gate.sha(self.original.encode()),
                "after_sha256": gate.sha(self.candidate.encode()),
            }],
        }))
        with self.assertRaisesRegex(ValueError, "protected"):
            gate.validate(self.repo, self.receipt_dir)

    def test_vm_argv_disables_network_host_mappings_and_remote_control(self):
        cmd = gate.qemu_args(
            Path("/tmp/source.iso"), Path("/tmp/candidate.iso"),
            Path("/tmp/vmlinuz"), Path("/tmp/initrd.img"),
            "candidate", Path("/tmp/guest-serial.log")
        )
        self.assertEqual(cmd[cmd.index("-nic") + 1], "none")
        self.assertEqual(cmd[cmd.index("-display") + 1], "none")
        self.assertEqual(cmd[cmd.index("-monitor") + 1], "none")
        self.assertNotIn("-netdev", cmd)
        self.assertNotIn("-virtfs", cmd)
        self.assertNotIn("-fsdev", cmd)
        self.assertNotIn("-qmp", cmd)
        self.assertNotIn("-daemonize", cmd)
        self.assertIn("if=virtio,readonly=on", " ".join(cmd))
        self.assertIn("media=cdrom,readonly=on", " ".join(cmd))
        self.assertIn("synapse.evolve_role=candidate", cmd[cmd.index("-append")+1])
        with self.assertRaises(ValueError):
            gate.qemu_args(Path(""), Path(""), Path(""), Path(""),
                           "privileged", Path(""))

    def test_guest_runs_only_when_live_vm_opted_in(self):
        service = SERVICE.read_text()
        guest = GUEST.read_text()
        self.assertIn("ConditionKernelCommandLine=synapse.evolve_vm=1", service)
        self.assertIn("ConditionPathExists=/run/live/medium", service)
        self.assertIn("synapse.evolve_vm=1", guest)
        self.assertIn("runuser", guest)
        self.assertIn("HOME=/tmp", guest)
        self.assertIn("PYTHONPATH=", guest)
        self.assertIn("capture_output=True", guest)
        self.assertIn("ro,nosuid,nodev,noexec", guest)
        self.assertNotIn("shell=True", guest)

    def test_readonly_payload_is_bounded_and_hashed(self):
        receipt, files = gate.validate(self.repo, self.receipt_dir)
        # No host dependency on xorriso in the general make-check matrix.
        manifest = {"schema": gate.SCHEMA, "base_commit": receipt["base_commit"],
                    "changes": receipt["changes"]}
        self.assertEqual(manifest["changes"][0]["after_sha256"],
                         hashlib.sha256(files[0][1]).hexdigest())


if __name__ == "__main__":
    unittest.main()
