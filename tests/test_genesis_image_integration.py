from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from synapse.genesis import EXPECTED_LICENSE, EXPECTED_ZENODO_DOI, parse_lsblk_inventory
from synapse.genesis_runtime import InstallerGenesisManager


ROOT = Path(__file__).resolve().parents[1]


def _disk():
    return parse_lsblk_inventory({
        "blockdevices": [{
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
        }]
    })


class GenesisLiveImageIntegrationTests(unittest.TestCase):
    def test_dedicated_system_service_is_kernel_gated_and_fixed_path(self):
        path = ROOT / "rootfs/usr/lib/systemd/system/synapse-genesis-installer-api.service"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("ConditionKernelCommandLine=synapse.genesis=1", text)
        self.assertIn("ConditionPathExists=/run/live/medium/synapse-genesis/manifest.json", text)
        self.assertIn("python3 -m synapse.genesis_server", text)
        self.assertIn("--genesis-installer-mode", text)
        self.assertIn("--genesis-manifest /run/live/medium/synapse-genesis/manifest.json", text)
        self.assertIn("--genesis-image /run/live/medium/live/filesystem.squashfs", text)
        self.assertIn("--genesis-staging-dir /run/synapse-genesis", text)
        self.assertIn("--token-file /run/synapse-genesis/token", text)
        self.assertNotIn("--genesis-simulation", text)
        self.assertNotIn("--allow-install", text)

    def test_normal_user_service_is_disabled_in_genesis_kernel_mode(self):
        text = (ROOT / "rootfs/usr/lib/systemd/user/synapse-phone-bootstrap.service").read_text(encoding="utf-8")
        self.assertIn("ConditionKernelCommandLine=!synapse.genesis=1", text)
        self.assertNotIn("--genesis-installer-mode", text)

    def test_writer_wrapper_exists_and_hook_enables_root_service(self):
        wrapper = ROOT / "rootfs/usr/local/bin/synapse-genesis-writer"
        self.assertTrue(wrapper.is_file())
        wrapper_text = wrapper.read_text(encoding="utf-8")
        self.assertIn("python3 -m synapse.genesis_writer", wrapper_text)
        hook = (ROOT / "build/hooks/020-phone-bootstrap.hook.chroot").read_text(encoding="utf-8")
        self.assertIn("chmod 0755 /usr/local/bin/synapse-genesis-writer", hook)
        self.assertIn("systemctl enable synapse-genesis-installer-api.service", hook)

    def test_amd64_build_includes_required_writer_tools(self):
        build = (ROOT / "build/build.sh").read_text(encoding="utf-8")
        for package in (
            "parted",
            "dosfstools",
            "e2fsprogs",
            "grub-efi-amd64-bin",
            "grub2-common",
            "squashfs-tools",
            "util-linux",
        ):
            self.assertIn(package, build)

    def test_non_simulation_manager_delegates_to_fixed_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "filesystem.squashfs"
            image.write_bytes(b"payload" * 1024)
            image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema": "synapse-genesis-manifest/v1",
                "synapse_version": "0.2.1a1",
                "architecture": "amd64",
                "image_type": "squashfs-rootfs",
                "image_filename": image.name,
                "image_size": image.stat().st_size,
                "image_sha256": image_sha,
                "build_commit": "deadbeef",
                "license": EXPECTED_LICENSE,
                "zenodo_doi": EXPECTED_ZENODO_DOI,
            }), encoding="utf-8")
            manager = InstallerGenesisManager(
                manifest_path=manifest,
                image_path=image,
                staging_dir=root / "stage",
                installer_mode=True,
                simulation=False,
                hardware_probe=lambda: {
                    "arch": "amd64",
                    "hwid": "GALLOP TEST",
                    "profile_id": "asus-cx1700cka-gallop",
                    "certification_state": "physical-target",
                },
                inventory_probe=_disk,
                source_disk_probe=lambda: "/dev/sda",
                power_probe=lambda: {"ac_online": True, "battery_percent": 100.0},
                boot_mode_probe=lambda: {"mode": "uefi", "genesis_kernel_marker": True},
            )
            armed = manager.arm()
            writer_result = {
                "schema": "synapse-genesis-receipt/v1",
                "final_state": "complete",
                "phases": [{"phase": "complete", "at": time.time(), "message": "writer complete"}],
                "zenodo_doi": EXPECTED_ZENODO_DOI,
                "license": EXPECTED_LICENSE,
            }
            with mock.patch("synapse.genesis_runtime.run_install", return_value=writer_result) as writer:
                manager.start(armed["challenge_id"], armed["acknowledgement"])
                deadline = time.time() + 2
                while manager.status()["phase"] not in {"complete", "failed"} and time.time() < deadline:
                    time.sleep(0.01)
            self.assertEqual("complete", manager.status()["phase"])
            self.assertEqual("complete", manager.receipt()["final_state"])
            writer.assert_called_once()
            args, kwargs = writer.call_args
            self.assertTrue(str(args[0]).endswith("install-plan.json"))
            self.assertTrue(str(args[1]).endswith("receipt.json"))
            self.assertTrue(kwargs["execute"])


if __name__ == "__main__":
    unittest.main()
