import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UsbReleaseTests(unittest.TestCase):
    def test_usb_release_workflow_and_guide_exist(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "release-usb-installer.yml"
        guide = ROOT / "USB_INSTALL.md"

        self.assertTrue(workflow.exists(), "USB installer release workflow is missing")
        self.assertTrue(guide.exists(), "USB installation guide is missing")

    def test_usb_release_workflow_publishes_iso_and_checksum(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("SynapseOS-*-amd64.iso", workflow)
        self.assertIn("*.iso.sha256", workflow)
        self.assertIn("gh release", workflow)
        self.assertIn("build/build.sh", workflow)
        self.assertIn("genesis-installed-vm-smoke.sh", workflow)

    def test_manual_release_defaults_to_repository_version(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertIn("required: false", workflow)
        self.assertIn("cat VERSION", workflow)

    def test_release_gate_reopens_iso_and_checks_genesis_payload(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertIn("filesystem.squashfs", workflow)
        self.assertIn("/synapse-genesis/manifest.json", workflow)
        self.assertIn("usr/share/synapse/GENESIS.html", workflow)
        self.assertIn("usr/local/bin/synapse-genesis-writer", workflow)
        self.assertIn("synapse-genesis-installer-api.service", workflow)
        self.assertIn("scripts/genesis_manifest.py verify", workflow)

    def test_usb_guide_documents_genesis_and_safe_flashing(self) -> None:
        guide = (ROOT / "USB_INSTALL.md").read_text(encoding="utf-8")

        self.assertIn("GENESIS", guide)
        self.assertIn("GALLOP", guide)
        self.assertIn("SHA-256", guide)
        self.assertIn("Rufus", guide)
        self.assertIn("balenaEtcher", guide)
        self.assertIn("dd", guide)
        self.assertIn("all data on the USB", guide)


if __name__ == "__main__":
    unittest.main()
