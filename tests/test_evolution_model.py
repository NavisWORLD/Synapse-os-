"""Secure model-neutral task packet and explicit local-only Beast adapter gates."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

from synapse import evolution_model as em


class ModelAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="synapse-model-gate-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.source = self.repo / "src/synapse/sample.py"
        self.source.parent.mkdir(parents=True)
        self.original = "def answer():\n    return 1\n"
        self.updated = "def answer():\n    return 2\n"
        self.source.write_text(self.original)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.email=test@example.invalid",
                 "-c", "user.name=Synapse Test", "commit", "-qm", "baseline")
        self.data_dir = self.root / "beast-state"
        self.data_dir.mkdir()
        self.out = self.root / "proposed"
        self.packet = em.prepare(self.repo, "Make answer equal 2.", "src/synapse/sample.py")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True,
                              text=True, capture_output=True)

    def reply(self, proposal=None):
        if proposal is None:
            proposal = {
                "schema": em.SCHEMA,
                "base_commit": self.packet["base_commit"],
                "goal": self.packet["goal"],
                "model_label": "claimed-smollm",
                "changes": [{
                    "path": self.packet["path"],
                    "before_sha256": self.packet["before_sha256"],
                    "after_text": self.updated,
                }],
            }
        return {"schema": "beastbox-response-v1", "ok": True,
                "result": {"response": json.dumps(proposal)}}

    def local(self, *, runner, approved=True, url="http://127.0.0.1:11434",
              provider="ollama"):
        return em.run_local(
            repo=self.repo, goal=self.packet["goal"],
            path_name=self.packet["path"], executable=Path("/bin/true"),
            data_dir=self.data_dir, provider=provider,
            model="smollm2:135m", url=url, output_parent=self.out,
            code_memory_approved=approved, runner=runner
        )

    def test_packet_excludes_host_data_and_binds_exact_file(self):
        p = self.packet
        self.assertEqual(p["schema"], em.TASK_SCHEMA)
        self.assertEqual(p["before_text"], self.original)
        self.assertEqual(p["before_sha256"],
                         hashlib.sha256(self.original.encode()).hexdigest())
        self.assertEqual(p["authority"],
                         "PROPOSAL_ONLY_NO_TOOLS_NO_EXECUTION_NO_DEPLOYMENT")
        self.assertEqual(set(p["response_contract"]["changes"][0]),
                         {"path", "before_sha256", "after_text"})
        self.assertNotIn("hostname", json.dumps(p))

    def test_malformed_and_remote_urls_denied(self):
        for url in (
            "https://127.0.0.1:443/v1", "http://8.8.8.8:11434",
            "http://remote.example:11434", "http://127.0.0.1:11434/?secret=1",
            "http://user:pass@127.0.0.1:11434", "http://127.0.0.1",
            "file:///tmp/model", "http://localhost:99999",
            "http://127.0.0.1:11434/redirect",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                em.local_url(url)
        self.assertEqual(em.local_url("http://127.0.0.1:11434/"),
                         "http://127.0.0.1:11434")
        self.assertEqual(em.local_url("http://localhost:8080/v1"),
                         "http://localhost:8080/v1")

    def test_never_exchanges_without_explicit_owner_consent(self):
        runner = mock.Mock()
        with self.assertRaisesRegex(ValueError, "approval"):
            self.local(runner=runner, approved=False)
        runner.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_parse_rejects_fences_ambiguous_fields_and_changed_task(self):
        with self.assertRaisesRegex(ValueError, "exactly one JSON"):
            em.parse_reply({"schema": "beastbox-response-v1", "ok": True,
                            "result": {"response": "~~~json\n{}\n~~~"}},
                           self.packet)
        proposal = json.loads(self.reply()["result"]["response"])
        proposal["base_commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "identity"):
            em.parse_reply(self.reply(proposal), self.packet)
        proposal["base_commit"] = self.packet["base_commit"]
        proposal["changes"][0]["path"] = "src/synapse/secret.py"
        with self.assertRaisesRegex(ValueError, "path"):
            em.parse_reply(self.reply(proposal), self.packet)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            em.parse_reply({"schema": "beastbox-response-v1", "ok": True,
                            "result": {"response": "{}", "text": "{}"}},
                           self.packet)

    def test_local_stub_stages_real_diff_but_never_runs_patch(self):
        calls = []
        def fake(argv, **kwargs):
            calls.append((argv, kwargs))
            return types.SimpleNamespace(returncode=0, stdout=json.dumps(self.reply()))
        with mock.patch.dict(os.environ, {"HF_TOKEN": "CLOUD_SECRET_DO_NOT_SEND"}, clear=False):
            receipt = self.local(runner=fake)
        self.assertEqual(len(calls), 1)
        argv, kwargs = calls[0]
        self.assertIn("ollama", argv)
        self.assertNotIn("--allow-remote", argv)
        self.assertFalse(kwargs["shell"])
        self.assertNotIn("HF_TOKEN", kwargs["env"])
        self.assertNotIn("CLOUD_SECRET_DO_NOT_SEND", json.dumps(kwargs))
        self.assertEqual(receipt["tests"], "NOT_RUN")
        self.assertFalse(receipt["production_modified"])
        self.assertTrue(receipt["model_adapter"]["code_sent_to_continuity"])
        self.assertFalse(receipt["model_adapter"]["model_origin_attested"])
        self.assertEqual((Path(receipt["workspace"]) / "src/synapse/sample.py").read_text(),
                         self.updated)
        self.assertEqual(self.source.read_text(), self.original)
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "")

    def test_reference_provider_and_non_json_reply_fail_closed(self):
        never = mock.Mock()
        with self.assertRaisesRegex(ValueError, "local ollama"):
            self.local(runner=never, provider="reference")
        never.assert_not_called()
        def malformed(*a, **kwargs):
            return types.SimpleNamespace(returncode=0, stdout="{malformed")
        with self.assertRaisesRegex(ValueError, "exchange JSON"):
            self.local(runner=malformed)
        self.assertFalse(self.out.exists())

    def test_source_changes_after_inference_cannot_stage(self):
        def changed(*a, **kwargs):
            self.source.write_text("def answer():\n    return 666\n")
            return types.SimpleNamespace(returncode=0, stdout=json.dumps(self.reply()))
        with self.assertRaisesRegex(ValueError, "tracked source changes"):
            self.local(runner=changed)

    def test_rejects_secret_and_policy_code_as_task_input(self):
        for name in ("src/synapse/evolution.py", "rootfs/etc/shadow",
                     "tests/../.github/workflows/main.yml"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                em.prepare(self.repo, "Improve it", name)

    def test_cli_wiring_prepare_and_local(self):
        from synapse.cli import main
        with mock.patch("synapse.cli.evolution_prepare", return_value=self.packet) as prep:
            self.assertEqual(main(["evolve", "prepare", "--repo", str(self.repo),
                                   "--path", self.packet["path"],
                                   "--goal", self.packet["goal"]]), 0)
            prep.assert_called_once()
        with mock.patch("synapse.cli.evolution_run_local", return_value={"tests": "NOT_RUN"}) as run:
            code = main(["evolve", "local", "--repo", str(self.repo),
                         "--path", self.packet["path"], "--goal", self.packet["goal"],
                         "--beast-executable", "/bin/true",
                         "--beast-data-dir", str(self.data_dir),
                         "--provider", "ollama", "--model", "smollm2:135m",
                         "--url", "http://127.0.0.1:11434",
                         "--output", str(self.out), "--approve-code-in-memory"])
            self.assertEqual(code, 0)
            self.assertTrue(run.call_args.kwargs["code_memory_approved"])


if __name__ == "__main__":
    unittest.main()
