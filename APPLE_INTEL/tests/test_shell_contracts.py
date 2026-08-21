import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ShellContractTests(unittest.TestCase):
    def text(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_installer_runs_preflight_before_genesis(self):
        text = self.text("INSTALL_SYNAPSE_MAC.sh")
        self.assertIn("set -Eeuo pipefail", text)
        self.assertIn("preflight_mac.sh", text)
        self.assertIn("synapse.genesis=1", text)
        self.assertIn("synapse-genesis-installer-api.service", text)
        self.assertNotIn("/dev/sda", text)

    def test_efi_repair_is_explicit_and_non_nvram(self):
        text = self.text("boot/apple_efi_install.sh")
        self.assertIn("--esp", text)
        self.assertIn("--root", text)
        self.assertIn("--target=x86_64-efi", text)
        self.assertIn("--removable", text)
        self.assertIn("--no-nvram", text)
        self.assertNotIn("efibootmgr -c", text)
        self.assertNotIn("/dev/sda", text)

    def test_command_wrappers_delegate_to_shell(self):
        self.assertIn("INSTALL_SYNAPSE_MAC.sh", self.text("INSTALL_SYNAPSE_MAC.command"))
        self.assertIn("RECOVER_SYNAPSE_MAC.sh", self.text("RECOVER_SYNAPSE_MAC.command"))

if __name__ == "__main__":
    unittest.main()
