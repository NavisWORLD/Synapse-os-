from __future__ import annotations

import unittest

from BEASTOS_WEB_MACHINE.bridge.server import BridgeState
from BEASTOS_WEB_MACHINE.bridge.vm import InMemoryVMBackend


class FakeExchange:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def chat(self, text: str) -> dict:
        self.messages.append(text)
        return {
            "schema": "beastbox-response-v1",
            "ok": True,
            "result": {"text": f"continued:{text}", "checkpoint": "abc123"},
        }

    def inspect(self) -> dict:
        return {
            "schema": "beastbox-response-v1",
            "ok": True,
            "result": {"checkpoint": "abc123", "memory_records": 354},
        }


class StoryBridgeTests(unittest.TestCase):
    def test_chat_requires_active_brain(self) -> None:
        state = BridgeState(vm_backend=InMemoryVMBackend(), beast_exchange=FakeExchange())
        with self.assertRaises(PermissionError):
            state.chat("hello")

    def test_chat_uses_beast_exchange_without_transferring_authority(self) -> None:
        exchange = FakeExchange()
        state = BridgeState(vm_backend=InMemoryVMBackend(), beast_exchange=exchange)
        state.clock_in("brain-a")
        state.grant("camera")
        response = state.chat("the sunflower stays")
        self.assertEqual(exchange.messages, ["the sunflower stays"])
        self.assertEqual(response["result"]["text"], "continued:the sunflower stays")
        self.assertEqual(state.authority.grants(), {"camera"})
        trace = state.provenance.records()
        self.assertEqual(trace[-1]["event"], "beast_chat")
        self.assertNotIn("the sunflower stays", str(trace[-1]))

    def test_model_swap_keeps_beast_exchange_but_revokes_keys(self) -> None:
        exchange = FakeExchange()
        state = BridgeState(vm_backend=InMemoryVMBackend(), beast_exchange=exchange)
        state.clock_in("brain-a")
        state.grant("filesystem.write")
        first = state.chat("story one")
        state.clock_in("brain-b")
        second = state.chat("story two")
        self.assertEqual(exchange.messages, ["story one", "story two"])
        self.assertEqual(first["result"]["checkpoint"], second["result"]["checkpoint"])
        self.assertEqual(state.authority.grants(), set())

    def test_inspect_is_read_only_and_records_no_secret_payload(self) -> None:
        state = BridgeState(vm_backend=InMemoryVMBackend(), beast_exchange=FakeExchange())
        result = state.inspect_beast()
        self.assertEqual(result["result"]["memory_records"], 354)
        self.assertEqual(state.provenance.records()[-1]["event"], "beast_inspect")


if __name__ == "__main__":
    unittest.main()
