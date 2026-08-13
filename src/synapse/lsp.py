from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO
from .flow import Flow2Error, TypeChecker, parse_lines


def diagnostics(text: str, source_name: str = "<editor>") -> list[dict[str, Any]]:
    try:
        program = parse_lines(text.splitlines(), source_name)
        TypeChecker(program).check()
        return []
    except Flow2Error as exc:
        message = str(exc)
        line_no = 1
        if message.startswith("line "):
            try:
                line_no = int(message.split(":", 1)[0].split()[1])
            except (ValueError, IndexError):
                pass
        return [{
            "range": {"start": {"line": max(0, line_no - 1), "character": 0}, "end": {"line": max(0, line_no - 1), "character": 999}},
            "severity": 1,
            "source": "synapse-flow",
            "message": message,
        }]


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        key, _, value = line.decode("ascii", errors="replace").partition(":")
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0 or length > 10_000_000:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def _write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    stream.flush()


def serve(inp: BinaryIO | None = None, out: BinaryIO | None = None) -> int:
    inp = inp or sys.stdin.buffer
    out = out or sys.stdout.buffer
    docs: dict[str, str] = {}
    while True:
        msg = _read_message(inp)
        if msg is None:
            return 0
        method = msg.get("method")
        ident = msg.get("id")
        params = msg.get("params", {})
        if method == "initialize":
            _write_message(out, {"jsonrpc": "2.0", "id": ident, "result": {"capabilities": {"textDocumentSync": 1}}})
        elif method == "shutdown":
            _write_message(out, {"jsonrpc": "2.0", "id": ident, "result": None})
        elif method == "exit":
            return 0
        elif method in {"textDocument/didOpen", "textDocument/didChange"}:
            td = params.get("textDocument", {})
            uri = td.get("uri", "")
            if method == "textDocument/didOpen":
                text = td.get("text", "")
            else:
                changes = params.get("contentChanges", [])
                text = changes[-1].get("text", docs.get(uri, "")) if changes else docs.get(uri, "")
            docs[uri] = text
            _write_message(out, {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": diagnostics(text, uri)}})
        elif ident is not None:
            _write_message(out, {"jsonrpc": "2.0", "id": ident, "result": None})
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
