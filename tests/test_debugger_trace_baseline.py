"""Independent baseline behavior tests before any disposable model patch."""
import inspect
import unittest
from unittest.mock import patch

from synapse.debugger import Debugger


class DebuggerBaselineContract(unittest.TestCase):
    def test_trace_copies_event_and_keeps_breakpoint_flag(self):
        debugger = Debugger(module=None, breakpoints={5})
        event = {"line": 5, "payload": "original"}
        debugger._trace(event)
        self.assertNotIn("breakpoint", event)
        self.assertIsNot(debugger.events[0], event)
        self.assertTrue(debugger.events[0]["breakpoint"])

    def test_existing_default_run_history_is_unchanged(self):
        debugger = Debugger(module=None, breakpoints={7})
        original_list = debugger.events

        class StubVM:
            def __init__(self, module, *, capabilities, trace):
                self.trace = trace
            def run(self):
                self.trace({"line": 7})
                return {"ok": True}

        with patch("synapse.debugger.VM", StubVM):
            self.assertEqual(len(debugger.run()["events"]), 1)
            self.assertEqual(len(debugger.run()["events"]), 2)
        self.assertIs(original_list, debugger.events)
        self.assertNotIn("reset_events", inspect.signature(Debugger.run).parameters)


if __name__ == "__main__":
    unittest.main()
