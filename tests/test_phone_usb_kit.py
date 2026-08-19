from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


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

    def test_phone_kit_packager_builds_a_self_contained_small_zip(self) -> None:
        script = ROOT / "scripts" / "package-phone-usb-kit.sh"
        with tempfile.TemporaryDirectory() as td:
            release = Path(td)
            for name in (
                "SynapseOS-Nebula-amd64.iso.parts.sha256",
                "SynapseOS-Nebula-amd64.iso.sha256",
                "reassemble-usb-installer.ps1",
                "reassemble-usb-installer.sh",
            ):
                (release / name).write_text(f"fixture {name}\n", encoding="utf-8")

            result = subprocess.run(
                ["bash", str(script), str(release)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"packager failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )

            bundle = release / "SynapseOS-Phone-USB-Kit.zip"
            checksum = release / "SynapseOS-Phone-USB-Kit.zip.sha256"
            self.assertTrue(bundle.exists())
            self.assertTrue(checksum.exists())

            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())
            self.assertIn("START_HERE.html", names)
            self.assertIn("README.md", names)
            self.assertIn("RELEASE_FILES.txt", names)
            self.assertIn("USB_INSTALL.md", names)
            self.assertIn("SynapseOS-Nebula-amd64.iso.parts.sha256", names)
            self.assertIn("SynapseOS-Nebula-amd64.iso.sha256", names)
            self.assertIn("reassemble-usb-installer.ps1", names)
            self.assertIn("reassemble-usb-installer.sh", names)


if __name__ == "__main__":
    unittest.main()
