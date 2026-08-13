import unittest
from synapse.dsl import parse_lines


class DSLTests(unittest.TestCase):
    def test_valid_plan(self):
        plan = parse_lines(["SYNAPSE/1", "profile pulse", "cosmos probe", "service check NetworkManager"])
        self.assertEqual([x.op for x in plan], ["profile", "cosmos", "service"])

    def test_missing_header(self):
        with self.assertRaises(ValueError):
            parse_lines(["profile pulse"])

    def test_arbitrary_shell_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_lines(["SYNAPSE/1", "exec rm -rf /"])

    def test_service_injection_rejected(self):
        with self.assertRaises(ValueError):
            parse_lines(["SYNAPSE/1", "service check foo;reboot"])
