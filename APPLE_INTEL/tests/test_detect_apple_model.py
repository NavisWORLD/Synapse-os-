import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.apple_hardware import normalize_probe, load_profiles


class AppleDetectionTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_profiles(ROOT / "hardware" / "apple_intel_profiles.json")

    def test_2015_macbook_pro_is_physical_target(self):
        result = normalize_probe({
            "sys_vendor": "Apple Inc.",
            "product_name": "MacBookPro12,1",
            "board_name": "Mac-E43C1C25D4880AD6",
            "bios_vendor": "Apple Inc.",
            "arch": "x86_64",
            "efi_present": True,
        }, self.registry)
        self.assertEqual(result["architecture"], "amd64")
        self.assertEqual(result["profile_id"], "macbookpro-2014-2015-intel")
        self.assertEqual(result["support_state"], "physical-target")
        self.assertFalse(result["touch_bar"])

    def test_same_model_name_from_non_apple_vendor_is_rejected(self):
        result = normalize_probe({
            "sys_vendor": "Not Apple Corp",
            "product_name": "MacBookPro12,1",
            "arch": "x86_64",
            "efi_present": True,
        }, self.registry)
        self.assertIsNone(result["profile_id"])
        self.assertEqual(result["support_state"], "unknown")

    def test_unknown_intel_apple_is_experimental_not_supported(self):
        result = normalize_probe({
            "sys_vendor": "Apple Inc.",
            "product_name": "MacBookPro99,9",
            "arch": "x86_64",
            "efi_present": True,
        }, self.registry)
        self.assertIsNone(result["profile_id"])
        self.assertEqual(result["support_state"], "experimental")

    def test_arm_apple_is_out_of_scope(self):
        result = normalize_probe({
            "sys_vendor": "Apple Inc.",
            "product_name": "MacBookPro18,3",
            "arch": "arm64",
            "efi_present": True,
        }, self.registry)
        self.assertEqual(result["support_state"], "unsupported")


if __name__ == "__main__":
    unittest.main()
