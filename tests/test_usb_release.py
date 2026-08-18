import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UsbReleaseTests(unittest.TestCase):
    def test_usb_release_workflow_and_guide_exist(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "release-usb-installer.yml"
        guide = ROOT / "USB_INSTALL.md"

        self.assertTrue(workflow.exists(), "USB installer release workflow is missing")
        self.assertTrue(guide.exists(), "USB installation guide is missing")

    def test_readme_links_the_usb_installer_guide(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("USB_INSTALL.md", readme)
        self.assertIn("usb installer", readme.lower())

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
        self.assertIn("VERSION", workflow)
        self.assertIn("TAG=\"v$(tr -d", workflow)

    def test_release_gate_reopens_iso_and_checks_genesis_payload(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertIn("filesystem.squashfs", workflow)
        self.assertIn("/synapse-genesis/manifest.json", workflow)
        self.assertIn("usr/share/synapse/GENESIS.html", workflow)
        self.assertIn("usr/local/bin/synapse-genesis-writer", workflow)
        self.assertIn("synapse-genesis-installer-api.service", workflow)
        self.assertIn("scripts/genesis_manifest.py verify", workflow)

    def test_release_notes_are_generated_without_shell_command_substitution(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertNotIn("cat > release/RELEASE_NOTES.md <<EOF", workflow)
        self.assertIn("Path(\"release/RELEASE_NOTES.md\").write_text", workflow)

    def test_existing_release_cannot_be_repointed_to_another_commit(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")

        self.assertIn("targetCommitish", workflow)
        self.assertIn("refusing to replace release", workflow)

    def test_large_iso_is_split_into_release_safe_parts_with_reassembly_helpers(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-usb-installer.yml").read_text(encoding="utf-8")
        packager = (ROOT / "scripts" / "package-usb-release.sh").read_text(encoding="utf-8")

        self.assertIn("package-usb-release.sh", workflow)
        self.assertIn('PART_SIZE="${SYNAPSE_RELEASE_PART_SIZE:-1900M}"', packager)
        self.assertIn("SynapseOS-Nebula-amd64.iso.part-", workflow)
        self.assertIn("reassemble-usb-installer.sh", workflow)
        self.assertIn("reassemble-usb-installer.ps1", workflow)
        self.assertNotIn("release/SynapseOS-Nebula-amd64.iso \\", workflow)

    def test_unix_reassembler_supports_stock_macos_bash_and_hash_tool(self) -> None:
        helper = (ROOT / "scripts" / "reassemble-usb-installer.sh").read_text(encoding="utf-8")

        self.assertNotIn("mapfile", helper)
        self.assertIn("shasum -a 256", helper)
        self.assertIn("sha256sum", helper)

    def test_release_packager_splits_and_reassembles_a_fixture(self) -> None:
        packager = ROOT / "scripts" / "package-usb-release.sh"
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            source = temp / "fixture.iso"
            release = temp / "release"
            source.write_bytes((b"synapse-release-test\x00" * 400) + b"tail")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()

            env = dict(os.environ)
            env["SYNAPSE_RELEASE_PART_SIZE"] = "1K"
            packaged = subprocess.run(
                ["bash", str(packager), str(source), str(release)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                packaged.returncode,
                0,
                f"packager failed\nstdout:\n{packaged.stdout}\nstderr:\n{packaged.stderr}",
            )

            parts = sorted(release.glob("SynapseOS-Nebula-amd64.iso.part-*"))
            self.assertGreater(len(parts), 1)
            self.assertTrue((release / "reassemble-usb-installer.sh").exists())
            self.assertTrue((release / "reassemble-usb-installer.ps1").exists())

            reassembled = subprocess.run(
                ["bash", str(release / "reassemble-usb-installer.sh")],
                cwd=release,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                reassembled.returncode,
                0,
                f"reassembly failed\nstdout:\n{reassembled.stdout}\nstderr:\n{reassembled.stderr}",
            )
            rebuilt = release / "SynapseOS-Nebula-amd64.iso"
            self.assertEqual(hashlib.sha256(rebuilt.read_bytes()).hexdigest(), expected)

    def test_usb_guide_documents_genesis_and_safe_flashing(self) -> None:
        guide = (ROOT / "USB_INSTALL.md").read_text(encoding="utf-8")

        self.assertIn("GENESIS", guide)
        self.assertIn("GALLOP", guide)
        self.assertIn("SHA-256", guide)
        self.assertIn("Rufus", guide)
        self.assertIn("balenaEtcher", guide)
        self.assertIn("dd", guide)
        self.assertIn("all data on the USB", guide)

    def test_usb_guide_uses_platform_correct_dd_examples(self) -> None:
        guide = (ROOT / "USB_INSTALL.md").read_text(encoding="utf-8")

        self.assertIn("/dev/sdX bs=4M status=progress", guide)
        self.assertIn("/dev/rdiskN bs=4m", guide)

    def test_usb_guide_explains_release_part_reassembly(self) -> None:
        guide = (ROOT / "USB_INSTALL.md").read_text(encoding="utf-8")

        self.assertIn("reassemble-usb-installer.sh", guide)
        self.assertIn("reassemble-usb-installer.ps1", guide)
        self.assertIn("iso.part-", guide)


if __name__ == "__main__":
    unittest.main()
