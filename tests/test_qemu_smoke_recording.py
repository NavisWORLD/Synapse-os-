#!/usr/bin/env python3
"""Contract tests for the QEMU smoke runner's optional display surface."""

from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qemu-smoke.sh"


class QemuSmokeRecordingContractTests(unittest.TestCase):
    def test_headless_remains_default_and_recording_can_request_display(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SYNAPSE_QEMU_DISPLAY="${SYNAPSE_QEMU_DISPLAY:-none}"', text)
        self.assertIn('-display "$SYNAPSE_QEMU_DISPLAY"', text)

    def test_live_boot_contract_is_preserved(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('systemd.unit=multi-user.target', text)
        self.assertIn('synapse.vmtest=1', text)
        self.assertIn("SYNAPSE_VM_READY", text)
        self.assertIn("SYNAPSE_VM_FAIL:", text)


if __name__ == "__main__":
    unittest.main()
