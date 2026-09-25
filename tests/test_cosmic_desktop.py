"""Source-level acceptance for Synapse desktop identity (not a GUI certification)."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
WELCOME = ROOT / "rootfs/usr/local/bin/synapse-welcome"
AUTOSTART = ROOT / "rootfs/etc/xdg/autostart/synapse-welcome.desktop"
APP = ROOT / "rootfs/usr/share/applications/synapse-welcome.desktop"
HOOK = ROOT / "build/hooks/010-synapse.hook.chroot"
KDE_WELCOME = ROOT / "rootfs/etc/skel/.config/plasma-welcomerc"
FAVORITES = ROOT / "rootfs/etc/xdg/kicker-extra-favoritesrc"
WALLPAPER = ROOT / "rootfs/usr/share/wallpapers/SynapseOS/contents/images/3840x2160.svg"


class CosmicDesktopSourceTests(unittest.TestCase):
    def test_welcome_compiles_and_launches_only_explicit_apps(self):
        source = WELCOME.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"/usr/local/bin/synapse-control"', source)
        self.assertIn('"/usr/bin/konsole"', source)
        self.assertIn('"/usr/bin/dolphin"', source)
        self.assertIn('"/usr/local/bin/synapse-beastos-web"', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("HF_TOKEN", source)
        self.assertIn('button.setShortcut(shortcut)', source)
        self.assertIn('"Alt+B"', source)
        self.assertIn('"Alt+S"', source)
        self.assertIn('"Alt+F"', source)
        self.assertIn('"Alt+T"', source)

    def test_first_run_is_user_owned_and_opt_in(self):
        source = WELCOME.read_text(encoding="utf-8")
        auto = AUTOSTART.read_text(encoding="utf-8")
        self.assertIn('STATE_MARKER.exists()', source)
        self.assertIn('STATE_MARKER.touch(', source)
        self.assertIn('BEAST_RUNTIME.is_file()', source)
        self.assertIn('not verified or selected', source)
        self.assertIn("Exec=/usr/local/bin/synapse-welcome --first-run", auto)
        self.assertIn("OnlyShowIn=KDE;", auto)

    def test_image_includes_real_launcher_and_cosmic_identity(self):
        installed = APP.read_text(encoding="utf-8")
        hook = HOOK.read_text(encoding="utf-8")
        wallpaper = WALLPAPER.read_text(encoding="utf-8")
        self.assertIn("Exec=/usr/local/bin/synapse-welcome", installed)
        self.assertIn("chmod 0755 /usr/local/bin/synapse-welcome", hook)
        self.assertIn("Synapse-Welcome.desktop", hook)
        self.assertIn("COSMOS // BEAST BOX // CST", wallpaper)
        favorites = FAVORITES.read_text(encoding="utf-8")
        self.assertIn("beastos-web.desktop", favorites)
        self.assertIn("synapse-control.desktop", favorites)
        self.assertIn("IgnoreDefaults=false", favorites)
        self.assertIn("ShouldShow=false", KDE_WELCOME.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
