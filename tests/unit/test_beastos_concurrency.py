"""Regression coverage for ThreadingHTTPServer request interleaving.

The real Beast continuity directory is owned by one bridge. Model exchanges,
brain swaps and permission changes must not race while a subprocess is active.
"""
from __future__ import annotations

from threading import Event, Thread
import unittest

from BEASTOS_WEB_MACHINE.bridge.server import BridgeState
from BEASTOS_WEB_MACHINE.bridge.vm import InMemoryVMBackend


class BlockingExchange:
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()
        self.count = 0
        self.second_entered = Event()

    def chat(self, text: str) -> dict:
        self.count += 1
        if self.count == 1:
            self.entered.set()
            if not self.release.wait(5):
                raise TimeoutError("test failed to release first exchange")
        else:
            self.second_entered.set()
        return {
            "schema": "beastbox-response-v1",
            "ok": True,
            "result": {"text": text},
        }

    def inspect(self) -> dict:
        return {"schema": "beastbox-response-v1", "ok": True, "result": {}}


class ContinuityConcurrencyTests(unittest.TestCase):
    def test_brain_swap_waits_for_old_brain_chat_receipt(self) -> None:
        exchange = BlockingExchange()
        state = BridgeState(vm_backend=InMemoryVMBackend(), beast_exchange=exchange)
        state.clock_in("brain-a")
        state.grant("filesystem.write")
        errors: list[BaseException] = []
        swapped = Event()

        def chat() -> None:
            try:
                state.chat("from brain a")
            except BaseException as exc:
                errors.append(exc)

        def swap() -> None:
            try:
                state.clock_in("brain-b")
            except BaseException as exc:
                errors.append(exc)
            finally:
                swapped.set()

        worker = Thread(target=chat, daemon=True)
        switcher = Thread(target=swap, daemon=True)
        worker.start()
        try:
            self.assertTrue(exchange.entered.wait(3), "first chat did not enter")
            switcher.start()
            self.assertFalse(swapped.wait(0.15), "brain switched during old brain chat")
        finally:
            exchange.release.set()
            worker.join(5)
            if switcher.ident is not None:
                switcher.join(5)

        self.assertFalse(worker.is_alive())
        self.assertFalse(switcher.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(state.status()["active_brain"], "brain-b")
        self.assertEqual(state.status()["grants"], [])
        events = [record for record in state.provenance_records()
                  if record["event"] in {"beast_chat", "brain_clock_in"}]
        self.assertEqual(events[-2]["event"], "beast_chat")
        self.assertEqual(events[-2]["data"]["brain"], "brain-a")
        self.assertEqual(events[-1]["event"], "brain_clock_in")
        self.assertEqual(events[-1]["data"]["brain"], "brain-b")

    def test_two_chats_never_write_shared_beast_store_simultaneously(self) -> None:
        exchange = BlockingExchange()
        state = BridgeState(vm_backend=InMemoryVMBackend(), beast_exchange=exchange)
        state.clock_in("brain-a")
        errors: list[BaseException] = []
        second_started = Event()

        def send(text: str, started: Event | None = None) -> None:
            try:
                if started:
                    started.set()
                state.chat(text)
            except BaseException as exc:
                errors.append(exc)

        first = Thread(target=send, args=("one",), daemon=True)
        second = Thread(target=send, args=("two", second_started), daemon=True)
        first.start()
        try:
            self.assertTrue(exchange.entered.wait(3), "first chat did not enter")
            second.start()
            self.assertTrue(second_started.wait(3), "second thread did not start")
            self.assertFalse(exchange.second_entered.wait(0.15),
                             "second exchange entered before the first completed")
        finally:
            exchange.release.set()
            first.join(5)
            if second.ident is not None:
                second.join(5)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(exchange.count, 2)
        chats = [record for record in state.provenance_records()
                 if record["event"] == "beast_chat"]
        self.assertEqual(len(chats), 2)
        self.assertTrue(all(record["data"]["brain"] == "brain-a" for record in chats))


if __name__ == "__main__":
    unittest.main()
