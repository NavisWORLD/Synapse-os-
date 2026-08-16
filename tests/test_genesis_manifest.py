from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.genesis_manifest import build_manifest, verify_manifest_file


class GenesisManifestScriptTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_binds_rootfs_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "filesystem.squashfs"
            image.write_bytes(b"synapse-rootfs" * 513)
            first = build_manifest(image, version="0.2.1a1", arch="amd64", commit="abc123")
            second = build_manifest(image, version="0.2.1a1", arch="amd64", commit="abc123")
            self.assertEqual(first, second)
            self.assertEqual("synapse-genesis-manifest/v1", first["schema"])
            self.assertEqual("squashfs-rootfs", first["image_type"])
            self.assertEqual("filesystem.squashfs", first["image_filename"])
            self.assertEqual(image.stat().st_size, first["image_size"])
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), first["image_sha256"])
            self.assertEqual("amd64", first["architecture"])
            self.assertEqual("abc123", first["build_commit"])
            self.assertEqual("Cory Davis / NavisWORLD Synapse Source License 1.0", first["license"])
            self.assertEqual("10.5281/zenodo.17574447", first["zenodo_doi"])
            self.assertGreaterEqual(first["required_target_bytes"], 8 * 1024**3)
            self.assertEqual({"scheme": "sha256", "detached_signature": None}, first["signature"])

    def test_verify_manifest_file_rejects_changed_rootfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "filesystem.squashfs"
            image.write_bytes(b"payload" * 64)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(build_manifest(image, version="1", arch="amd64", commit="deadbeef")), encoding="utf-8")
            self.assertEqual("hash-verified", verify_manifest_file(manifest, image)["verification"])
            original = image.read_bytes()
            image.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            with self.assertRaises(ValueError):
                verify_manifest_file(manifest, image)

    def test_verify_manifest_file_rejects_wrong_license_or_doi(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "filesystem.squashfs"
            image.write_bytes(b"payload")
            payload = build_manifest(image, version="1", arch="amd64", commit="deadbeef")
            payload["zenodo_doi"] = "wrong"
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_manifest_file(manifest, image)


if __name__ == "__main__":
    unittest.main()
