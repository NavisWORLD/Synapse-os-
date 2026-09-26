"""Offline security and provenance gates for the initial Synapse Evolution Engine."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from synapse import evolution


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synapse-evolve-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / "repo"
        self.repo.mkdir()
        (self.repo / "src/synapse").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (self.repo / "tests").mkdir()
        self.original = "def greet():\n    return 'BEFORE'\n"
        (self.repo / "src/synapse/example.py").write_text(self.original)
        (self.repo / "docs/README.md").write_text("# Existing documentation\n")
        (self.repo / "tests/test_example.py").write_text("# existing test\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Synapse Test", "-c",
                 "user.email=test@example.invalid", "commit", "-qm", "baseline")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        self.out = self.home / "review-area"

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True,
                              text=True, capture_output=True)

    def proposal(self, changes=None, **overrides):
        if changes is None:
            changes = [{
                "path": "src/synapse/example.py",
                "before_sha256": sha(self.original),
                "after_text": "def greet():\n    return 'AFTER'\n",
            }]
        p = {
            "schema": evolution.SCHEMA, "base_commit": self.head,
            "goal": "Propose a bounded, reversible example change.",
            "model_label": "replaceable model (label only)",
            "changes": changes,
        }
        p.update(overrides)
        file = self.home / "proposal.json"
        file.write_text(json.dumps(p), encoding="utf-8")
        return file

    def test_stage_detached_review_only(self):
        result = evolution.stage(self.proposal(), self.repo, self.out)
        checkout = Path(result["workspace"])
        self.assertTrue(checkout.is_dir())
        self.assertTrue((checkout.parent / "PATCH_REVIEW.diff").is_file())
        stored = json.loads((checkout.parent / "RECEIPT.json").read_text())
        self.assertEqual(stored["base_commit"], self.head)
        self.assertEqual(stored["changes"][0]["before_sha256"], sha(self.original))
        self.assertEqual(stored["changes"][0]["after_sha256"],
                         sha("def greet():\n    return 'AFTER'\n"))
        self.assertEqual(stored["execution"], "STATIC_SYNTAX_ONLY")
        self.assertEqual(stored["tests"], "NOT_RUN")
        self.assertEqual(stored["vm_boot"], "NOT_RUN")
        self.assertEqual(stored["promotion"], "OWNER_REVIEW_REQUIRED")
        self.assertFalse(stored["production_modified"])
        self.assertEqual((self.repo / "src/synapse/example.py").read_text(), self.original)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.head)
        self.assertEqual(subprocess.run(["git", "remote"], cwd=checkout,
                         capture_output=True, text=True, check=True).stdout.strip(), "")

    def test_observe_bounded_telemetry_without_secret_fields(self):
        fake = {
            "synapse_version": "test", "hostname": "PRIVATE_HOST",
            "machine": "amd64", "cpu_count": 4, "load_1m": 0.25,
            "memory": {"available_bytes": 4000},
            "cosmos": {"web": {"port": 8081, "reachable": True}},
            "secret": "DO_NOT_PUBLISH",
        }
        with mock.patch("synapse.evolution.core.system_status", return_value=fake):
            first = evolution.observe(self.repo)
            second = evolution.observe(self.repo)
        self.assertEqual(first, second)
        self.assertEqual(first["repo_commit"], self.head)
        self.assertEqual(first["model_input"], "NOT_SENT")
        raw = json.dumps(first)
        self.assertNotIn("PRIVATE_HOST", raw)
        self.assertNotIn("DO_NOT_PUBLISH", raw)
        self.assertNotIn('"port"', raw)
        self.assertTrue(first["cosmos"]["web"])

    def test_untrusted_change_cannot_modify_engine_or_authority(self):
        for path in ("src/synapse/evolution.py", "src/synapse/evolution_model.py",
                     "src/synapse/evolution_review.py", "src/synapse/evolution_bundle.py", "src/synapse/cli.py",
                     "src/synapse/agent.py", ".github/workflows/evil.yml",
                     "rootfs/etc/shadow", "docs/../../outside.md",
                     "docs//README.md", "/tmp/evil.py", "src/synapse/../../../secret.py"):
            with self.subTest(path=path):
                changes = [{
                    "path": path, "before_sha256": sha(self.original),
                    "after_text": "pass\n",
                }]
                with self.assertRaises(ValueError):
                    evolution.stage(self.proposal(changes), self.repo, self.out)
        self.assertFalse(self.out.exists())

    def test_rejects_stale_base_or_modified_source(self):
        with self.assertRaises(ValueError):
            evolution.stage(self.proposal(base_commit="0" * 40), self.repo, self.out)
        self.assertFalse(self.out.exists())
        path = self.proposal()
        (self.repo / "src/synapse/example.py").write_text("locally edited\n")
        with self.assertRaisesRegex(ValueError, "tracked source changes"):
            evolution.stage(path, self.repo, self.out)
        self.assertFalse(self.out.exists())

    def test_rejects_forged_baseline_digest(self):
        changes = [{
            "path": "src/synapse/example.py",
            "before_sha256": "0" * 64, "after_text": "pass\n",
        }]
        with self.assertRaisesRegex(ValueError, "baseline digest mismatch"):
            evolution.stage(self.proposal(changes), self.repo, self.out)

    def test_rejects_invalid_syntax_and_duplicate_paths(self):
        bad = [{
            "path": "src/synapse/example.py",
            "before_sha256": sha(self.original), "after_text": "def broken(:\n",
        }]
        with self.assertRaisesRegex(ValueError, "syntax"):
            evolution.stage(self.proposal(bad), self.repo, self.out)
        good = self.proposal()
        same = json.loads(good.read_text())["changes"][0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evolution.stage(self.proposal([same, same]), self.repo, self.out)

    def test_never_executes_proposed_python(self):
        # This would throw if imported or run; static AST parsing is harmless.
        modified = "raise RuntimeError('PROPOSAL_WAS_EXECUTED')\n"
        changes = [{
            "path": "src/synapse/example.py", "before_sha256": sha(self.original),
            "after_text": modified,
        }]
        receipt = evolution.stage(self.proposal(changes), self.repo, self.out)
        self.assertEqual(Path(receipt["workspace"], "src/synapse/example.py").read_text(),
                         modified)
        self.assertEqual(receipt["tests"], "NOT_RUN")

    def test_rejects_symlink_target(self):
        external = self.home / "external.py"
        external.write_text("pass\n")
        link = self.repo / "src/synapse/link.py"
        link.symlink_to(external)
        self.git("add", ".")
        self.git("-c", "user.name=Synapse Test", "-c",
                 "user.email=test@example.invalid", "commit", "-qm", "test symlink")
        current = self.git("rev-parse", "HEAD").stdout.strip()
        changes = [{
            "path": "src/synapse/link.py",
            "before_sha256": sha("pass\n"), "after_text": "print('unsafe')\n"
        }]
        with self.assertRaisesRegex(ValueError, "symlink"):
            evolution.stage(self.proposal(changes, base_commit=current),
                            self.repo, self.out)
        self.assertEqual(external.read_text(), "pass\n")

    def test_output_inside_repo_refused_without_writes(self):
        target = self.repo / "should-not-exist"
        with self.assertRaisesRegex(ValueError, "outside"):
            evolution.stage(self.proposal(), self.repo, target)
        self.assertFalse(target.exists())

    def test_rejects_extra_proposal_authority_fields(self):
        p = self.proposal(grant="root", command="apt full-upgrade")
        with self.assertRaisesRegex(ValueError, "documented fields"):
            evolution.stage(p, self.repo, self.out)

    def test_cli_wiring(self):
        from synapse.cli import main
        with mock.patch("synapse.cli.evolution_observe", return_value={"ok": True}) as obs:
            self.assertEqual(main(["evolve", "observe", "--repo", str(self.repo)]), 0)
            obs.assert_called_once_with(self.repo)
        with mock.patch("synapse.cli.evolution_stage", return_value={"tests": "NOT_RUN"}) as st:
            self.assertEqual(main(["evolve", "stage", str(self.proposal()),
                                   "--repo", str(self.repo), "--output", str(self.out)]), 0)
            self.assertEqual(st.call_count, 1)


if __name__ == "__main__":
    unittest.main()
