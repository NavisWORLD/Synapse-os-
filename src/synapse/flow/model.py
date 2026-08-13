from __future__ import annotations
from dataclasses import dataclass, field
import json
from typing import Any

MAGIC = b"SYB2\n"
BYTECODE_VERSION = 2
MAX_STEPS = 250_000
MAX_CALL_DEPTH = 64
MAX_EXPR = 4096
MAX_CONTAINER = 1024
TYPE_NAMES = {"int", "float", "bool", "str", "none", "any", "list", "map"}

class FlowError(ValueError):
    pass

@dataclass(frozen=True)
class Expr:
    source: str
    line: int

@dataclass(frozen=True)
class Stmt:
    op: str
    line: int
    name: str | None = None
    type_name: str | None = None
    expr: Expr | None = None
    body: tuple["Stmt", ...] = ()
    else_body: tuple["Stmt", ...] = ()
    params: tuple[tuple[str, str], ...] = ()
    return_type: str | None = None

@dataclass
class Program:
    body: list[Stmt]
    functions: dict[str, Stmt]
    source_name: str = "<memory>"
    source_hash: str = ""

@dataclass(frozen=True)
class FunctionSig:
    name: str
    params: tuple[tuple[str, str], ...]
    return_type: str

@dataclass(frozen=True)
class Instruction:
    op: str
    arg: Any = None
    line: int = 0
    def as_json(self) -> dict[str, Any]:
        return {"op": self.op, "arg": self.arg, "line": self.line}
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Instruction":
        return cls(str(data["op"]), data.get("arg"), int(data.get("line", 0)))

@dataclass
class CodeObject:
    name: str
    params: list[str]
    param_types: list[str]
    return_type: str
    instructions: list[Instruction]
    def as_json(self) -> dict[str, Any]:
        return {"name": self.name, "params": self.params, "param_types": self.param_types,
                "return_type": self.return_type, "instructions": [x.as_json() for x in self.instructions]}
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CodeObject":
        return cls(str(data["name"]), [str(x) for x in data.get("params", [])],
                   [str(x) for x in data.get("param_types", [])], str(data.get("return_type", "none")),
                   [Instruction.from_json(x) for x in data.get("instructions", [])])

@dataclass
class BytecodeModule:
    source_name: str
    source_hash: str
    globals: CodeObject
    functions: dict[str, CodeObject]
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_bytes(self) -> bytes:
        payload = {"bytecode_version": BYTECODE_VERSION, "source_name": self.source_name,
                   "source_hash": self.source_hash, "globals": self.globals.as_json(),
                   "functions": {k: v.as_json() for k, v in sorted(self.functions.items())},
                   "metadata": self.metadata}
        return MAGIC + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    @classmethod
    def from_bytes(cls, data: bytes) -> "BytecodeModule":
        if not data.startswith(MAGIC):
            raise FlowError("not Synapse Flow v2 bytecode")
        try:
            payload = json.loads(data[len(MAGIC):].decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FlowError("invalid Synapse bytecode payload") from exc
        if payload.get("bytecode_version") != BYTECODE_VERSION:
            raise FlowError("unsupported Synapse bytecode version")
        return cls(str(payload.get("source_name", "<bytecode>")), str(payload.get("source_hash", "")),
                   CodeObject.from_json(payload["globals"]),
                   {k: CodeObject.from_json(v) for k, v in payload.get("functions", {}).items()},
                   dict(payload.get("metadata", {})))

@dataclass(frozen=True)
class RuntimeCapabilities:
    network: bool = False
    allowed_hosts: frozenset[str] = frozenset()
    timeout_seconds: float = 8.0
    max_response_bytes: int = 2_000_000
