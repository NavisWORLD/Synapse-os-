from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from scripts.real_model_snapshot_trial import package

ROOT=Path(__file__).resolve().parents[1]
GUEST=ROOT/"rootfs/usr/local/lib/synapse/evolution-vm-evaluator.py"
BASELINE_SHA="4855aa5be41c3581f4e37e22384915b736c1b7c7d15140bd66d5460c806ea8ee"
BASELINE_FIXTURE=ROOT/"tests/fixture_snapshot_original_debugger.py.txt"

def historical_baseline():
    data=BASELINE_FIXTURE.read_bytes()
    if hashlib.sha256(data).hexdigest()!=BASELINE_SHA:
        raise ValueError("immutable historical debugger fixture hash mismatch")
    return data.decode("utf-8")

def contract():
    parsed=ast.parse(GUEST.read_text())
    assignments=[node for node in parsed.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=="DEBUGGER_CONTRACT_CODE"
                         for t in node.targets)]
    assert len(assignments)==1
    return ast.literal_eval(assignments[0].value)

class SnapshotIndependentContractTests(unittest.TestCase):
    def invoke(self,role,root):
        env=dict(os.environ)
        env["PYTHONPATH"]=str(root)
        return subprocess.run(
            [sys.executable,"-c",contract(),role],
            cwd=str(root),env=env,text=True,capture_output=True,timeout=25,
        )

    def historical_tree(self,dest):
        # Explicitly replay the old source; current development source already
        # has the VM-verified snapshot and must not become the old baseline.
        where=Path(dest)
        shutil.copytree(ROOT/"src/synapse",where/"synapse",
                        ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
        file=where/"synapse/debugger.py"
        file.write_text(historical_baseline())
        return file

    def test_reviewed_reset_baseline_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.historical_tree(tmp)
            x=self.invoke("baseline",Path(tmp))
            self.assertEqual(x.returncode,0,x.stderr)
            self.assertTrue(json.loads(x.stdout)["passed"])

    def test_candidate_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.historical_tree(tmp)
            before=path.read_text()
            path.write_text(package("return [dict(event) for event in self.events]",before)[2])
            x=self.invoke("candidate",Path(tmp))
            self.assertEqual(x.returncode,0,x.stderr)
            self.assertTrue(json.loads(x.stdout)["passed"])

    def test_baseline_must_reject_missing_snapshot_in_candidate_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.historical_tree(tmp)
            self.assertNotEqual(self.invoke("candidate",Path(tmp)).returncode,0)

    def test_baseline_rejects_snapshots_not_yet_in_deployed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.historical_tree(tmp)
            path.write_text(package("return [event.copy() for event in self.events]",path.read_text())[2])
            self.assertNotEqual(self.invoke("baseline",Path(tmp)).returncode,0)

if __name__=="__main__":
    unittest.main()
