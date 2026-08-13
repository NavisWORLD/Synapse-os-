from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .core import cosmos_probe, set_profile


@dataclass(frozen=True)
class Instruction:
    op: str
    args: tuple[str, ...]
    line: int


def parse_lines(lines: Iterable[str]) -> list[Instruction]:
    instructions: list[Instruction] = []
    saw_header = False
    for lineno, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        if not saw_header:
            if text != "SYNAPSE/1":
                raise ValueError(f"line {lineno}: expected SYNAPSE/1 header")
            saw_header = True
            continue
        parts = text.split()
        op = parts[0].lower()
        args = tuple(parts[1:])
        if op == "profile" and len(args) == 1 and args[0] in {"pulse", "balanced", "quiet", "auto"}:
            instructions.append(Instruction(op, args, lineno))
        elif op == "cosmos" and args == ("probe",):
            instructions.append(Instruction(op, args, lineno))
        elif op == "service" and len(args) == 2 and args[0] == "check":
            name = args[1]
            if not all(c.isalnum() or c in "@_.-" for c in name):
                raise ValueError(f"line {lineno}: invalid service name")
            instructions.append(Instruction(op, args, lineno))
        else:
            raise ValueError(f"line {lineno}: unsupported instruction: {text}")
    if not saw_header:
        raise ValueError("missing SYNAPSE/1 header")
    return instructions


def parse_file(path: str | Path) -> list[Instruction]:
    return parse_lines(Path(path).read_text().splitlines())


def apply(instructions: list[Instruction]) -> list[dict]:
    import subprocess

    results = []
    for item in instructions:
        if item.op == "profile":
            results.append({"line": item.line, "profile": set_profile(item.args[0])})
        elif item.op == "cosmos":
            results.append({"line": item.line, "cosmos": cosmos_probe()})
        elif item.op == "service":
            name = item.args[1]
            p = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, check=False, timeout=2)
            results.append({"line": item.line, "service": name, "active": p.returncode == 0, "detail": (p.stdout or p.stderr).strip()})
    return results
