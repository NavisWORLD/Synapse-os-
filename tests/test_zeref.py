from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from synapse.cli import build_parser
from synapse.zeref.receipt import load_receipt, validate_receipt
from synapse.zeref.runtime import (
    ResidentConfig,
    build_full_zeref_argv,
    derive_readiness,
    sanitized_subject_env,
)

ROOT = Path(__file__).resolve().parents[1]


class ZerefReceiptTests(unittest.TestCase):
    def base_receipt(self):
        return {
            "schema": "synapse.zeref.ibm-receipt.v1",
            "authenticated": True,
            "backend": "ibm_marrakesh",
            "job_id": "da1l0maein7c73bdi2d0",
            "job_status": "DONE",
            "source": "ibm-runtime",
            "generated_at": 1000,
            "expires_at": 2000,
            "entropy12": [0.1] * 12,
            "entropy_source_sha256": "a" * 64,
            "counts_sha256": "b" * 64,
            "secret_exposed_to_subject": False,
        }

    def test_receipt_reports_fresh_and_stale_without_losing_validation(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "latest.json"
            path.write_text(json.dumps(self.base_receipt()), encoding="utf-8")
            fresh = load_receipt(path, now=1500)
            stale = load_receipt(path, now=2500)
        self.assertTrue(fresh["fresh"])
        self.assertFalse(stale["fresh"])
        self.assertEqual(stale["job_id"], "da1l0maein7c73bdi2d0")

    def test_receipt_rejects_secret_bearing_fields(self):
        value = self.base_receipt()
        value["api_token"] = "never"
        with self.assertRaisesRegex(ValueError, "secret-like"):
            validate_receipt(value, now=1500)

    def test_receipt_rejects_non_hardware_backend_and_exposed_secret(self):
        value = self.base_receipt()
        value["backend"] = "aer_simulator"
        with self.assertRaises(ValueError):
            validate_receipt(value, now=1500)
        value = self.base_receipt()
        value["secret_exposed_to_subject"] = True
        with self.assertRaises(ValueError):
            validate_receipt(value, now=1500)


class ZerefRuntimeTests(unittest.TestCase):
    def test_subject_environment_strips_ibm_authority(self):
        env = sanitized_subject_env({
            "PATH": "/usr/bin",
            "IBM_QUANTUM_TOKEN": "must-not-travel",
            "HOME": "/home/cory",
        })
        self.assertNotIn("IBM_QUANTUM_TOKEN", env)
        self.assertEqual(env["PATH"], "/usr/bin")

    def test_full_zeref_command_is_fixed_purpose_and_contains_no_secret(self):
        cfg = ResidentConfig(
            full_zeref="/usr/local/bin/full-zeref",
            beastbox_config="/var/lib/synapse/zeref/beastbox.json",
            native_server="/var/lib/synapse/zeref/qc67/cosmos_serve.py",
            checkpoint="/var/lib/synapse/zeref/qc67/spark_cst.pt",
            ibm_receipt="/var/lib/synapse/zeref/ibm/latest.json",
            socket_path="/run/user/1000/synapse/zeref.sock",
        )
        argv = build_full_zeref_argv(cfg, command="serve")
        self.assertEqual(argv[0], "/usr/local/bin/full-zeref")
        self.assertEqual(argv[1], "serve")
        self.assertIn("--socket", argv)
        self.assertNotIn("IBM_QUANTUM_TOKEN", " ".join(argv))
        self.assertNotIn("--allow-run", argv)

    def test_readiness_is_fail_soft_and_explicit(self):
        self.assertEqual(derive_readiness(model_available=False, receipt_state="fresh", socket_ready=False), "MODEL_UNAVAILABLE")
        self.assertEqual(derive_readiness(model_available=True, receipt_state="missing", socket_ready=False), "IBM_UNAVAILABLE")
        self.assertEqual(derive_readiness(model_available=True, receipt_state="stale", socket_ready=True), "IBM_STALE")
        self.assertEqual(derive_readiness(model_available=True, receipt_state="fresh", socket_ready=False), "STOPPED")
        self.assertEqual(derive_readiness(model_available=True, receipt_state="fresh", socket_ready=True), "READY")


class ZerefBuildContractTests(unittest.TestCase):
    def test_build_accepts_preverified_qc67_bundle_without_weakening_hashes(self):
        build = (ROOT / "build" / "build.sh").read_text(encoding="utf-8")
        self.assertIn("SYNAPSE_QC67_LOCAL_DIR", build)
        self.assertIn("preverified QC67 bundle is missing", build)
        self.assertIn("955805d45f7b407ef5cc9b6efe178d9a5f63df5b32eaf539d9aedcbb2967f1dc", build)
        self.assertIn("02a509f9c2a20f63c38dca186c082bfdc2603aa8b6f1f903ec19a0e709218d87", build)
        self.assertIn("aa0cb13c1e67d459db280a53b6407dfc2b5b5f3fd6f640bc43686b70d799acd1", build)
        self.assertIn("hf_credential_embedded\": false", build)


class ZerefCliTests(unittest.TestCase):
    def test_parser_exposes_full_zeref_surface(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["zeref", "status"]).zeref_command, "status")
        self.assertEqual(parser.parse_args(["zeref", "doctor"]).zeref_command, "doctor")
        self.assertEqual(parser.parse_args(["zeref", "start"]).zeref_command, "start")
        self.assertEqual(parser.parse_args(["zeref", "stop"]).zeref_command, "stop")
        chat = parser.parse_args(["zeref", "chat", "hello"])
        self.assertEqual(chat.zeref_command, "chat")
        self.assertEqual(chat.message, "hello")
        ibm = parser.parse_args(["zeref", "ibm", "refresh"])
        self.assertEqual(ibm.zeref_command, "ibm")
        self.assertEqual(ibm.ibm_command, "refresh")


if __name__ == "__main__":
    unittest.main()
