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
    GenesisManager,
    parse_lsblk_inventory,
)


class GenesisWriterWiringTests(unittest.TestCase):
    def test_installer_mode_invokes_fixed_writer_and_completes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = root / "filesystem.squashfs"
            image.write_bytes(b"synapse" * 1024)
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "synapse-genesis-manifest/v1",
                        "synapse_version": "0.2.1a1",
                        "architecture": "amd64",
                        "image_type": "squashfs-rootfs",
                        "image_filename": "live/filesystem.squashfs",
                        "image_size": image.stat().st_size,
                        "image_sha256": digest,
                        "build_commit": "test",
                        "license": EXPECTED_LICENSE,
                        "zenodo_doi": EXPECTED_ZENODO_DOI,
                        "required_target_bytes": image.stat().st_size,
                    }
                ),
                encoding="utf-8",
            )
            inventory = parse_lsblk_inventory(
                {
                    "blockdevices": [
                        {
                            "name": "mmcblk0",
                            "kname": "mmcblk0",
                            "path": "/dev/mmcblk0",
                            "type": "disk",
                            "size": 128_000_000_000,
                            "rm": False,
                            "rota": False,
                            "tran": "mmc",
                            "model": "TEST EMMC",
                            "serial": "GENESIS-TARGET",
                            "pkname": None,
                            "mountpoints": [None],
                            "children": [],
                        }
                    ]
                }
            )
            calls: list[tuple[Path, Path]] = []

            def fake_writer(plan_path: Path, receipt_path: Path) -> dict:
                calls.append((Path(plan_path), Path(receipt_path)))
                receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
                receipt["final_state"] = "complete"
                receipt["writer"] = "fake-test-writer"
                receipt.setdefault("phases", []).append(
                    {"phase": "complete", "at": time.time(), "message": "fake writer completed"}
                )
                return receipt

            manager = GenesisManager(
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
                inventory_probe=lambda: inventory,
                source_disk_probe=lambda: None,
                power_probe=lambda: {"ac_online": True, "battery_percent": 100.0},
                boot_mode_probe=lambda: {"mode": "uefi", "genesis_kernel_marker": True},
                writer_runner=fake_writer,
            )

            armed = manager.arm()
            manager.start(armed["challenge_id"], armed["acknowledgement"])
            deadline = time.time() + 2.0
            while manager.status()["phase"] not in {"complete", "failed"} and time.time() < deadline:
                time.sleep(0.01)

            self.assertEqual("complete", manager.status()["phase"])
            self.assertEqual(1, len(calls))
            self.assertEqual(root / "stage" / "install-plan.json", calls[0][0])
            self.assertEqual(root / "stage" / "receipt.json", calls[0][1])
            receipt = manager.receipt()
            self.assertIsNotNone(receipt)
            assert receipt is not None
            self.assertEqual("complete", receipt["final_state"])
            self.assertEqual("fake-test-writer", receipt["writer"])


if __name__ == "__main__":
    unittest.main()
