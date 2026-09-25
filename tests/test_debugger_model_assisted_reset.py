"""Independent regression for the opt-in model-assisted debugger trace reset.

The complete source change is assembled from a fixed trusted method template
and one feedback-corrected real-model statement. These tests are independent
of prompts or generated code and run on the exact candidate source.
"""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from synapse.debugger import Debugger


class OneEventVM:
    def __init__(self, module, *, capabilities, trace):
        self.trace = trace

    def run(self):
        origin = {"line": 7, "payload": "original"}
        self.trace(origin)
        assert "breakpoint" not in origin, "the source event was mutated"
        return {"ok": True}


class ModelAssistedTraceResetTests(unittest.TestCase):
    def test_reset_is_keyword_only_and_defaults_to_false(self):
        signature = inspect.signature(Debugger.run)
        self.assertEqual(
            signature.parameters["reset_events"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIs(signature.parameters["reset_events"].default, False)

    def test_normal_runs_retain_cumulative_history_and_original_list_identity(self):
        debugger = Debugger(module=None, breakpoints={7})
        original_list = debugger.events
        with patch("synapse.debugger.VM", OneEventVM):
            first = debugger.run()
            self.assertEqual(len(original_list), 1)
            second = debugger.run()
            self.assertEqual(len(original_list), 2)
        self.assertIs(first["events"], original_list)
        self.assertIs(second["events"], original_list)
        self.assertTrue(all(item["breakpoint"] is True for item in original_list))
        self.assertTrue(all(item["payload"] == "original" for item in original_list))

    def test_opt_in_reset_clears_same_existing_list_before_new_trace(self):
        debugger = Debugger(module=None, breakpoints={7})
        original_list = debugger.events
        with patch("synapse.debugger.VM", OneEventVM):
            debugger.run()
            debugger.run()
            self.assertEqual(len(original_list), 2)
            result = debugger.run(reset_events=True)
            self.assertEqual(len(original_list), 1)
            self.assertIs(result["events"], original_list)
            self.assertIs(debugger.events, original_list)
            self.assertTrue(original_list[0]["breakpoint"])
            debugger.run(reset_events=False)
            self.assertEqual(len(original_list), 2)

    def test_truthy_opt_in_does_not_change_breakpoints_or_capabilities(self):
        debugger = Debugger(module=None, breakpoints={999})
        original_breakpoints = debugger.breakpoints
        original_capabilities = debugger.capabilities
        with patch("synapse.debugger.VM", OneEventVM):
            result = debugger.run(reset_events=True)
        self.assertIs(debugger.breakpoints, original_breakpoints)
        self.assertIs(debugger.capabilities, original_capabilities)
        self.assertFalse(result["events"][0]["breakpoint"])

    def test_positional_reset_flag_is_rejected(self):
        debugger = Debugger(module=None)
        with self.assertRaises(TypeError):
            debugger.run(True)


if __name__ == "__main__":
    unittest.main()
