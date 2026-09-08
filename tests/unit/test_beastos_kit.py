from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from BEASTOS_WEB_MACHINE.bridge.kit import load_manifest, safe_extract, verify_file


class BeastKitTests(unittest.TestCase):
    def test_repository_manifest_pins_v060_release_asset(self) -> None:
        manifest = load_manifest(Path("BEASTOS_WEB_MACHINE/manifests/beast-v0.6.0.json"))
        self.assertEqual(manifest["tag"], "v0.6.0")
        self.assertEqual(manifest["commit"], "331f03c5d6a4aab0b2e32314293e36c7a94be393")
        self.assertEqual(manifest["asset"], "beast-box-combined-0.6.0.zip")
        self.assertEqual(manifest["size"], 676405)
        self.assertEqual(
            manifest["sha256"],
            "c2a5bf5e3cb972ec3e5f1aa45f06d7e77e9b6de115e049f06e830a1f4c312ad2",
        )
        self.assertTrue(manifest["prerelease"])
        self.assertEqual(manifest["integration_api"]["command"], ["beastbox", "runtime", "exchange"])

    def test_verify_file_checks_size_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "kit.zip"
            path.write_bytes(b"real-kit-bytes")
            manifest = {"size": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()}
            verify_file(path, manifest)
            path.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                verify_file(path, manifest)

    def test_safe_extract_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("../escape", b"nope")
            with self.assertRaises(ValueError):
                safe_extract(archive, Path(td) / "out")

    def test_safe_extract_accepts_regular_release_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "good.zip"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("LICENSE", b"license")
                target.writestr("cosmos_beast_box-0.6.0-py3-none-any.whl", b"wheel")
            out = Path(td) / "out"
            safe_extract(archive, out)
            self.assertEqual((out / "LICENSE").read_bytes(), b"license")
            self.assertEqual((out / "cosmos_beast_box-0.6.0-py3-none-any.whl").read_bytes(), b"wheel")


if __name__ == "__main__":
    unittest.main()
