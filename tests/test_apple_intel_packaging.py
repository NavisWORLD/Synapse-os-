import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class AppleIntelPackagingTests(unittest.TestCase):
    def test_build_copies_apple_target_into_amd64_live_image(self):
        text = (ROOT / 'build' / 'build.sh').read_text(encoding='utf-8')
        self.assertIn('APPLE_INTEL', text)
        self.assertIn('usr/share/synapse/apple-intel', text)
        self.assertIn('if [[ "$ARCH" == "amd64" ]]', text)

    def test_hook_exposes_safe_launchers(self):
        text = (ROOT / 'build' / 'hooks' / '040-apple-intel.hook.chroot').read_text(encoding='utf-8')
        self.assertIn('synapse-apple-preflight', text)
        self.assertIn('synapse-apple-diagnostics', text)
        self.assertIn('synapse-apple-install', text)

    def test_makefile_lints_and_tests_apple_tree(self):
        text = (ROOT / 'Makefile').read_text(encoding='utf-8')
        self.assertIn('APPLE_INTEL/tests', text)
        self.assertIn('APPLE_INTEL', text)

if __name__ == '__main__': unittest.main()
