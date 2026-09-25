"""Source acceptance for Synapse live-media boot identity."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GRUB = ROOT / "build/config/bootloaders/grub-pc/grub.cfg"
THEME = ROOT / "build/config/bootloaders/grub-pc/live-theme/theme.txt"


class CosmicBootloaderTests(unittest.TestCase):
    def test_live_menu_is_synapse_branded(self):
        grub = GRUB.read_text(encoding="utf-8")
        self.assertIn("SYNAPSE OS // NEBULA // LIVE", grub)
        self.assertIn("SYNAPSE OS // GENESIS // GATED INSTALLER", grub)
        self.assertIn("@KERNEL_LIVE@ @APPEND_LIVE@", grub)
        self.assertIn("@LB_BOOTAPPEND_LIVE_FAILSAFE@", grub)
        self.assertNotIn("Debian GNU/Linux", grub)

    def test_theme_is_asset_light_and_cosmic(self):
        theme = THEME.read_text(encoding="utf-8")
        self.assertIn('title-text: "SYNAPSE OS // NEBULA"', theme)
        self.assertIn('text = "COSMOS // BEAST BOX // CST"', theme)
        self.assertIn("desktop-color:", theme)
        self.assertNotIn("desktop-image:", theme)
        self.assertNotIn("pixmap", theme.lower())


if __name__ == "__main__":
    unittest.main()
