from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "phone-bootstrap" / "FLASH_USB.html"


@unittest.skipUnless(shutil.which("node"), "Node.js not available for browser SHA-256 source-vector test")
class UsbFlashBrowserShaTests(unittest.TestCase):
    def _hash(self, updates: list[bytes]) -> str:
        source = HTML.read_text(encoding="utf-8")
        bytes_start = source.index("function bytesToHex")
        class_start = source.index("class IncrementalSHA256")
        class_end = source.index("async function sha256File", class_start)
        helper_end = source.index("\n\nclass IncrementalSHA256", bytes_start)
        js = source[bytes_start:helper_end] + "\n\n" + source[class_start:class_end]
        encoded_updates = ",".join(repr(chunk.decode("ascii")) for chunk in updates)
        js += f"""
const h = new IncrementalSHA256();
for (const part of [{encoded_updates}]) h.update(new TextEncoder().encode(part));
console.log(h.hex());
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sha-test.js"
            path.write_text(js, encoding="utf-8")
            proc = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout.strip()

    def test_empty_vector(self) -> None:
        self.assertEqual(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            self._hash([]),
        )

    def test_abc_vector(self) -> None:
        self.assertEqual(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            self._hash([b"abc"]),
        )

    def test_chunk_boundary_vector(self) -> None:
        self.assertEqual(
            "2816597888e4a0d3a36b82b83316ab32680eb8f00f8cd3b904d681246d285a0e",
            self._hash([b"a" * 63, b"a", b"a" * 36]),
        )


if __name__ == "__main__":
    unittest.main()
