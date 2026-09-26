"""Offline independent checks of model-bound single-line snapshot proposal."""
from __future__ import annotations
import ast
from pathlib import Path
import hashlib
import unittest
from scripts.real_model_snapshot_trial import ALLOWED, SUFFIX, normalize, package

ROOT = Path(__file__).resolve().parents[1]

class SnapshotTrialTests(unittest.TestCase):
    def baseline(self):
        # Reproduce the historical, independent pre-promotion input rather than
        # assuming the current development source is missing the new method.
        data = (ROOT / "tests/fixture_snapshot_original_debugger.py.txt").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "4855aa5be41c3581f4e37e22384915b736c1b7c7d15140bd66d5460c806ea8ee")
        return data.decode("utf-8")

    def test_one_statement_is_exactly_model_scope(self):
        before = self.baseline()
        for raw in ALLOWED:
            statement, note, after = package(raw, before)
            self.assertEqual(statement, raw)
            self.assertEqual(note, "RAW_ONE_LINE")
            self.assertEqual(after, before + SUFFIX + "        " + raw + "\n")
            self.assertEqual(len(ast.parse(after).body), len(ast.parse(before).body))

    def test_one_optional_wrapper_only(self):
        raw = chr(96) * 3 + "python\nreturn [dict(event) for event in self.events]\n" + chr(96) * 3
        statement, note = normalize(raw)
        self.assertEqual(statement, "return [dict(event) for event in self.events]")
        self.assertEqual(note, "SINGLE_FENCE_STRIPPED")

    def test_incorrect_sharing_mutation_and_commands_fail(self):
        for bad in (
            "return self.events",
            "return list(self.events)",
            "return self.events.copy()",
            "self.events.clear()",
            "return [dict(event) for event in self.events]; import os",
            "return [dict(event) for event in self.events]\nimport os",
            "return eval(input())",
            "return [copy.deepcopy(event) for event in self.events]",
            "Here is the correct code:",
        ):
            with self.subTest(raw=bad), self.assertRaises(ValueError):
                normalize(bad)

    def test_stale_existing_method_and_removed_reset_fail(self):
        original=self.baseline()
        for unsafe in (
            original + SUFFIX + "        return []\n",
            original.replace("self.events.clear()", "self.events = []"),
        ):
            with self.subTest(unsafe=unsafe[:30]), self.assertRaises(ValueError):
                package(next(iter(ALLOWED)), unsafe)

    def test_candidate_keeps_original_source_bytes(self):
        before = self.baseline()
        _, _, after = package("return [dict(event) for event in self.events]", before)
        self.assertEqual(after[:len(before)], before)
        self.assertEqual(after.count("def snapshot_events("), 1)
        self.assertIn("def run(self, *, reset_events: bool = False)", after)

if __name__ == "__main__":
    unittest.main()
