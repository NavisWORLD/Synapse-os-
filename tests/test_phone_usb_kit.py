from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PhoneUsbKitTests(unittest.TestCase):
    def test_phone_usb_kit_has_copy_ready_entry_points(self) -> None:
        kit = ROOT / "PHONE_USB_KIT"
        self.assertTrue((kit / "README.md").exists())
        self.assertTrue((kit / "START_HERE.html").exists())
        self.assertTrue((kit / "RELEASE_FILES.txt").exists())

    def test_phone_usb_kit_lists_every_required_release_asset(self) -> None:
        files = (ROOT / "PHONE_USB_KIT" / "RELEASE_FILES.txt").read_text(encoding="utf-8")
        self.assertIn("SynapseOS-Nebula-amd64.iso.part-*", files)
        self.assertIn("SynapseOS-Nebula-amd64.iso.parts.sha256", files)
        self.assertIn("SynapseOS-Nebula-amd64.iso.sha256", files)
        self.assertIn("reassemble-usb-installer.ps1", files)
        self.assertIn("reassemble-usb-installer.sh", files)

    def test_phone_usb_kit_is_truthful_about_copying_vs_flashing(self) -> None:
        readme = (ROOT / "PHONE_USB_KIT" / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("copying", readme)
        self.assertIn("does not make the usb bootable", readme)
        self.assertIn("flash", readme)
        self.assertIn("iphone", readme)

    def test_release_workflow_publishes_phone_kit_zip(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")
        self.assertIn("SynapseOS-Phone-USB-Kit.zip", workflow)
        self.assertIn("PHONE_USB_KIT", workflow)


if __name__ == "__main__":
    unittest.main()
