from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import time
import unittest

from synapse.usb_flash import (
    UsbDevice,
    UsbFlashError,
    UsbFlashManager,
    parse_usb_inventory,
    select_usb_target,
)


def lsblk_payload(*devices: dict) -> dict:
    return {"blockdevices": list(devices)}


def disk(
    name: str,
    *,
    size: int = 64 * 1024 * 1024,
    rm: bool = True,
    tran: str | None = "usb",
    serial: str | None = "USB-SERIAL",
    model: str = "TEST USB",
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
        "model": model,
        "serial": serial,
        "pkname": None,
        "mountpoints": mountpoints or [None],
        "children": [],
    }


class UsbInventoryTests(unittest.TestCase):
    def test_unique_removable_usb_disk_is_selected(self) -> None:
        devices = parse_usb_inventory(lsblk_payload(disk("sdb")))
        target = select_usb_target(devices, image_size=8 * 1024 * 1024, source_disk_path=None)
        self.assertEqual("/dev/sdb", target.path)
        self.assertTrue(target.removable)
        self.assertEqual("usb", target.transport)
        self.assertTrue(target.fingerprint.startswith("sha256:"))

    def test_internal_disk_is_rejected(self) -> None:
        devices = parse_usb_inventory(lsblk_payload(disk("nvme0n1", rm=False, tran="nvme")))
        with self.assertRaises(UsbFlashError) as ctx:
            select_usb_target(devices, image_size=1024, source_disk_path=None)
        self.assertEqual("NO_ELIGIBLE_USB", ctx.exception.code)

    def test_non_usb_removable_disk_is_rejected(self) -> None:
        devices = parse_usb_inventory(lsblk_payload(disk("mmcblk1", rm=True, tran="mmc")))
        with self.assertRaises(UsbFlashError) as ctx:
            select_usb_target(devices, image_size=1024, source_disk_path=None)
        self.assertEqual("NO_ELIGIBLE_USB", ctx.exception.code)

    def test_ambiguous_usb_targets_fail_closed(self) -> None:
        devices = parse_usb_inventory(
            lsblk_payload(
                disk("sdb", serial="A"),
                disk("sdc", serial="B"),
            )
        )
        with self.assertRaises(UsbFlashError) as ctx:
            select_usb_target(devices, image_size=1024, source_disk_path=None)
        self.assertEqual("TARGET_AMBIGUOUS", ctx.exception.code)

    def test_source_disk_is_rejected(self) -> None:
        devices = parse_usb_inventory(lsblk_payload(disk("sdb")))
        with self.assertRaises(UsbFlashError) as ctx:
            select_usb_target(devices, image_size=1024, source_disk_path="/dev/sdb")
        self.assertEqual("NO_ELIGIBLE_USB", ctx.exception.code)

    def test_undersized_usb_is_rejected(self) -> None:
        devices = parse_usb_inventory(lsblk_payload(disk("sdb", size=4096)))
        with self.assertRaises(UsbFlashError) as ctx:
            select_usb_target(devices, image_size=8192, source_disk_path=None)
        self.assertEqual("NO_ELIGIBLE_USB", ctx.exception.code)

    def test_fingerprint_is_deterministic_and_identity_sensitive(self) -> None:
        first = parse_usb_inventory(lsblk_payload(disk("sdb", serial="A")))[0]
        same = parse_usb_inventory(lsblk_payload(disk("sdb", serial="A")))[0]
        changed = parse_usb_inventory(lsblk_payload(disk("sdb", serial="B")))[0]
        self.assertEqual(first.fingerprint, same.fingerprint)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)


class UsbFlashManagerTests(unittest.TestCase):
    def _fixture(self, *, arm_ttl: float = 120.0, corrupt_readback: bool = False):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        image = root / "SynapseOS-Nebula-amd64.iso"
        image.write_bytes((b"SYNAPSE-USB-TEST\n" * 4096) + bytes(range(256)))
        expected = hashlib.sha256(image.read_bytes()).hexdigest()
        target_file = root / "usb-target.img"
        target_file.write_bytes(b"\0" * (image.stat().st_size + 4096))
        device = UsbDevice(
            name="sdb",
            path=str(target_file),
            dev_type="disk",
            size=target_file.stat().st_size,
            removable=True,
            transport="usb",
            model="DISPOSABLE TEST USB",
            serial="TEST-USB-001",
            parent=None,
            mountpoints=(),
        )

        class TestManager(UsbFlashManager):
            def _verify_readback(self, target: UsbDevice, expected_sha256: str, byte_count: int) -> str:
                digest = super()._verify_readback(target, expected_sha256, byte_count)
                if corrupt_readback:
                    raise UsbFlashError("VERIFY_MISMATCH", "simulated verification mismatch")
                return digest

        manager = TestManager(
            image_path=image,
            expected_sha256=expected,
            simulation=True,
            arm_ttl=arm_ttl,
            inventory_probe=lambda: [device],
            source_disk_probe=lambda: None,
        )
        return td, image, target_file, expected, manager

    def _wait_terminal(self, manager: UsbFlashManager) -> None:
        deadline = time.time() + 3
        while manager.status()["phase"] not in {"complete", "failed"} and time.time() < deadline:
            time.sleep(0.01)
        self.assertIn(manager.status()["phase"], {"complete", "failed"})

    def test_image_hash_mismatch_fails_preflight(self) -> None:
        td, image, _, expected, manager = self._fixture()
        with td:
            image.write_bytes(image.read_bytes() + b"tampered")
            with self.assertRaises(UsbFlashError) as ctx:
                manager.preflight()
            self.assertEqual("IMAGE_HASH_MISMATCH", ctx.exception.code)

    def test_arm_is_bound_to_target_and_image(self) -> None:
        td, _, _, expected, manager = self._fixture()
        with td:
            preflight = manager.preflight()
            self.assertTrue(preflight["ready"])
            armed = manager.arm()
            self.assertEqual(preflight["target"]["fingerprint"], armed["target_fingerprint"])
            self.assertEqual(expected, armed["image_sha256"])
            self.assertEqual(
                f"FLASH:{armed['target_fingerprint']}:IMAGE:{expected}:SIZE:{preflight['image']['size']}",
                armed["acknowledgement"],
            )

    def test_arm_expires(self) -> None:
        td, _, _, _, manager = self._fixture(arm_ttl=0.01)
        with td:
            arm = manager.arm()
            time.sleep(0.03)
            with self.assertRaises(UsbFlashError) as ctx:
                manager.start(arm["challenge_id"], arm["acknowledgement"])
            self.assertEqual("ARM_EXPIRED", ctx.exception.code)

    def test_arm_replay_is_rejected(self) -> None:
        td, _, _, _, manager = self._fixture()
        with td:
            arm = manager.arm()
            manager.start(arm["challenge_id"], arm["acknowledgement"])
            with self.assertRaises(UsbFlashError) as ctx:
                manager.start(arm["challenge_id"], arm["acknowledgement"])
            self.assertEqual("ARM_REPLAYED", ctx.exception.code)
            self._wait_terminal(manager)

    def test_target_change_after_arm_is_rejected(self) -> None:
        td, _, target_file, _, manager = self._fixture()
        with td:
            arm = manager.arm()
            original = manager._inventory_probe()
            changed = UsbDevice(
                name=original[0].name,
                path=original[0].path,
                dev_type=original[0].dev_type,
                size=original[0].size,
                removable=True,
                transport="usb",
                model=original[0].model,
                serial="CHANGED-SERIAL",
                parent=None,
                mountpoints=(),
            )
            manager._inventory_probe = lambda: [changed]
            with self.assertRaises(UsbFlashError) as ctx:
                manager.start(arm["challenge_id"], arm["acknowledgement"])
            self.assertEqual("TARGET_CHANGED", ctx.exception.code)
            self.assertTrue(target_file.exists())

    def test_success_requires_full_readback_hash_match(self) -> None:
        td, image, target_file, expected, manager = self._fixture()
        with td:
            arm = manager.arm()
            manager.start(arm["challenge_id"], arm["acknowledgement"])
            self._wait_terminal(manager)
            state = manager.status()
            self.assertEqual("complete", state["phase"])
            self.assertEqual(100, state["progress"])
            self.assertEqual(expected, hashlib.sha256(target_file.read_bytes()[: image.stat().st_size]).hexdigest())
            receipt = manager.receipt()
            self.assertIsNotNone(receipt)
            assert receipt is not None
            self.assertEqual(expected, receipt["readback_sha256"])
            self.assertTrue(receipt["verified"])

    def test_verification_mismatch_never_reports_complete(self) -> None:
        td, _, _, _, manager = self._fixture(corrupt_readback=True)
        with td:
            arm = manager.arm()
            manager.start(arm["challenge_id"], arm["acknowledgement"])
            self._wait_terminal(manager)
            state = manager.status()
            self.assertEqual("failed", state["phase"])
            self.assertIn("VERIFY_MISMATCH", state["error"])
            self.assertIsNone(manager.receipt())


if __name__ == "__main__":
    unittest.main()
