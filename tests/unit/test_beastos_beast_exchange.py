from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from BEASTOS_WEB_MACHINE.bridge.adapter import BeastExchangeAdapter


class FakeRunner:
    def __init__(self, *, stdout: str = '', returncode: int = 0, stderr: str = '') -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[dict] = []

    def __call__(self, argv, **kwargs):
        self.calls.append({'argv': list(argv), **kwargs})
        return type('Result', (), {
            'stdout': self.stdout,
            'stderr': self.stderr,
            'returncode': self.returncode,
        })()


class BeastExchangeAdapterTests(unittest.TestCase):
    def test_uses_fixed_runtime_exchange_protocol_without_shell(self) -> None:
        response = json.dumps({
            'schema': 'beastbox-response-v1',
            'ok': True,
            'result': {'text': 'continued'},
        })
        runner = FakeRunner(stdout=response)
        with tempfile.TemporaryDirectory() as td:
            adapter = BeastExchangeAdapter(data_dir=Path(td), executable='beastbox', runner=runner)
            result = adapter.chat('hello')
        self.assertEqual(result['result']['text'], 'continued')
        call = runner.calls[0]
        self.assertEqual(call['argv'][:3], ['beastbox', 'runtime', 'exchange'])
        self.assertEqual(call['argv'][3:5], ['--data-dir', td])
        self.assertFalse(call.get('shell', False))
        request = json.loads(call['input'])
        self.assertEqual(request, {'schema': 'beastbox-request-v1', 'operation': 'chat', 'text': 'hello'})

    def test_request_size_is_bounded_before_process_launch(self) -> None:
        runner = FakeRunner()
        adapter = BeastExchangeAdapter(data_dir=Path('/tmp/beast'), runner=runner)
        with self.assertRaises(ValueError):
            adapter.chat('x' * 20000)
        self.assertEqual(runner.calls, [])

    def test_invalid_response_fails_closed_without_fallback(self) -> None:
        runner = FakeRunner(stdout=json.dumps({'ok': True, 'result': {}}))
        adapter = BeastExchangeAdapter(data_dir=Path('/tmp/beast'), runner=runner)
        with self.assertRaises(RuntimeError):
            adapter.inspect()

    def test_nonzero_runtime_exit_does_not_fallback(self) -> None:
        runner = FakeRunner(returncode=2, stderr='runtime error: provider unavailable')
        adapter = BeastExchangeAdapter(data_dir=Path('/tmp/beast'), runner=runner)
        with self.assertRaises(RuntimeError) as raised:
            adapter.chat('hello')
        self.assertIn('provider unavailable', str(raised.exception))
        self.assertEqual(len(runner.calls), 1)

    def test_only_chat_inspect_and_init_are_exposed(self) -> None:
        adapter = BeastExchangeAdapter(data_dir=Path('/tmp/beast'), runner=FakeRunner())
        self.assertFalse(hasattr(adapter, 'shell'))
        self.assertFalse(hasattr(adapter, 'exec'))
        self.assertFalse(hasattr(adapter, 'tool'))


if __name__ == '__main__':
    unittest.main()
