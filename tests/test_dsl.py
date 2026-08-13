import tempfile
from pathlib import Path
import unittest

from synapse.dsl import FlowError, Runtime, apply, parse_file, parse_lines


class DSLTests(unittest.TestCase):
    def test_valid_legacy_plan(self):
        plan = parse_lines(["SYNAPSE/1", "profile pulse", "cosmos probe", "service check NetworkManager"])
        self.assertEqual([x.op for x in plan], ["profile", "cosmos", "service"])

    def test_missing_header(self):
        with self.assertRaises(ValueError):
            parse_lines(["profile pulse"])

    def test_arbitrary_shell_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_lines(["SYNAPSE/1", "exec echo hello"])

    def test_service_injection_rejected(self):
        with self.assertRaises(ValueError):
            parse_lines(["SYNAPSE/1", "service check foo;bar"])

    def test_state_math_and_repeat(self):
        program = parse_lines([
            "SYNAPSE/1", "state x = 2", "repeat 3", "set x = x * 2", "end",
            "assert x == 16", "emit x + phi",
        ])
        out = apply(program)
        self.assertAlmostEqual(out[-1]["emit"], 16 + (1 + 5 ** 0.5) / 2)

    def test_if_else(self):
        program = parse_lines([
            "SYNAPSE/1", "let x = 3", "if x > 4", "emit 'big'", "else",
            "emit 'small'", "end",
        ])
        self.assertEqual(apply(program)[0]["emit"], "small")

    def test_function_call(self):
        program = parse_lines([
            "SYNAPSE/1", "fn twice(v)", "emit v * 2", "end", "call twice(21)",
        ])
        self.assertEqual(apply(program)[0]["emit"], 42)

    def test_math_helpers(self):
        program = parse_lines([
            "SYNAPSE/1", "emit round(mean([2, 4, 6]), 2)",
            "emit clamp(12, 0, 10)", "emit round(sqrt(81) + cos(0), 2)",
        ])
        self.assertEqual([x["emit"] for x in apply(program)], [4.0, 10, 10.0])

    def test_import_escape_is_rejected(self):
        program = parse_lines(["SYNAPSE/1", "emit __import__('os')"])
        with self.assertRaises(FlowError):
            apply(program)

    def test_attribute_access_is_rejected(self):
        program = parse_lines(["SYNAPSE/1", "emit (1).__class__"])
        with self.assertRaises(FlowError):
            apply(program)

    def test_repeat_is_bounded(self):
        program = parse_lines(["SYNAPSE/1", "repeat 10001", "emit 1", "end"])
        with self.assertRaises(FlowError):
            Runtime().run(program)

    def test_module_use(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "math.syn").write_text("SYNAPSE/1\nlet base = 40\n")
            (root / "main.syn").write_text("SYNAPSE/1\nuse math.syn\nset base = base + 2\nemit base\n")
            self.assertEqual(Runtime().run(parse_file(root / "main.syn"))[-1]["emit"], 42)

    def test_module_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "program"
            root.mkdir()
            (Path(d) / "outside.syn").write_text("SYNAPSE/1\nemit 1\n")
            (root / "main.syn").write_text("SYNAPSE/1\nuse ../outside.syn\n")
            with self.assertRaises(FlowError):
                parse_file(root / "main.syn")

    def test_module_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.syn").write_text("SYNAPSE/1\nuse b.syn\n")
            (root / "b.syn").write_text("SYNAPSE/1\nuse a.syn\n")
            with self.assertRaises(FlowError):
                parse_file(root / "a.syn")


if __name__ == "__main__":
    unittest.main()
