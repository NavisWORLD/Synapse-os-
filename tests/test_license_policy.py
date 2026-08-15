from pathlib import Path
import unittest

from scripts import license_audit


ROOT = Path(__file__).resolve().parents[1]


class LicensePolicyTests(unittest.TestCase):
    def test_required_legal_files_exist(self):
        missing = [name for name in license_audit.REQUIRED_FILES if not (ROOT / name).is_file()]
        self.assertEqual([], missing)

    def test_root_license_is_synapse_source_license(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Cory Davis / NavisWORLD Synapse Source License 1.0", text)
        self.assertIn("SOURCE-AVAILABLE LICENSE, NOT AN OPEN-SOURCE LICENSE", text)
        self.assertIn("AI/ML Use", text)
        self.assertIn("NO PATENT LICENSE", text)

    def test_package_metadata_does_not_publish_mit(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        cargo = (ROOT / "sdk/rust/Cargo.toml").read_text(encoding="utf-8")
        self.assertNotIn('license = {text = "MIT"}', pyproject)
        self.assertNotIn('license = "MIT"', cargo)
        self.assertIn("Synapse Source License 1.0", pyproject)
        self.assertIn('license-file = "../../LICENSE"', cargo)

    def test_history_preserves_mit_boundary_without_relicensing_current_version(self):
        history = (ROOT / "LICENSE-HISTORY.md").read_text(encoding="utf-8")
        self.assertIn("3e7642d4b5c060ee0302ba769357e99c20dae98b", history)
        self.assertIn("not revoked", history)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("source-available, not open source", readme)
        self.assertNotIn("Synapse-specific original code is MIT licensed", readme)

    def test_build_stages_legal_package_into_bootable_image(self):
        build = (ROOT / "build/build.sh").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/build-vm-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("usr/share/doc/synapse-os", build)
        for name in (
            "LICENSE",
            "NOTICE",
            "COMMERCIAL-LICENSING.md",
            "LICENSE-HISTORY.md",
            "TRADEMARKS.md",
            "THIRD_PARTY_NOTICES.md",
        ):
            self.assertIn(name, build)
            self.assertIn(f"usr/share/doc/synapse-os/{name}", workflow)
        self.assertIn("Cory Davis / NavisWORLD Synapse Source License 1.0", workflow)

    def test_repository_license_audit_passes(self):
        self.assertEqual([], license_audit.audit())


if __name__ == "__main__":
    unittest.main()
