from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from synapse.genesis import (
    EXPECTED_LICENSE,
    EXPECTED_ZENODO_DOI,
    GenesisError,
    GenesisManager,
    ImageManifest,
    parse_lsblk_inventory,
    select_install_target,
    verify_manifest,
)
from synapse.genesis_runtime import InstallerGenesisManager


GALLOP = {
    "arch": "amd64",
    "hwid": "GALLOP TEST-HWID",
    "profile_id": "asus-cx1700cka-gallop",
    "certification_state": "physical-target",
    "product_name": "ASUS Chromebook CX1700CKA",
}


def lsblk_payload(*devices: dict) -> dict:
    return {"blockdevices": list(devices)}


def disk(
    name: str,
    *,
    size: int = 128_000_000_000,
    rm: bool = False,
    tran: str | None = "mmc",
    serial: str | None = "SERIAL-A",
    mountpoints: list[str | None] | None = None,
) -> dict:
    return {
        "name": name,
        "kname": name,
        "path": f"/dev/{name}",
        "type": "disk",
        "size": size,
        "rm": rm,
        "rota": False,
        "tran": tran,
        "model": "TEST DISK",
        "serial": serial,
        "pkname": None,
        "mountpoints": mountpoints or [None],
        "children": [],
    }


class GenesisInventoryTests(unittest.TestCase):
    def test_unique_internal_emmc_is_selected(self):
        devices = parse_lsblk_inventory(lsblk_payload(disk("mmcblk0")))
        target = select_install_target(devices, source_disk_path=None)
        self.assertEqual("/dev/mmcblk0", target.path)
        self.assertFalse(target.removable)
        self.assertEqual("mmc", target.transport)
        self.assertTrue(target.fingerprint.startswith("sha256:"))

    def test_usb_or_removable_disk_is_never_selected(self):
        devices = parse_lsblk_inventory(
            lsblk_payload(
                disk("sda", rm=True, tran="usb", serial="USB"),
                disk("mmcblk0", tran="mmc", serial="INTERNAL"),
            )
        )
        target = select_install_target(devices, source_disk_path="/dev/sda")
        self.assertEqual("/dev/mmcblk0", target.path)

    def test_ambiguous_internal_targets_fail_closed(self):
        devices = parse_lsblk_inventory(
            lsblk_payload(
                disk("nvme0n1", tran="nvme", serial="A"),
                disk("mmcblk0", tran="mmc", serial="B"),
            )
        )
        with self.assertRaises(GenesisError) as ctx:
            select_install_target(devices, source_disk_path=None)
        self.assertEqual("TARGET_AMBIGUOUS", ctx.exception.code)

    def test_source_disk_is_excluded_even_when_not_removable(self):
        devices = parse_lsblk_inventory(
            lsblk_payload(
                disk("nvme0n1", tran="nvme", serial="SOURCE"),
                disk("mmcblk0", tran="mmc", serial="TARGET"),
            )
        )
        target = select_install_target(devices, source_disk_path="/dev/nvme0n1")
        self.assertEqual("/dev/mmcblk0", target.path)


class GenesisManifestTests(unittest.TestCase):
    def _fixture(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        image = root / "filesystem.squashfs"
        image.write_bytes(b"synapse-genesis-image\n" * 64)
        sha = hashlib.sha256(image.read_bytes()).hexdigest()
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "synapse-genesis-manifest/v1",
                    "synapse_version": "0.2.1a1",
                    "architecture": "amd64",
                    "image_type": "squashfs-rootfs",
                    "image_filename": image.name,
                    "image_size": image.stat().st_size,
                    "image_sha256": sha,
                    "build_commit": "deadbeef",
                    "license": EXPECTED_LICENSE,
                    "zenodo_doi": EXPECTED_ZENODO_DOI,
                }
            ),
            encoding="utf-8",
        )
        return td, image, manifest_path, sha

    def test_manifest_verifies_size_hash_arch_and_provenance(self):
        td, image, manifest_path, sha = self._fixture()
        with td:
            manifest = ImageManifest.from_path(manifest_path)
            result = verify_manifest(
                manifest,
                image_path=image,
                expected_arch="amd64",
                target_size=32_000_000_000,
            )
            self.assertTrue(result["verified"])
            self.assertEqual(sha, result["image_sha256"])
            self.assertEqual("hash-verified", result["verification"])

    def test_hash_mismatch_is_rejected(self):
        td, image, manifest_path, _ = self._fixture()
        with td:
            manifest = ImageManifest.from_path(manifest_path)
            original = image.read_bytes()
            image.write_bytes(bytes([original[0] ^ 0x01]) + original[1:])
            with self.assertRaises(GenesisError) as ctx:
                verify_manifest(manifest, image_path=image, expected_arch="amd64", target_size=32_000_000_000)
            self.assertEqual("IMAGE_HASH_MISMATCH", ctx.exception.code)

    def test_arch_mismatch_is_rejected(self):
        td, image, manifest_path, _ = self._fixture()
        with td:
            manifest = ImageManifest.from_path(manifest_path)
            with self.assertRaises(GenesisError) as ctx:
                verify_manifest(manifest, image_path=image, expected_arch="arm64", target_size=32_000_000_000)
            self.assertEqual("ARCH_MISMATCH", ctx.exception.code)

    def test_missing_license_or_doi_is_rejected(self):
        td, image, manifest_path, _ = self._fixture()
        with td:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw["zenodo_doi"] = "wrong"
            manifest_path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = ImageManifest.from_path(manifest_path)
            with self.assertRaises(GenesisError) as ctx:
                verify_manifest(manifest, image_path=image, expected_arch="amd64", target_size=32_000_000_000)
            self.assertEqual("PROVENANCE_MISMATCH", ctx.exception.code)


class GenesisArmAndReceiptTests(unittest.TestCase):
    def _manager(
        self,
        *,
        arm_ttl=120.0,
        installer_mode=False,
        simulation=True,
        hardware=None,
        power=None,
        boot=None,
    ):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        image = root / "filesystem.squashfs"
        image.write_bytes(b"payload" * 512)
        image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "synapse-genesis-manifest/v1",
                    "synapse_version": "0.2.1a1",
                    "architecture": "amd64",
                    "image_type": "squashfs-rootfs",
                    "image_filename": image.name,
                    "image_size": image.stat().st_size,
                    "image_sha256": image_sha,
                    "build_commit": "cafebabe",
                    "license": EXPECTED_LICENSE,
                    "zenodo_doi": EXPECTED_ZENODO_DOI,
                }
            ),
            encoding="utf-8",
        )
        inventory = parse_lsblk_inventory(lsblk_payload(disk("mmcblk0", serial="TARGET")))
        manager_type = InstallerGenesisManager if installer_mode and not simulation else GenesisManager
        manager = manager_type(
            manifest_path=manifest_path,
            image_path=image,
            staging_dir=root / "stage",
            installer_mode=installer_mode,
            simulation=simulation,
            arm_ttl=arm_ttl,
            hardware_probe=lambda: dict(GALLOP if hardware is None else hardware),
            inventory_probe=lambda: inventory,
            source_disk_probe=lambda: None,
            power_probe=lambda: dict({"ac_online": True, "battery_percent": 100.0} if power is None else power),
            boot_mode_probe=lambda: dict({"mode": "uefi", "genesis_kernel_marker": installer_mode} if boot is None else boot),
        )
        return td, manager

    def _wait_terminal(self, manager: GenesisManager) -> None:
        deadline = time.time() + 2
        while manager.status()["phase"] not in {"complete", "failed"} and time.time() < deadline:
            time.sleep(0.01)
        self.assertIn(manager.status()["phase"], {"complete", "failed"})

    def test_real_destructive_preflight_requires_gallop_profile(self):
        unknown = {
            "arch": "amd64",
            "hwid": "OTHER",
            "profile_id": None,
            "certification_state": "unverified",
            "product_name": "Unknown Laptop",
        }
        td, manager = self._manager(installer_mode=True, simulation=False, hardware=unknown)
        with td:
            with self.assertRaises(GenesisError) as ctx:
                manager.preflight()
            self.assertEqual("HARDWARE_UNSUPPORTED", ctx.exception.code)

    def test_real_destructive_preflight_requires_uefi(self):
        td, manager = self._manager(
            installer_mode=True,
            simulation=False,
            boot={"mode": "legacy-or-unknown", "genesis_kernel_marker": True},
        )
        with td:
            with self.assertRaises(GenesisError) as ctx:
                manager.preflight()
            self.assertEqual("INSTALLER_DISABLED", ctx.exception.code)

    def test_real_destructive_preflight_rejects_unknown_power(self):
        td, manager = self._manager(
            installer_mode=True,
            simulation=False,
            power={"ac_online": None, "battery_percent": None},
        )
        with td:
            with self.assertRaises(GenesisError) as ctx:
                manager.preflight()
            self.assertEqual("POWER_INSUFFICIENT", ctx.exception.code)

    def test_arm_is_bound_to_target_device_and_image(self):
        td, manager = self._manager()
        with td:
            preflight = manager.preflight()
            self.assertTrue(preflight["ready"])
            armed = manager.arm()
            self.assertIn("challenge_id", armed)
            self.assertEqual(preflight["device_fingerprint"], armed["device_fingerprint"])
            self.assertEqual(preflight["target"]["fingerprint"], armed["target_disk_id"])
            self.assertEqual(preflight["image"]["image_sha256"], armed["image_sha256"])
            self.assertEqual(
                f"ERASE:{armed['target_disk_id']}:INSTALL:{armed['image_sha256']}",
                armed["acknowledgement"],
            )

    def test_arm_replay_is_rejected_after_start_consumes_it(self):
        td, manager = self._manager()
        with td:
            armed = manager.arm()
            manager.start(armed["challenge_id"], armed["acknowledgement"])
            with self.assertRaises(GenesisError) as ctx:
                manager.start(armed["challenge_id"], armed["acknowledgement"])
            self.assertEqual("ARM_REPLAYED", ctx.exception.code)
            self._wait_terminal(manager)

    def test_expired_arm_is_rejected(self):
        td, manager = self._manager(arm_ttl=0.01)
        with td:
            armed = manager.arm()
            time.sleep(0.03)
            with self.assertRaises(GenesisError) as ctx:
                manager.start(armed["challenge_id"], armed["acknowledgement"])
            self.assertEqual("ARM_EXPIRED", ctx.exception.code)

    def test_wrong_acknowledgement_is_rejected(self):
        td, manager = self._manager()
        with td:
            armed = manager.arm()
            with self.assertRaises(GenesisError) as ctx:
                manager.start(armed["challenge_id"], "ERASE:WRONG:INSTALL:WRONG")
            self.assertEqual("ARM_MISMATCH", ctx.exception.code)

    def test_receipt_contains_provenance_and_phase_history(self):
        td, manager = self._manager()
        with td:
            armed = manager.arm()
            manager.start(armed["challenge_id"], armed["acknowledgement"])
            self._wait_terminal(manager)
            receipt = manager.receipt()
            self.assertIsNotNone(receipt)
            assert receipt is not None
            self.assertEqual(EXPECTED_ZENODO_DOI, receipt["zenodo_doi"])
            self.assertEqual(EXPECTED_LICENSE, receipt["license"])
            self.assertEqual("asus-cx1700cka-gallop", receipt["hardware"]["profile_id"])
            self.assertEqual(armed["challenge_id"], receipt["challenge_id"])
            self.assertGreaterEqual(len(receipt["phases"]), 3)
            self.assertEqual("complete", receipt["final_state"])


if __name__ == "__main__":
    unittest.main()
