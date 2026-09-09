from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BeastOSLiveDemoContractTests(unittest.TestCase):
    def test_guest_boot_emits_real_hardware_receipt_markers(self) -> None:
        smoke = (ROOT / "rootfs/usr/local/lib/synapse/vm-smoke").read_text(encoding="utf-8")
        self.assertIn("SYNAPSE_VM_HW_BEGIN", smoke)
        self.assertIn("SYNAPSE_VM_HW_END", smoke)
        self.assertIn("/sys/class/dmi/id/sys_vendor", smoke)
        self.assertIn("/proc/cpuinfo", smoke)
        self.assertIn("/proc/meminfo", smoke)

    def test_live_demo_uses_canonical_vm_budget_and_real_recorders(self) -> None:
        workflow = (ROOT / ".github/workflows/beastos-boot-local-live-demo.yml").read_text(encoding="utf-8")
        self.assertIn("-m 4096", workflow)
        self.assertIn("ffmpeg", workflow)
        self.assertIn("qemu-system-x86_64", workflow)
        self.assertIn("smollm2:135m", workflow)
        self.assertIn("live-demo.mjs", workflow)
        self.assertNotIn("FakeExchange", workflow)

    def test_browser_demo_script_records_raw_model_turns_and_capabilities(self) -> None:
        script = ROOT / "BEASTOS_WEB_MACHINE/scripts/live-demo.mjs"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn("recordVideo", text)
        self.assertIn("conversation.json", text)
        self.assertIn("browser-capabilities.json", text)
        self.assertIn(".beast-turn.beast", text)
        self.assertNotIn("mockResponse", text)


if __name__ == "__main__":
    unittest.main()
