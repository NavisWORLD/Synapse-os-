from __future__ import annotations
import ast
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
        result=subprocess.run(
            [sys.executable,"-c",contract(),role],
            cwd=str(root),env=env,text=True,capture_output=True,timeout=25,
        )
        return result

    def test_reviewed_reset_baseline_passes(self):
        x=self.invoke("baseline",ROOT/"src")
        self.assertEqual(x.returncode,0,x.stderr)
        self.assertTrue(json.loads(x.stdout)["passed"])

    def test_candidate_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            where=Path(tmp)
            shutil.copytree(ROOT/"src/synapse",where/"synapse",
                            ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
            path=where/"synapse/debugger.py"
            before=path.read_text()
            path.write_text(package("return [dict(event) for event in self.events]",before)[2])
            x=self.invoke("candidate",where)
            self.assertEqual(x.returncode,0,x.stderr)
            self.assertTrue(json.loads(x.stdout)["passed"])

    def test_baseline_must_reject_missing_snapshot_in_candidate_role(self):
        self.assertNotEqual(self.invoke("candidate",ROOT/"src").returncode,0)

    def test_baseline_rejects_snapshots_not_yet_in_deployed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            where=Path(tmp)
            shutil.copytree(ROOT/"src/synapse",where/"synapse",
                            ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
            path=where/"synapse/debugger.py"
            path.write_text(package("return [event.copy() for event in self.events]",path.read_text())[2])
            self.assertNotEqual(self.invoke("baseline",where).returncode,0)

if __name__=="__main__":
    unittest.main()
