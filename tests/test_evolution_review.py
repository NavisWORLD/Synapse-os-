"""Fail-closed Stage 3 owner review tests.

With SYNAPSE_REAL_EVIDENCE_DIR set, tests validate the EXACT pinned real
GitHub Actions artifact, not a synthetic or model-labeled fixture.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from synapse import evolution_review as er

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = os.environ.get("SYNAPSE_REAL_EVIDENCE_DIR", "")
CI_RECEIPT = os.environ.get("SYNAPSE_EXACT_CI_JSON", "")


class ReviewDisplayTests(unittest.TestCase):
    def test_invalid_schema_denied(self):
        with self.assertRaises(ValueError):
            er.review_display({"schema": "untrusted"})

    def test_untrusted_imports_remain_informational(self):
        text = er.review_display({
            "schema": er.SCHEMA,
            "model_id": "untrusted displayed label",
            "source_path": "docs/fake.py",
            "model_authored_scope": "claimed",
            "two_vm_checks": {"baseline": ["status"], "candidate": ["status"]},
            "candidate_sha256": "0" * 64,
        })
        self.assertIn("READ ONLY", text)
        self.assertIn("requires independent approval", text)

    def test_native_tab_has_no_execution_or_auto_grants(self):
        ui = (ROOT / "rootfs/usr/local/bin/synapse-control").read_text()
        section = ui[ui.index("    def evolution_tab"):ui.index("    def recovery_tab")]
        self.assertIn("setReadOnly(True)", section)
        self.assertIn("review_display(data)", section)
        self.assertIn("candidate.is_symlink()", section)
        self.assertNotIn("subprocess.", section)
        self.assertNotIn("write_text(", section)


@unittest.skipUnless(EVIDENCE and CI_RECEIPT,
                     "exact historical GitHub artifact is downloaded only in dedicated review CI")
class RealArtifactOwnerReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synapse-review-real-")
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.artifact = self.dir / "historical-evidence"
        shutil.copytree(EVIDENCE, self.artifact)
        self.ci = self.dir / "ci.json"
        self.ci.write_bytes(Path(CI_RECEIPT).read_bytes())

    def test_full_provenance_chain_and_nonexecuting_rollback_preview(self):
        bundle, previous, rollback = er.verify(self.artifact, ROOT, self.ci)
        self.assertEqual(bundle["original_model_run"], er.ORIGINAL_RUN)
        self.assertEqual(bundle["feedback_model_run"], er.FEEDBACK_RUN)
        self.assertEqual(bundle["two_disconnected_vm_run"], er.TWO_VM_RUN)
        self.assertEqual(bundle["successful_candidate_ci_run"], er.FULL_CI_RUN)
        self.assertEqual(bundle["candidate_sha256"], er.CANDIDATE_SOURCE_SHA)
        self.assertEqual(er.digest(previous), er.ORIGINAL_SOURCE_SHA)
        self.assertEqual(er.digest(rollback.encode()), bundle["rollback_preview_sha256"])
        self.assertFalse(bundle["automated_merge"])
        self.assertFalse(bundle["production_modified"])
        folder = self.dir / "review"
        result = er.write_review(self.artifact, ROOT, self.ci, folder)
        self.assertEqual(result, bundle)
        self.assertEqual((folder / "ORIGINAL_DEBUGGER_BASELINE.py.txt").read_bytes(), previous)
        self.assertEqual(er.digest((folder / "ROLLBACK_PREVIEW.diff").read_bytes()),
                         bundle["rollback_preview_sha256"])
        with self.assertRaisesRegex(ValueError, "new or empty"):
            er.write_review(self.artifact, ROOT, self.ci, folder)

    def test_refuses_modified_vm_regression_receipt(self):
        target = self.artifact / "COMPARISON.json"
        record = json.loads(target.read_text())
        record["candidate"]["checks"]["debugger_contract"]["passed"] = False
        target.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "guest functional"):
            er.verify(self.artifact, ROOT, self.ci)

    def test_refuses_substituted_model_output(self):
        (self.artifact / "ACTUAL_MODEL_CORRECTION.txt").write_text(
            "model response quietly replaced"
        )
        with self.assertRaisesRegex(ValueError, "genuine feedback"):
            er.verify(self.artifact, ROOT, self.ci)

    def test_refuses_modified_review_patch(self):
        with (self.artifact / "STAGED_PATCH_REVIEW.diff").open("ab") as f:
            f.write(b"\nmalicious extra diff\n")
        with self.assertRaisesRegex(ValueError, "Stage 1"):
            er.verify(self.artifact, ROOT, self.ci)

    def test_refuses_unverified_ci_head(self):
        record = json.loads(self.ci.read_text())
        record["head_sha"] = "0" * 40
        self.ci.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "full CI"):
            er.verify(self.artifact, ROOT, self.ci)

    def test_refuses_fake_candidate_source(self):
        forged = self.dir / "forged"
        (forged / er.SOURCE.parent).mkdir(parents=True)
        (forged / er.SOURCE).write_text("not the reviewed source")
        with self.assertRaisesRegex(ValueError, "candidate not exact"):
            er.verify(self.artifact, forged, self.ci)

    def test_review_bundle_cannot_be_written_inside_real_repository(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            er.write_review(self.artifact, ROOT, self.ci, ROOT / "never-create-owner-review")


if __name__ == "__main__":
    unittest.main()
