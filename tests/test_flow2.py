from pathlib import Path
import tempfile
import unittest

from synapse.flow import BytecodeModule, FlowError, RuntimeCapabilities, TypeChecker, VM, compile_program, disassemble, parse_lines
from synapse.lsp import diagnostics
from synapse.net import NetworkError
from synapse.packages import Manifest

PROGRAM="""SYNAPSE/2
state coherence: float = 0.25
fn evolve(step: float) -> float
    return clamp(coherence + step * phi, 0.0, 1.0)
end
repeat 3
    set coherence = evolve(0.2)
end
if coherence > 0.5
    emit "awake"
else
    emit "quiet"
end
assert coherence <= 1.0
"""

class Flow2Tests(unittest.TestCase):
    def test_typecheck_compile_vm(self):
        program=parse_lines(PROGRAM.splitlines());info=TypeChecker(program).check();self.assertEqual(info["globals"]["coherence"],"float")
        result=VM(compile_program(program)).run();self.assertEqual(result["output"],["awake"]);self.assertGreater(result["globals"]["coherence"],0.5)
    def test_bytecode_roundtrip(self):
        module=compile_program(parse_lines(PROGRAM.splitlines()));restored=BytecodeModule.from_bytes(module.to_bytes());self.assertEqual(VM(restored).run()["output"],["awake"]);self.assertIn("CALL_FUNC",disassemble(restored))
    def test_return_type_error(self):
        bad='SYNAPSE/2\nfn nope(x: int) -> int\n return "wrong"\nend\n'
        with self.assertRaises(FlowError):TypeChecker(parse_lines(bad.splitlines())).check()
    def test_while_break_continue(self):
        src='SYNAPSE/2\nstate x: int = 0\nwhile x < 10\n set x = x + 1\n if x == 3\n  continue\n end\n if x == 5\n  break\n end\nend\nemit x\n'
        self.assertEqual(VM(compile_program(parse_lines(src.splitlines()))).run()["output"],[5])
    def test_network_disabled_by_default(self):
        src='SYNAPSE/2\nlet page: str = http_get("https://example.com")\nemit page\n';module=compile_program(parse_lines(src.splitlines()))
        with self.assertRaises(NetworkError):VM(module,RuntimeCapabilities(network=False)).run()
        with self.assertRaises(NetworkError):VM(module,RuntimeCapabilities(network=True)).run()
    def test_lsp_reports_type_error(self):
        items=diagnostics('SYNAPSE/2\nlet x: int = "oops"\n');self.assertEqual(len(items),1);self.assertIn("cannot assign str to int",items[0]["message"])
    def test_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"synapse.toml";p.write_text('[package]\nname="demo"\nversion="0.1.0"\nentry="main.syn"\n\n[dependencies]\nmath="1.0.0"\n')
            self.assertEqual(Manifest.load(p).dependencies["math"],"1.0.0")
    def test_attribute_access_rejected(self):
        with self.assertRaises(FlowError):TypeChecker(parse_lines('SYNAPSE/2\nlet x: any = (1).__class__\n'.splitlines())).check()

if __name__=="__main__":unittest.main()
