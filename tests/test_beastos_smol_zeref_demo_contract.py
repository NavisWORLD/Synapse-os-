from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BeastOSSmolZerefDemoContractTests(unittest.TestCase):
    def test_lineage_provider_is_exact_frozen_smol_then_zeref(self) -> None:
        provider = ROOT / "BEASTOS_WEB_MACHINE/scripts/smol_zeref_lineage_provider.py"
        self.assertTrue(provider.is_file())
        text = provider.read_text(encoding="utf-8")
        self.assertIn("HuggingFaceTB/SmolLM2-135M", text)
        self.assertIn("4e53f736cbb20a9a0f56b4c4bf378d9f306ff915", text)
        self.assertIn("109a74ae153ab55706aa31dcb1ae10f39fb281deea6728a3546b55d6dc0fcbb3", text)
        self.assertIn("454f3017618a81fb9a13393b215d448f365534baf5b607e19d1438955921e425", text)
        self.assertIn("955805d45f7b407ef5cc9b6efe178d9a5f63df5b32eaf539d9aedcbb2967f1dc", text)
        self.assertIn("edf6501633ff26948a73815690e2f184c3e4025414c3ac2d64fbfec203307f7a", text)
        self.assertIn("/demo/brain", text)
        self.assertIn("/api/generate", text)
        self.assertNotIn("qwen", text.lower())

    def test_browser_recorder_performs_live_swap_and_authority_reset(self) -> None:
        recorder = ROOT / "BEASTOS_WEB_MACHINE/scripts/live-demo-smol-zeref.mjs"
        self.assertTrue(recorder.is_file())
        text = recorder.read_text(encoding="utf-8")
        self.assertIn("SmolLM2-135M", text)
        self.assertIn("Zeref", text)
        self.assertIn("filesystem.write", text)
        self.assertIn("grantsBeforeSwap", text)
        self.assertIn("grantsAfterSwap", text)
        self.assertIn("/demo/brain", text)
        self.assertIn("recordVideo", text)
        self.assertGreaterEqual(text.count("await send("), 6)
        self.assertNotIn("qwen", text.lower())
        self.assertNotIn("mockResponse", text)

    def test_demo_workflow_must_download_preserved_zeref_artifact_and_record_full_demo(self) -> None:
        workflow = ROOT / ".github/workflows/beastos-smol-zeref-demo.yml"
        self.assertTrue(workflow.is_file())
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("33132618727", text)
        self.assertIn("9670847045", text)
        self.assertIn("zeref-world-r12-downstream-diagnostic-33132618727", text)
        self.assertIn("454f3017618a81fb9a13393b215d448f365534baf5b607e19d1438955921e425", text)
        self.assertIn("qemu-system-x86_64", text)
        self.assertIn("SYNAPSE_VM_READY", text)
        self.assertIn("live-demo-smol-zeref.mjs", text)
        self.assertIn("smol-zeref-full-demo.mp4", text)
        self.assertIn("SHA256SUMS", text)
        self.assertNotIn("qwen", text.lower())


if __name__ == "__main__":
    unittest.main()
