"""Source checks for live-only Synapse desktop cleanup and VM display tuning."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "rootfs/usr/local/lib/synapse/live-desktop-polish"
AUTOSTART = ROOT / "rootfs/etc/xdg/autostart/synapse-live-desktop-polish.desktop"


class LiveDesktopPolishTests(unittest.TestCase):
    def test_changes_are_live_only_and_non_destructive(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("boot=live", source)
        self.assertIn("Name=Install Debian", source)
        self.assertIn("rm -f --", source)
        self.assertNotIn("Install Synapse OS", source)
        self.assertNotIn("sudo", source)

    def test_qemu_resolution_is_best_effort_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("qemu", source.lower())
        self.assertIn("bochs", source.lower())
        self.assertIn("1024x768", source)
        self.assertIn("800x600", source)
        self.assertIn("|| true", source)

    def test_autostart_is_hidden_kde_only(self):
        desktop = AUTOSTART.read_text(encoding="utf-8")
        self.assertIn("OnlyShowIn=KDE;", desktop)
        self.assertIn("NoDisplay=true", desktop)
        self.assertIn("Exec=/usr/local/lib/synapse/live-desktop-polish", desktop)


if __name__ == "__main__":
    unittest.main()
