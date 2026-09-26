"""Stage 3.5: exact historical ZIP/member hashes and native Review Bay import."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from synapse import evolution_bundle as gate

ROOT = Path(__file__).resolve().parents[1]
EXACT_ZIP = os.environ.get("SYNAPSE_PINNED_REVIEW_ZIP", "")


class PinnedReviewStaticTests(unittest.TestCase):
    def test_pin_anchors_exact_historical_source_and_full_evidence(self):
        self.assertEqual(len(gate.PINNED_FILES), 9)
        self.assertEqual(gate.ARTIFACT_RUN, 36189003354)
        self.assertEqual(
            gate.PINNED_FILES["REVIEW_BUNDLE.json"],
            "4bd9c026bce6b89fcec98a543fd2c23c791249b83e9d426747abdb6ca801120e",
        )
        self.assertEqual(
            gate.PINNED_FILES["ACTUAL_MODEL_CORRECTION.txt"],
            "8723342b9531a7ae1e13d1ade26b8bdaec17aa5bb10f3776235fb554fa477fa1",
        )

    def test_rejects_wrong_source_before_accepting_any_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            source = p / "debugger.py"
            source.write_text("print('not a candidate')\n")
            archive = p / "fake.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("REVIEW_BUNDLE.json", "{}")
            with self.assertRaisesRegex(ValueError, "installed source differs"):
                gate.verify_pinned_archive(archive, source)

    def test_native_ui_explicitly_separates_unverified_and_pinned_import(self):
        ui = (ROOT / "rootfs/usr/local/bin/synapse-control").read_text()
        section = ui[ui.index("    def evolution_tab"):ui.index("    def recovery_tab")]
        self.assertIn("verify_pinned_archive(", section)
        self.assertIn("PINNED EVIDENCE VERIFIED", section)
        self.assertIn("NOT a GitHub digital signature", section)
        self.assertIn("OWNER APPROVAL STILL REQUIRED", section)
        self.assertIn("does NOT authenticate imported JSON", section)
        self.assertNotIn("subprocess.", section)
        self.assertNotIn("write_text(", section)


@unittest.skipUnless(EXACT_ZIP, "the exact real historical archive is supplied only by evidence CI")
class RealPinnedReviewArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_zip = Path(EXACT_ZIP)
        cls.original = zipfile.ZipFile(cls.original_zip)
        cls.members = {name: cls.original.read(name) for name in cls.original.namelist()}
        cls.source = ROOT / gate.SOURCE

    @classmethod
    def tearDownClass(cls):
        cls.original.close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synapse-pinned-review-")
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)

    def make_archive(self, members, *, force_symlink=None):
        target = self.area / "trial.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, raw in members:
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (
                    (stat.S_IFLNK if force_symlink == name else stat.S_IFREG) | 0o644
                ) << 16
                z.writestr(info, raw)
        return target

    def test_authentic_repacked_content_and_local_candidate_match(self):
        archive = self.make_archive(list(reversed(list(self.members.items()))))
        result = gate.verify_pinned_archive(archive, self.source)
        self.assertEqual(
            result["status"], "PINNED_HISTORICAL_ARTIFACT_AND_LOCAL_SOURCE_MATCH"
        )
        self.assertEqual(result["checked_members"], 9)
        self.assertTrue(result["owner_approval_required"])
        self.assertFalse(result["production_modified"])
        self.assertFalse(result["cryptographic_github_signature_established"])

    def test_real_git_artifact_bytes_pass(self):
        assert gate.verify_pinned_archive(self.original_zip, self.source)["historical_artifact_run"] == 36189003354

    def test_rejects_single_byte_forgery(self):
        forged = dict(self.members)
        forged["REVIEW_BUNDLE.json"] += b" "
        with self.assertRaisesRegex(ValueError, "independently pinned"):
            gate.verify_pinned_archive(self.make_archive(list(forged.items())), self.source)

    def test_rejects_extra_duplicate_or_missing_member(self):
        extra = list(self.members.items()) + [("additional.json", b"{}")]
        missing = list(self.members.items())[:-1]
        duplicate = list(self.members.items()) + [("REVIEW_BUNDLE.json", b"{}")]
        for fixture in (extra, missing, duplicate):
            with self.subTest(length=len(fixture)):
                with self.assertRaisesRegex(ValueError, "duplicate or extra"):
                    gate.verify_pinned_archive(self.make_archive(fixture), self.source)

    def test_rejects_symlink_zip_member(self):
        raw = list(self.members.items())
        with self.assertRaisesRegex(ValueError, "unsafe archive"):
            gate.verify_pinned_archive(
                self.make_archive(raw, force_symlink="COMPARISON.json"), self.source
            )

    def test_rejects_locally_modified_candidate(self):
        candidate = self.area / "debugger.py"
        candidate.write_bytes(self.source.read_bytes() + b"\n# changed after review\n")
        with self.assertRaisesRegex(ValueError, "installed source differs"):
            gate.verify_pinned_archive(self.original_zip, candidate)


if __name__ == "__main__":
    unittest.main()
