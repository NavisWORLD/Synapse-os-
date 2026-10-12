from pathlib import Path
import shutil
import tempfile
import unittest

from BEASTOS_WEB_MACHINE.bridge.adapter import BeastExchangeAdapter
from BEASTOS_WEB_MACHINE.bridge.server import initialize_runtime


class FirstLaunchTests(unittest.TestCase):
    def test_startup_initializes_through_existing_protocol_without_chat(self):
        class Exchange:
            def __init__(self):
                self.calls = []

            def init(self):
                self.calls.append("init")
                return {"schema": "beastbox-response-v1", "ok": True, "result": {"turn": 0}}

        exchange = Exchange()
        self.assertTrue(initialize_runtime(exchange)["ok"])
        self.assertEqual(exchange.calls, ["init"])

    def test_startup_error_is_not_swallowed(self):
        class Exchange:
            def init(self):
                raise RuntimeError("corrupt checkpoint")

        with self.assertRaisesRegex(RuntimeError, "corrupt checkpoint"):
            initialize_runtime(Exchange())

    @unittest.skipUnless(shutil.which("beastbox"), "requires the installed Beast Box runtime")
    def test_actual_runtime_first_launch_and_restart_preserve_identity_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            exchange = BeastExchangeAdapter(data_dir=Path(directory), executable=shutil.which("beastbox"))
            first = initialize_runtime(exchange)["result"]
            same = initialize_runtime(exchange)["result"]
            self.assertEqual(first, same)
            exchange.chat("Synapse isolated continuity fixture; reference output is not inference")
            after = exchange.inspect()["result"]
            restarted = initialize_runtime(exchange)["result"]
            self.assertEqual(after, restarted)
            self.assertEqual(first["system_id"], after["system_id"])
            self.assertEqual(first["turn"] + 1, after["turn"])


if __name__ == "__main__":
    unittest.main()
