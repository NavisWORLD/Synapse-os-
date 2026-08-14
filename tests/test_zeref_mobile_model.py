import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "models" / "zeref-mobile-v1" / "verify_cosmosmodel.py"
MODEL_JSON = ROOT / "models" / "zeref-mobile-v1" / "model.json"
SPEC = importlib.util.spec_from_file_location("verify_cosmosmodel", VERIFY_PATH)
VERIFY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(VERIFY)


class ZerefMobileIntegrationTests(unittest.TestCase):
    def test_manifest_matches_frozen_verifier_identity(self):
        model = json.loads(MODEL_JSON.read_text(encoding="utf-8"))
        self.assertEqual(model["lineage"], "Zeref-Mobile-v1")
        self.assertEqual(model["package"]["sha256"], VERIFY.EXPECTED_PACKAGE_SHA)
        self.assertEqual(model["q8_payload"]["sha256"], VERIFY.EXPECTED_WEIGHTS_SHA)
        self.assertEqual(model["tokenizer_sha256"], VERIFY.EXPECTED_TOKENIZER_SHA)
        self.assertEqual(model["parent_checkpoint_sha256"], VERIFY.EXPECTED_PARENT_SHA)
        self.assertFalse(model["physical_apple_device_verified"])

    def test_unrecognized_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "unknown.cosmosmodel"
            package.write_bytes(b"not-zeref")
            with self.assertRaises(VERIFY.VerificationError):
                VERIFY.verify_package(package)


if __name__ == "__main__":
    unittest.main()
