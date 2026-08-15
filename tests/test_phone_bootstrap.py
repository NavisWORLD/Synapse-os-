from pathlib import Path
import tempfile
import unittest
from unittest import mock

from synapse.phone_bootstrap import InstallManager, device_snapshot, resolve_ui_path


class PhoneBootstrapTests(unittest.TestCase):
    def test_device_snapshot_has_required_shape(self):
        with mock.patch("synapse.phone_bootstrap._network_addresses", return_value=[]), mock.patch(
            "synapse.phone_bootstrap._port_open", return_value=False
        ):
            data = device_snapshot()
        self.assertIn("hostname", data)
        self.assertIn("machine", data)
        self.assertIn("disk_root", data)
        self.assertIn("cosmos_ports", data)
        self.assertIn("11434", data["cosmos_ports"])

    def test_install_is_disabled_without_explicit_flag(self):
        manager = InstallManager(install_root=Path("/tmp/unused-cosmos"), allow_install=False, activate=False)
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            manager.start()

    def test_existing_non_git_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "COSMOS"
            root.mkdir()
            manager = InstallManager(install_root=root, allow_install=True, activate=False)
            with mock.patch("synapse.phone_bootstrap.shutil.which", return_value="/usr/bin/git"):
                with self.assertRaisesRegex(RuntimeError, "not a git checkout"):
                    manager._install()

    def test_resolve_explicit_ui_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ui.html"
            path.write_text("<html></html>", encoding="utf-8")
            self.assertEqual(resolve_ui_path(str(path)), path.resolve())


if __name__ == "__main__":
    unittest.main()
