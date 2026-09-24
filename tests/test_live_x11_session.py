"""Regression checks for the non-destructive, live-only SDDM session editor."""
from pathlib import Path
import runpy
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "rootfs/usr/local/lib/synapse/live-x11-session.py"
module = runpy.run_path(str(SCRIPT))
patch = module["patch_autologin"]
patch_environment = module["patch_environment"]


class LiveX11ConfigTests(unittest.TestCase):
    def test_existing_session_only(self):
        original = "[Theme]\nCurrent=synapse-nebula\n[Autologin]\nUser=cory\nSession=plasma.desktop\nRelogin=false\n[General]\nInputMethod=\n"
        revised = patch(original)
        self.assertIn("Session=plasmax11.desktop", revised)
        self.assertNotIn("Session=plasma.desktop", revised)
        self.assertIn("User=cory\n", revised)
        self.assertIn("[Theme]\nCurrent=synapse-nebula\n", revised)
        self.assertIn("[General]\nInputMethod=\n", revised)
        self.assertEqual(patch(revised), revised)

    def test_appends_session_when_existing_section_lacks_one(self):
        original = "[Autologin]\nUser=cory\n\n[Theme]\nCurrent=synapse-nebula\n"
        revised = patch(original)
        self.assertIn("User=cory\n\nSession=plasmax11.desktop\n", revised)
        self.assertIn("[Theme]\nCurrent=synapse-nebula", revised)

    def test_live_vm_compositor_override_is_idempotent(self):
        revised = patch_environment("PATH=/usr/bin\\n")
        self.assertEqual(revised, "PATH=/usr/bin\\nKWIN_COMPOSE=N\\n")
        self.assertEqual(patch_environment(revised), revised)
        self.assertEqual(patch_environment("KWIN_COMPOSE=O\\n"), "KWIN_COMPOSE=O\\n")

    def test_does_not_create_a_user_or_password(self):
        revised = patch("[Theme]\nCurrent=synapse-nebula\n")
        self.assertIn("[Autologin]\nSession=plasmax11.desktop\n", revised)
        self.assertNotIn("User=", revised)
        self.assertNotIn("Password=", revised)


if __name__ == "__main__":
    unittest.main()
