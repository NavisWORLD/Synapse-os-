import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.apple_preflight import evaluate_preflight

IDENTITY = {
    "vendor": "Apple Inc.",
    "product_name": "MacBookPro12,1",
    "architecture": "amd64",
    "efi_present": True,
    "profile_id": "macbookpro-2014-2015-intel",
    "support_state": "physical-target",
}
CAPS = {"gpu": True, "keyboard": True, "pointer": True, "network": True, "audio": True, "applesmc": True, "suspend": True}
POWER = {"ac_online": True, "battery_percent": 80}

class PreflightPolicyTests(unittest.TestCase):
    def disk(self, path, *, rm=False, tran="sata", size=256_000_000_000, model="APPLE SSD"):
        return {"path": path, "type": "disk", "rm": rm, "tran": tran, "size": size, "model": model}

    def test_accepts_one_safe_internal_target(self):
        result = evaluate_preflight(IDENTITY, [self.disk("/dev/sda"), self.disk("/dev/sdb", rm=True, tran="usb")], "/dev/sdb", CAPS, POWER)
        self.assertTrue(result["ok"])
        self.assertEqual(result["target"]["path"], "/dev/sda")
        self.assertEqual(result["fatal"], [])

    def test_rejects_ambiguous_internal_targets(self):
        result = evaluate_preflight(IDENTITY, [self.disk("/dev/sda"), self.disk("/dev/nvme0n1", tran="nvme")], "/dev/sdb", CAPS, POWER)
        self.assertFalse(result["ok"])
        self.assertIn("TARGET_AMBIGUOUS", result["fatal"])

    def test_rejects_source_collision(self):
        result = evaluate_preflight(IDENTITY, [self.disk("/dev/sda")], "/dev/sda", CAPS, POWER)
        self.assertFalse(result["ok"])
        self.assertIn("TARGET_MISSING", result["fatal"])

    def test_rejects_non_amd64(self):
        identity = dict(IDENTITY, architecture="arm64")
        result = evaluate_preflight(identity, [self.disk("/dev/sda")], "/dev/sdb", CAPS, POWER)
        self.assertIn("ARCH_UNSUPPORTED", result["fatal"])

    def test_rejects_missing_efi(self):
        identity = dict(IDENTITY, efi_present=False)
        result = evaluate_preflight(identity, [self.disk("/dev/sda")], "/dev/sdb", CAPS, POWER)
        self.assertIn("EFI_REQUIRED", result["fatal"])

    def test_experimental_apple_profile_is_warning_not_silent_support(self):
        identity = dict(IDENTITY, profile_id=None, support_state="experimental")
        result = evaluate_preflight(identity, [self.disk("/dev/sda")], "/dev/sdb", CAPS, POWER)
        self.assertTrue(result["ok"])
        self.assertIn("HARDWARE_EXPERIMENTAL", result["warnings"])

    def test_optional_devices_become_warnings(self):
        caps = dict(CAPS, network=False, audio=False, suspend=False)
        result = evaluate_preflight(IDENTITY, [self.disk("/dev/sda")], "/dev/sdb", caps, POWER)
        self.assertTrue(result["ok"])
        self.assertIn("NETWORK_NOT_DETECTED", result["warnings"])
        self.assertIn("AUDIO_NOT_DETECTED", result["warnings"])
        self.assertIn("SUSPEND_UNVERIFIED", result["warnings"])

    def test_low_battery_without_ac_is_fatal(self):
        result = evaluate_preflight(IDENTITY, [self.disk("/dev/sda")], "/dev/sdb", CAPS, {"ac_online": False, "battery_percent": 10})
        self.assertIn("POWER_UNSAFE", result["fatal"])

if __name__ == "__main__":
    unittest.main()
