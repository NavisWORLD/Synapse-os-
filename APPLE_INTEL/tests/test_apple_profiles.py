import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class AppleProfileRegistryTests(unittest.TestCase):
    def test_registry_has_required_fields_and_no_touchbar(self):
        data = json.loads((ROOT / "hardware" / "apple_intel_profiles.json").read_text())
        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["profiles"])
        profile = data["profiles"][0]
        for key in ("id", "model_identifiers", "arch", "support_state", "touch_bar", "notes"):
            self.assertIn(key, profile)
        self.assertEqual(profile["arch"], "amd64")
        self.assertFalse(profile["touch_bar"])
        for model in ("MacBookPro11,1", "MacBookPro11,2", "MacBookPro11,3", "MacBookPro11,4", "MacBookPro11,5", "MacBookPro12,1"):
            self.assertIn(model, profile["model_identifiers"])

if __name__ == "__main__":
    unittest.main()
