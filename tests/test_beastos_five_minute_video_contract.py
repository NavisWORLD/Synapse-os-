from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BeastOSFiveMinuteVideoContractTests(unittest.TestCase):
    def test_five_minute_browser_script_exists_and_records_extended_real_conversation(self) -> None:
        script = ROOT / "BEASTOS_WEB_MACHINE/scripts/live-demo-5min.mjs"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn("recordVideo", text)
        self.assertIn("conversation-5min.json", text)
        self.assertIn("qwen2.5:0.5b", text)
        self.assertIn("filesystem.write", text)
        self.assertIn("Demo Brain B", text)
        self.assertGreaterEqual(text.count("await send("), 6)
        self.assertNotIn("mockResponse", text)

    def test_workflow_records_boot_then_conversation_and_seals_exact_five_minute_mp4(self) -> None:
        workflow = ROOT / ".github/workflows/beastos-five-minute-video.yml"
        self.assertTrue(workflow.is_file())
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("qemu-system-x86_64", text)
        self.assertIn("SYNAPSE_VM_READY", text)
        self.assertIn("qwen2.5:0.5b", text)
        self.assertIn("live-demo-5min.mjs", text)
        self.assertIn("beastos-five-minute-demo.mp4", text)
        self.assertIn("duration=300", text)
        self.assertIn("SHA256SUMS", text)
        self.assertNotIn("FakeExchange", text)


if __name__ == "__main__":
    unittest.main()
