"""Independent static verification of the RAW native proposal acceptance gate."""
import unittest
from scripts.real_rawrphos_event_count_trial import (
    ACCEPTED_STATEMENT, EXPECTED_WEIGHT_SHA256, normalize, package,
    verify_model_info,
)

BASE = '''from __future__ import annotations
from typing import Any
class Debugger:
    def __init__(self):
        self.events: list[dict[str, Any]] = []
    def run(self, *, reset_events: bool = False):
        if reset_events:
            self.events.clear()
        return self.events
'''

class RawrphosTrialTests(unittest.TestCase):
    def test_exact_model_text_only(self):
        self.assertEqual(normalize(ACCEPTED_STATEMENT), ACCEPTED_STATEMENT)
        self.assertEqual(normalize('\x60\x60\x60python\nreturn len(self.events)\n\x60\x60\x60'), ACCEPTED_STATEMENT)
        for sample in ('x' + ACCEPTED_STATEMENT, 'return 3',
                       'return len(self.events)\nprint(4)',
                       'return len(self.events) # generated', '  ',
                       'The answer is: return len(self.events)', 'return len(self.breakpoints)'):
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                normalize(sample)

    def test_trusted_template_only(self):
        line, candidate = package(ACCEPTED_STATEMENT, BASE)
        self.assertEqual(line, ACCEPTED_STATEMENT)
        self.assertEqual(candidate.count('def event_count('), 1)
        self.assertIn('self.events.clear()', candidate)
        self.assertEqual(candidate[:len(BASE)], BASE)
        with self.assertRaises(ValueError):
            package(ACCEPTED_STATEMENT, candidate)
        with self.assertRaises(ValueError):
            package('return 3', BASE)

    def test_checkpoint_attestation_is_strict(self):
        actual = {
            'model_id': 'rawrphos-native', 'checkpoint_sha256': EXPECTED_WEIGHT_SHA256,
            'training_steps': 12000, 'serving_backend': 'pytorch-cpu'
        }
        verify_model_info(actual)
        for key, bad in [('model_id', 'qwen'), ('checkpoint_sha256', '0'*64),
                         ('training_steps', 18000), ('serving_backend', 'remote')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_model_info(dict(actual, **{key: bad}))

if __name__ == '__main__':
    unittest.main()
