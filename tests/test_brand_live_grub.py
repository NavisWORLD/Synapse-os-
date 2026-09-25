"""Regression tests for final live-build GRUB branding."""
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / "scripts/brand_live_grub.py"))
brand = MODULE["brand"]


class BrandLiveGrubTests(unittest.TestCase):
    def test_preserves_rendered_kernel_arguments_while_rebranding(self):
        source = """source /boot/grub/config.cfg

menuentry "Live system (amd64)" --hotkey=l {
 linux /live/vmlinuz-6.12 boot=live components quiet splash findiso=${iso_path}
 initrd /live/initrd.img-6.12
}
menuentry "Live system (amd64 fail-safe mode)" {
 linux /live/vmlinuz-6.12 boot=live components synapse.genesis=1
 initrd /live/initrd.img-6.12
}
submenu 'Utilities...' --hotkey=u {
 source /boot/grub/theme.cfg
}
"""
        rendered = brand(source)
        self.assertIn('menuentry "SYNAPSE OS // NEBULA // LIVE" --hotkey=s {', rendered)
        self.assertIn('menuentry "SYNAPSE OS // GENESIS // GATED INSTALLER" --hotkey=g {', rendered)
        self.assertIn('submenu "SYNAPSE // ADVANCED" --hotkey=u {', rendered)
        self.assertIn("findiso=${iso_path}", rendered)
        self.assertIn("synapse.genesis=1", rendered)
        self.assertNotIn("Live system (amd64)", rendered)

    def test_fails_closed_without_genesis_failsafe(self):
        with self.assertRaises(ValueError):
            brand('menuentry "Live system (amd64)" --hotkey=l {\n}\n')

    def test_rejects_remaining_debian_branding(self):
        source = """# Debian GNU/Linux title
menuentry "Live system (amd64)" --hotkey=l {
}
menuentry "Live system (amd64 fail-safe mode)" {
}
"""
        with self.assertRaises(ValueError):
            brand(source)


if __name__ == "__main__":
    unittest.main()
