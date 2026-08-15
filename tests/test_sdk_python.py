import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

SDK_DIR = Path(__file__).resolve().parents[1] / "sdk" / "python"
sys.path.insert(0, str(SDK_DIR))


class PythonSdkTests(unittest.TestCase):
    def test_native_abi_version(self):
        library = os.environ.get("SYNAPSE_ABI_LIBRARY")
        if not library:
            self.skipTest("SYNAPSE_ABI_LIBRARY not provided")
        import synapse_sdk
        importlib.reload(synapse_sdk)
        self.assertEqual(synapse_sdk.abi_version(), 1)

    def test_status_path_argument(self):
        previous = os.environ.pop("SYNAPSE_ABI_LIBRARY", None)
        try:
            import synapse_sdk
            importlib.reload(synapse_sdk)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "status.json"
                path.write_text('{"ok": true}', encoding="utf-8")
                self.assertEqual(synapse_sdk.status(path), {"ok": True})
        finally:
            if previous is not None:
                os.environ["SYNAPSE_ABI_LIBRARY"] = previous


if __name__ == "__main__":
    unittest.main()
