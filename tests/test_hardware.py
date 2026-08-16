import unittest

from synapse import hardware


PROFILES = {
    "profiles": [
        {
            "id": "asus-cx1700cka-gallop",
            "arch": "amd64",
            "hwid_contains": ["GALLOP"],
            "board_contains": ["GALLOP"],
            "product_contains": ["CX1700CKA"],
            "vendor_contains": ["ASUS"],
            "certification_state": "physical-target",
        }
    ]
}


class HardwareTests(unittest.TestCase):
    def test_gallop_matches(self):
        result = hardware.match_profile(
            {"arch": "amd64", "hwid": "GALLOP TEST", "product_name": "CX1700CKA"},
            PROFILES,
        )
        self.assertEqual(result["profile_id"], "asus-cx1700cka-gallop")
        self.assertEqual(result["certification_state"], "physical-target")

    def test_gallop_matches_board_name_when_chromeos_hwid_is_unavailable(self):
        result = hardware.match_profile(
            {
                "arch": "amd64",
                "hwid": None,
                "board_name": "GALLOP",
                "product_name": "unknown",
                "sys_vendor": "Google",
            },
            PROFILES,
        )
        self.assertEqual(result["profile_id"], "asus-cx1700cka-gallop")
        self.assertEqual(result["certification_state"], "physical-target")

    def test_product_fallback_requires_matching_vendor(self):
        result = hardware.match_profile(
            {
                "arch": "amd64",
                "hwid": None,
                "board_name": "unknown",
                "product_name": "ASUS Chromebook CX1700CKA",
                "sys_vendor": "NOT-ASUS-CORP",
            },
            PROFILES,
        )
        self.assertIsNone(result["profile_id"])
        self.assertEqual(result["certification_state"], "unverified")

    def test_product_fallback_accepts_asus_cx1700cka(self):
        result = hardware.match_profile(
            {
                "arch": "amd64",
                "hwid": None,
                "board_name": "unknown",
                "product_name": "Chromebook CX1700CKA",
                "sys_vendor": "ASUSTeK COMPUTER INC.",
            },
            PROFILES,
        )
        self.assertEqual(result["profile_id"], "asus-cx1700cka-gallop")

    def test_arch_mismatch_refused(self):
        result = hardware.match_profile({"arch": "arm64", "hwid": "GALLOP TEST"}, PROFILES)
        self.assertIsNone(result["profile_id"])
        self.assertEqual(result["certification_state"], "unverified")

    def test_unknown_unverified(self):
        result = hardware.match_profile({"arch": "arm64", "hwid": "OTHER"}, PROFILES)
        self.assertEqual(result["certification_state"], "unverified")


if __name__ == "__main__":
    unittest.main()
