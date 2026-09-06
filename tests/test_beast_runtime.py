"""Exercise the user-space install boundary with subprocesses outside this tree."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class BeastRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synapse-beast-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = {**os.environ, "HOME": str(self.home), "XDG_DATA_HOME": str(self.home / "data"),
                    "PYTHONPATH": str(ROOT / "src")}
        self.wheel = self.home / "cosmos_beast_box-99.0.0-py3-none-any.whl"
        with zipfile.ZipFile(self.wheel, "w") as z:
            z.writestr("cosmos_beast_box-99.0.0.dist-info/METADATA",
                       "Metadata-Version: 2.1\nName: cosmos-beast-box\nVersion: 99.0.0\n")
            z.writestr("cosmos_beast_box-99.0.0.dist-info/WHEEL",
                       "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            z.writestr("cosmos_beast_box-99.0.0.dist-info/RECORD", "")
            z.writestr("beastbox/__init__.py", "")
            z.writestr("beastbox/__main__.py", '''import argparse, json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("runtime")
p.add_argument("action")
p.add_argument("--data-dir", required=True)
a=p.parse_args()
d=Path(a.data_dir); d.mkdir(parents=True, exist_ok=True)
f=d/"state.json"
n=json.loads(f.read_text())["starts"] if f.exists() else 0
if a.action=="init": n+=1; f.write_text(json.dumps({"starts": n}))
print(json.dumps({"starts": n, "data_dir": str(d)}))
''')
        self.digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()

    def cli(self, *args, root=False):
        command = [sys.executable, "-m", "synapse.beast_runtime", *args]
        if os.geteuid() == 0 and not root:
            # Single-UID containers cannot drop privileges. This substitutes only
            # the identity check; normal CI runners execute the CLI unchanged.
            command = [sys.executable, "-c",
                       "import os, runpy; os.geteuid=lambda: 1000; "
                       "runpy.run_module('synapse.beast_runtime', run_name='__main__')", *args]
        return subprocess.run(command, cwd=self.home, env=self.env,
                              text=True, capture_output=True)

    def install(self, digest=None):
        return self.cli("install", "--wheel", str(self.wheel), "--sha256", digest or self.digest)

    def test_hash_mismatch_creates_no_install(self):
        result = self.install("0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256 mismatch", result.stderr)
        self.assertFalse((self.home / "data" / "synapse-beast").exists())

    def test_local_wheel_requires_explicit_hash(self):
        result = self.cli("install", "--wheel", str(self.wheel))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --sha256", result.stderr)

    @unittest.skipUnless(os.geteuid() == 0, "requires root to exercise refusal")
    def test_root_install_refused(self):
        result = self.cli("install", "--wheel", str(self.wheel), "--sha256", self.digest, root=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("normal user", result.stderr)
        self.assertFalse((self.home / "data").exists())

    def test_install_run_restart_and_idempotent_install(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in (1, 2):
            result = self.cli("run", "init")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["starts"], expected)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("run", "inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["starts"], 2)
        self.assertEqual(json.loads(result.stdout)["data_dir"], str(self.home / "data/synapse-beast/runtime"))
        result = self.cli("run", "inspect", "--data-dir", "/tmp/escape")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed by synapse-beast", result.stderr)

    @unittest.skipUnless(os.environ.get("SYNAPSE_BEAST_RELEASE_WHEEL"), "published wheel not supplied")
    def test_published_release_install_and_restart(self):
        from synapse.beast_runtime import RELEASE_SHA256
        self.wheel.write_bytes(Path(os.environ["SYNAPSE_BEAST_RELEASE_WHEEL"]).read_bytes())
        # pip validates filename against archive metadata.
        correct = self.wheel.with_name("cosmos_beast_box-0.4.0-py3-none-any.whl")
        self.wheel.rename(correct)
        self.wheel = correct
        result = self.install(RELEASE_SHA256)
        self.assertEqual(result.returncode, 0, result.stderr)
        first = self.cli("run", "init")
        self.assertEqual(first.returncode, 0, first.stderr)
        system_id = json.loads(first.stdout)["system_id"]
        written = self.cli("run", "chat", "Remember the sunflower code is marigold")
        self.assertEqual(written.returncode, 0, written.stderr)
        recalled = self.cli("run", "chat", "What is the sunflower code?")
        self.assertEqual(recalled.returncode, 0, recalled.stderr)
        self.assertIn("marigold", json.loads(recalled.stdout)["model"]["prompt"])
        inspected = self.cli("run", "inspect")
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        state = json.loads(inspected.stdout)
        self.assertEqual(state["system_id"], system_id)
        self.assertEqual(state["turn"], 2)
        self.assertTrue(state["valid"])


if __name__ == "__main__":
    unittest.main()
