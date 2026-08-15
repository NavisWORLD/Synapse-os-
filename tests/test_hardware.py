import unittest

from synapse import hardware


PROFILES = {
    "profiles": [
        {
            "id": "asus-cx1700cka-gallop",
            "arch": "amd64",
            "hwid_contains": ["GALLOP"],
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

    def test_arch_mismatch_refused(self):
        result = hardware.match_profile({"arch": "arm64", "hwid": "GALLOP TEST"}, PROFILES)
        self.assertIsNone(result["profile_id"])
        self.assertEqual(result["certification_state"], "unverified")

    def test_unknown_unverified(self):
        result = hardware.match_profile({"arch": "arm64", "hwid": "OTHER"}, PROFILES)
        self.assertEqual(result["certification_state"], "unverified")


if __name__ == "__main__":
    unittest.main()
