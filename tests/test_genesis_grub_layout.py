from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from synapse.genesis import EXPECTED_LICENSE, EXPECTED_ZENODO_DOI, parse_lsblk_inventory
from synapse import genesis_writer


def _disk():
    return {
        "name": "mmcblk0",
        "kname": "mmcblk0",
        "path": "/dev/mmcblk0",
        "type": "disk",
        "size": 128_000_000_000,
        "rm": False,
        "rota": False,
        "tran": "mmc",
        "model": "TEST",
        "serial": "TARGET",
        "pkname": None,
        "mountpoints": [None],
        "children": [],
    }


class GenesisGrubLayoutTests(unittest.TestCase):
    def test_removable_uefi_grub_boot_directory_and_config_live_on_esp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "filesystem.squashfs"
            image.write_bytes(b"rootfs" * 1024)
            target = parse_lsblk_inventory({"blockdevices": [_disk()]})[0]
            mount_root = root / "mnt"

            # Fake the result of unsquashfs because this unit test is only
            # checking the removable UEFI GRUB layout contract.
            (mount_root / "boot").mkdir(parents=True)
            (mount_root / "boot" / "vmlinuz-test").write_text("kernel", encoding="utf-8")
            (mount_root / "boot" / "initrd.img-test").write_text("initrd", encoding="utf-8")
            (mount_root / "etc").mkdir(parents=True)
            (mount_root / "etc" / "os-release").write_text("ID=synapseos\n", encoding="utf-8")
            (mount_root / "usr/share/doc/synapse-os").mkdir(parents=True)
            (mount_root / "usr/share/doc/synapse-os/LICENSE").write_text(EXPECTED_LICENSE, encoding="utf-8")
            (mount_root / "usr/share/doc/synapse-os/PROVENANCE.md").write_text(
                EXPECTED_ZENODO_DOI, encoding="utf-8"
            )
            (mount_root / "usr/share/synapse").mkdir(parents=True)
            (mount_root / "usr/share/synapse/phone-bootstrap.html").write_text("bootstrap", encoding="utf-8")

            plan = {
                "schema": "synapse-genesis-plan/v1",
                "device_fingerprint": "sha256:device",
                "target": target.public(),
                "image_path": str(image),
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "architecture": "amd64",
                "license": EXPECTED_LICENSE,
                "zenodo_doi": EXPECTED_ZENODO_DOI,
            }
            receipt = {
                "schema": "synapse-genesis-receipt/v1",
                "license": EXPECTED_LICENSE,
                "zenodo_doi": EXPECTED_ZENODO_DOI,
                "final_state": "installing",
                "phases": [],
            }
            calls: list[list[str]] = []

            def fake_runner(argv, **kwargs):
                calls.append(list(argv))
                name = Path(argv[0]).name
                if name == "lsblk":
                    return ""
                if name == "blkid":
                    return "ROOT-UUID" if str(argv[-1]).endswith("p2") else "EFI-UUID"
                return ""

            with mock.patch("synapse.genesis_writer._require_tool", side_effect=lambda name: name):
                result = genesis_writer._partition_and_install(plan, receipt, fake_runner, mount_root)

            self.assertEqual("complete", result["final_state"])
            grub_call = next(call for call in calls if call and call[0] == "grub-install")
            esp_boot = mount_root / "boot" / "efi" / "boot"
            self.assertIn(f"--boot-directory={esp_boot}", grub_call)
            self.assertTrue((esp_boot / "grub" / "grub.cfg").is_file())
            self.assertFalse((mount_root / "boot" / "grub" / "grub.cfg").exists())


if __name__ == "__main__":
    unittest.main()
