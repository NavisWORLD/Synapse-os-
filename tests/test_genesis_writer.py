from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from synapse.genesis import EXPECTED_LICENSE, EXPECTED_ZENODO_DOI, GenesisError, parse_lsblk_inventory
from synapse import genesis_writer
from synapse.genesis_writer import (
    partition_paths,
    run_install,
    validate_install_plan,
)


def disk(name="mmcblk0", *, rm=False, tran="mmc", serial="TARGET"):
    return {
        "name": name,
        "kname": name,
        "path": f"/dev/{name}",
        "type": "disk",
        "size": 128_000_000_000,
        "rm": rm,
        "rota": False,
        "tran": tran,
        "model": "TEST",
        "serial": serial,
        "pkname": None,
        "mountpoints": [None],
        "children": [],
    }


class GenesisWriterTests(unittest.TestCase):
    def _fixture(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        image = root / "filesystem.squashfs"
        image.write_bytes(b"rootfs" * 1024)
        image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
        inventory = parse_lsblk_inventory({"blockdevices": [disk()]})
        target = inventory[0]
        plan = {
            "schema": "synapse-genesis-plan/v1",
            "created_at": 1.0,
            "device_fingerprint": "sha256:device",
            "target": target.public(),
            "image_path": str(image),
            "manifest_path": str(root / "manifest.json"),
            "image_sha256": image_sha,
            "architecture": "amd64",
            "license": EXPECTED_LICENSE,
            "zenodo_doi": EXPECTED_ZENODO_DOI,
        }
        plan_path = root / "install-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        receipt_path = root / "receipt.json"
        receipt_path.write_text(json.dumps({"schema": "synapse-genesis-receipt/v1"}), encoding="utf-8")
        return td, root, image, target, inventory, plan, plan_path, receipt_path

    def test_partition_paths_handle_mmc_and_nvme_suffixes(self):
        self.assertEqual(("/dev/mmcblk0p1", "/dev/mmcblk0p2"), partition_paths("/dev/mmcblk0"))
        self.assertEqual(("/dev/nvme0n1p1", "/dev/nvme0n1p2"), partition_paths("/dev/nvme0n1"))
        self.assertEqual(("/dev/sda1", "/dev/sda2"), partition_paths("/dev/sda"))

    def test_simulation_validates_without_destructive_commands(self):
        td, _, _, _, inventory, _, plan_path, receipt_path = self._fixture()
        with td:
            calls = []
            result = run_install(
                plan_path,
                receipt_path,
                execute=False,
                inventory_probe=lambda: inventory,
                source_disk_probe=lambda: "/dev/sda",
                command_runner=lambda argv, **kwargs: calls.append(list(argv)) or "",
                euid=1000,
                cmdline="quiet splash",
            )
            self.assertEqual("simulated", result["final_state"])
            self.assertEqual([], calls)

    def test_execute_requires_root(self):
        td, _, _, _, inventory, _, plan_path, receipt_path = self._fixture()
        with td:
            with self.assertRaises(GenesisError) as ctx:
                run_install(
                    plan_path,
                    receipt_path,
                    execute=True,
                    inventory_probe=lambda: inventory,
                    source_disk_probe=lambda: "/dev/sda",
                    euid=1000,
                    cmdline="synapse.genesis=1",
                )
            self.assertEqual("INSTALLER_DISABLED", ctx.exception.code)

    def test_execute_requires_genesis_kernel_marker(self):
        td, _, _, _, inventory, _, plan_path, receipt_path = self._fixture()
        with td:
            with self.assertRaises(GenesisError) as ctx:
                run_install(
                    plan_path,
                    receipt_path,
                    execute=True,
                    inventory_probe=lambda: inventory,
                    source_disk_probe=lambda: "/dev/sda",
                    euid=0,
                    cmdline="quiet splash",
                )
            self.assertEqual("INSTALLER_DISABLED", ctx.exception.code)

    def test_target_fingerprint_mismatch_is_rejected(self):
        td, _, _, _, _, _, plan_path, receipt_path = self._fixture()
        other = parse_lsblk_inventory({"blockdevices": [disk(serial="OTHER")]})
        with td:
            with self.assertRaises(GenesisError) as ctx:
                validate_install_plan(
                    json.loads(plan_path.read_text(encoding="utf-8")),
                    inventory=other,
                    source_disk_path="/dev/sda",
                )
            self.assertEqual("ARM_MISMATCH", ctx.exception.code)

    def test_removable_or_usb_target_is_rejected(self):
        td, _, _, _, _, plan, _, _ = self._fixture()
        with td:
            removable = parse_lsblk_inventory({"blockdevices": [disk(rm=True, tran="usb")]})
            plan["target"] = removable[0].public()
            with self.assertRaises(GenesisError) as ctx:
                validate_install_plan(plan, inventory=removable, source_disk_path=None)
            self.assertEqual("TARGET_REMOVABLE", ctx.exception.code)

    def test_image_hash_mismatch_is_rejected_immediately_before_install(self):
        td, _, image, _, inventory, _, plan_path, receipt_path = self._fixture()
        with td:
            original = image.read_bytes()
            image.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            with self.assertRaises(GenesisError) as ctx:
                run_install(
                    plan_path,
                    receipt_path,
                    execute=False,
                    inventory_probe=lambda: inventory,
                    source_disk_probe=lambda: "/dev/sda",
                )
            self.assertEqual("IMAGE_HASH_MISMATCH", ctx.exception.code)

    def test_source_media_target_is_rejected(self):
        td, _, _, target, inventory, plan, _, _ = self._fixture()
        with td:
            plan["target"] = target.public()
            with self.assertRaises(GenesisError) as ctx:
                validate_install_plan(plan, inventory=inventory, source_disk_path=target.path)
            self.assertEqual("ARM_MISMATCH", ctx.exception.code)

    def test_installed_receipt_is_finalized_before_it_is_embedded(self):
        td, root, image, target, _, plan, _, _ = self._fixture()
        with td:
            mount_root = root / "mnt"
            (mount_root / "boot").mkdir(parents=True)
            (mount_root / "boot" / "vmlinuz-test").write_text("kernel", encoding="utf-8")
            (mount_root / "boot" / "initrd.img-test").write_text("initrd", encoding="utf-8")
            (mount_root / "etc").mkdir(parents=True)
            (mount_root / "etc" / "os-release").write_text("ID=synapseos\n", encoding="utf-8")
            (mount_root / "usr/share/doc/synapse-os").mkdir(parents=True)
            (mount_root / "usr/share/doc/synapse-os/LICENSE").write_text(EXPECTED_LICENSE, encoding="utf-8")
            (mount_root / "usr/share/doc/synapse-os/PROVENANCE.md").write_text(EXPECTED_ZENODO_DOI, encoding="utf-8")
            (mount_root / "usr/share/synapse").mkdir(parents=True)
            (mount_root / "usr/share/synapse/phone-bootstrap.html").write_text("bootstrap", encoding="utf-8")

            plan = dict(plan)
            plan["target"] = target.public()
            plan["image_path"] = str(image)
            receipt = {
                "schema": "synapse-genesis-receipt/v1",
                "license": EXPECTED_LICENSE,
                "zenodo_doi": EXPECTED_ZENODO_DOI,
                "final_state": "installing",
                "phases": [],
            }

            def fake_runner(argv, **kwargs):
                name = Path(argv[0]).name
                if name == "lsblk":
                    return ""
                if name == "blkid":
                    return "ROOT-UUID" if str(argv[-1]).endswith("p2") else "EFI-UUID"
                return ""

            with mock.patch("synapse.genesis_writer._require_tool", side_effect=lambda name: name):
                result = genesis_writer._partition_and_install(plan, receipt, fake_runner, mount_root)

            self.assertEqual("complete", result["final_state"])
            embedded = json.loads(
                (mount_root / "var/lib/synapse/genesis/receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual("complete", embedded["final_state"])
            self.assertEqual("complete", embedded["phases"][-1]["phase"])

    def test_execute_delegates_only_after_all_fixed_validations(self):
        td, root, _, _, inventory, _, plan_path, receipt_path = self._fixture()
        with td:
            seen = {}

            def fake_installer(plan, receipt, runner, mount_root):
                seen["plan"] = plan
                seen["receipt"] = receipt
                seen["mount_root"] = mount_root
                return {"final_state": "complete", "phases": ["partition", "extract", "bootloader", "verify"]}

            result = run_install(
                plan_path,
                receipt_path,
                execute=True,
                inventory_probe=lambda: inventory,
                source_disk_probe=lambda: "/dev/sda",
                euid=0,
                cmdline="quiet synapse.genesis=1",
                installer=fake_installer,
                mount_root=root / "mnt",
            )
            self.assertEqual("complete", result["final_state"])
            self.assertEqual("/dev/mmcblk0", seen["plan"]["target"]["path"])
            self.assertNotIn("command", seen["plan"])
            self.assertNotIn("shell", seen["plan"])


if __name__ == "__main__":
    unittest.main()
