import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UsbAutoReleaseTests(unittest.TestCase):
    def test_usb_release_runs_on_main_when_version_changes(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertIn("branches:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn("paths:", workflow)
        self.assertIn("- VERSION", workflow)

    def test_usb_release_feature_bumps_alpha_version(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "0.1.0-alpha.2")


if __name__ == "__main__":
    unittest.main()
