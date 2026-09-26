"""Independent source regression for the model-assisted shallow trace snapshot.

Tests are human-authored and are not treated as model-origin evidence.
Only the return statement inside snapshot_events was authored by the model.
"""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from synapse.debugger import Debugger


class StubVM:
    def __init__(self, module, *, capabilities, trace):
        self.trace = trace

    def run(self):
        original = {"line": 7, "payload": {"nested": "shared"}}
        self.trace(original)
        assert "breakpoint" not in original
        return {"ok": True}


class SnapshotSourceTests(unittest.TestCase):
    def test_empty_snapshot_is_a_new_list(self):
        dbg = Debugger(module=None)
        snapshot = dbg.snapshot_events()
        self.assertEqual(snapshot, [])
        self.assertIsNot(snapshot, dbg.events)

    def test_snapshot_copies_list_and_top_level_event_dicts(self):
        dbg = Debugger(module=None, breakpoints={7})
        with patch("synapse.debugger.VM", StubVM):
            dbg.run()
            dbg.run()
        saved = dbg.events
        copy = dbg.snapshot_events()
        self.assertEqual(len(copy), 2)
        self.assertIsNot(copy, saved)
        self.assertTrue(all(x == y and x is not y for x, y in zip(copy, saved)))
        copy[0]["line"] = 99
        copy.append({"line": 100})
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["line"], 7)
        self.assertIs(saved, dbg.events)
        self.assertTrue(all(event["breakpoint"] for event in saved))

    def test_shallow_scope_is_explicit_not_deep_immutability(self):
        dbg = Debugger(module=None)
        dbg.events.append({"nested": {"a": 1}})
        snap = dbg.snapshot_events()
        self.assertIsNot(snap[0], dbg.events[0])
        self.assertIs(snap[0]["nested"], dbg.events[0]["nested"])

    def test_prior_reset_contract_is_preserved(self):
        dbg = Debugger(module=None, breakpoints={7})
        shared = dbg.events
        signature = inspect.signature(Debugger.run)
        self.assertEqual(signature.parameters["reset_events"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(signature.parameters["reset_events"].default, False)
        with patch("synapse.debugger.VM", StubVM):
            dbg.run()
            dbg.run()
            self.assertEqual(len(shared), 2)
            dbg.run(reset_events=True)
        self.assertIs(dbg.events, shared)
        self.assertEqual(len(shared), 1)
        self.assertEqual(len(dbg.snapshot_events()), 1)
        with self.assertRaises(TypeError):
            dbg.run(True)


if __name__ == "__main__":
    unittest.main()
