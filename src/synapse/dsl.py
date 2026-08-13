from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import operator
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Iterable

from .core import cosmos_probe, set_profile

ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SERVICE = re.compile(r"^[A-Za-z0-9@_.-]+$")
RESERVED = {"true", "false", "none", "pi", "tau", "e", "phi"}
PROFILES = {"pulse", "balanced", "quiet", "auto"}
MAX_EXPR = 2048
MAX_ITEMS = 256
MAX_STEPS = 100_000
MAX_REPEAT = 10_000
MAX_CALL_DEPTH = 32
MAX_MODULE_DEPTH = 16


@dataclass(frozen=True)
class Statement:
    op: str
    args: tuple[str, ...]
    line: int
    body: tuple["Statement", ...] = ()
    else_body: tuple["Statement", ...] = ()


Instruction = Statement  # compatibility with Synapse Flow 0.x callers


class FlowError(ValueError):
    pass


def _ident(name: str, line: int, kind: str = "identifier") -> str:
    if not ID.fullmatch(name) or name.lower() in RESERVED:
        raise FlowError(f"line {line}: invalid {kind}: {name}")
    return name


def _mean(values: Any) -> float:
    seq = list(values)
    if not seq or len(seq) > MAX_ITEMS:
        raise FlowError("mean() requires 1..256 values")
    return sum(float(v) for v in seq) / len(seq)


def _clamp(value: Any, low: Any, high: Any) -> Any:
    if low > high:
        raise FlowError("clamp() low must be <= high")
    return max(low, min(high, value))


PURE = {
    "abs": abs, "bool": bool, "clamp": _clamp, "float": float,
    "int": int, "len": len, "max": max, "mean": _mean, "min": min,
    "round": round, "str": str, "sqrt": math.sqrt, "sin": math.sin,
    "cos": math.cos, "tanh": math.tanh, "log": math.log,
}
CONSTANTS = {
    "true": True, "false": False, "none": None, "pi": math.pi,
    "tau": math.tau, "e": math.e, "phi": (1 + math.sqrt(5)) / 2,
}
BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}
CMP = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}


class SafeExpression:
    """Pure expression evaluator: no attributes, imports, I/O, network, or shell."""

    def __init__(self, variables: dict[str, Any]):
        self.variables = variables

    def evaluate(self, source: str) -> Any:
        if len(source) > MAX_EXPR:
            raise FlowError("expression too long")
        try:
            return self.node(ast.parse(source, mode="eval").body)
        except SyntaxError as exc:
            raise FlowError("invalid expression") from exc

    def node(self, n: ast.AST) -> Any:
        if isinstance(n, ast.Constant) and isinstance(n.value, (str, int, float, bool, type(None))):
            return n.value
        if isinstance(n, ast.Name):
            key = n.id.lower()
            if key in CONSTANTS:
                return CONSTANTS[key]
            if n.id in self.variables:
                return self.variables[n.id]
            raise FlowError(f"unknown name: {n.id}")
        if isinstance(n, (ast.List, ast.Tuple)):
            if len(n.elts) > MAX_ITEMS:
                raise FlowError("container literal too large")
            values = [self.node(x) for x in n.elts]
            return values if isinstance(n, ast.List) else tuple(values)
        if isinstance(n, ast.Dict):
            if len(n.keys) > MAX_ITEMS:
                raise FlowError("container literal too large")
            return {self.node(k): self.node(v) for k, v in zip(n.keys, n.values) if k is not None}
        if isinstance(n, ast.Subscript):
            target, index = self.node(n.value), self.node(n.slice)
            if not isinstance(target, (list, tuple, dict, str)):
                raise FlowError("invalid subscript target")
            return target[index]
        if isinstance(n, ast.UnaryOp):
            value = self.node(n.operand)
            if isinstance(n.op, ast.Not): return not value
            if isinstance(n.op, ast.USub): return -value
            if isinstance(n.op, ast.UAdd): return +value
        if isinstance(n, ast.BinOp):
            left, right = self.node(n.left), self.node(n.right)
            if isinstance(n.op, ast.Pow):
                if not isinstance(right, (int, float)) or abs(right) > 16:
                    raise FlowError("power exponent outside safe range")
                return left ** right
            fn = BIN.get(type(n.op))
            if fn:
                return fn(left, right)
        if isinstance(n, ast.BoolOp):
            if isinstance(n.op, ast.And):
                result: Any = True
                for value in n.values:
                    result = self.node(value)
                    if not result: return result
                return result
            if isinstance(n.op, ast.Or):
                result = False
                for value in n.values:
                    result = self.node(value)
                    if result: return result
                return result
        if isinstance(n, ast.Compare):
            left = self.node(n.left)
            for op, raw in zip(n.ops, n.comparators):
                right = self.node(raw)
                fn = CMP.get(type(op))
                if fn is None or not fn(left, right): return False
                left = right
            return True
        if isinstance(n, ast.IfExp):
            return self.node(n.body if self.node(n.test) else n.orelse)
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name) or n.keywords or n.func.id not in PURE:
                raise FlowError("function not allowed in expression")
            try:
                return PURE[n.func.id](*(self.node(x) for x in n.args))
            except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
                raise FlowError(f"{n.func.id}(): {exc}") from exc
        raise FlowError(f"expression node not allowed: {type(n).__name__}")


class Parser:
    def __init__(self, lines: Iterable[str]):
        self.lines = [(n, s.strip()) for n, s in enumerate(lines, 1) if s.strip() and not s.strip().startswith("#")]
        self.i = 0

    def parse(self) -> list[Statement]:
        if not self.lines:
            raise FlowError("missing SYNAPSE/1 header")
        line, text = self.lines[0]
        if text != "SYNAPSE/1":
            raise FlowError(f"line {line}: expected SYNAPSE/1 header")
        self.i = 1
        body, stop = self.block(set())
        if stop:
            line, text = self.lines[self.i]
            raise FlowError(f"line {line}: unexpected {text}")
        return body

    def block(self, stops: set[str]) -> tuple[list[Statement], str | None]:
        out: list[Statement] = []
        while self.i < len(self.lines):
            line, text = self.lines[self.i]
            low = text.lower()
            if low in stops or low in {"else", "end"}:
                return out, low
            if low.startswith("if "):
                expr = self.expr(text[3:], line); self.i += 1
                body, stop = self.block({"else", "end"}); other: list[Statement] = []
                if stop == "else":
                    self.i += 1; other, stop = self.block({"end"})
                if stop != "end": raise FlowError(f"line {line}: if block missing end")
                self.i += 1; out.append(Statement("if", (expr,), line, tuple(body), tuple(other))); continue
            if low.startswith("repeat "):
                expr = self.expr(text[7:], line); self.i += 1
                body, stop = self.block({"end"})
                if stop != "end": raise FlowError(f"line {line}: repeat block missing end")
                self.i += 1; out.append(Statement("repeat", (expr,), line, tuple(body))); continue
            if low.startswith("fn "):
                m = re.fullmatch(r"fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", text, re.I)
                if not m: raise FlowError(f"line {line}: invalid function declaration")
                name = _ident(m.group(1), line, "function name"); params: list[str] = []
                for raw in filter(None, (x.strip() for x in m.group(2).split(","))):
                    p = _ident(raw, line, "parameter")
                    if p in params: raise FlowError(f"line {line}: duplicate parameter: {p}")
                    params.append(p)
                self.i += 1; body, stop = self.block({"end"})
                if stop != "end": raise FlowError(f"line {line}: function block missing end")
                self.i += 1; out.append(Statement("fn", (name, *params), line, tuple(body))); continue
            out.append(self.simple(text, line)); self.i += 1
        return out, None

    def simple(self, text: str, line: int) -> Statement:
        for op in ("let", "state", "set"):
            m = re.fullmatch(rf"{op}\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", text, re.I)
            if m: return Statement(op, (_ident(m.group(1), line), self.expr(m.group(2), line)), line)
        low = text.lower()
        if low.startswith("emit "): return Statement("emit", (self.expr(text[5:], line),), line)
        if low.startswith("assert "): return Statement("assert", (self.expr(text[7:], line),), line)
        if low.startswith("call "):
            source = text[5:].strip(); self.call(source, line); return Statement("call", (source,), line)
        if low.startswith("use "):
            try: parts = shlex.split(text)
            except ValueError as exc: raise FlowError(f"line {line}: invalid use path") from exc
            if len(parts) != 2: raise FlowError(f"line {line}: use expects one .syn path")
            return Statement("use", (parts[1],), line)
        try: parts = shlex.split(text)
        except ValueError as exc: raise FlowError(f"line {line}: invalid instruction") from exc
        if len(parts) == 2 and parts[0].lower() == "profile" and parts[1].lower() in PROFILES:
            return Statement("profile", (parts[1].lower(),), line)
        if [x.lower() for x in parts] == ["cosmos", "probe"]:
            return Statement("cosmos", ("probe",), line)
        if len(parts) == 3 and [x.lower() for x in parts[:2]] == ["service", "check"]:
            if not SERVICE.fullmatch(parts[2]): raise FlowError(f"line {line}: invalid service name")
            return Statement("service", ("check", parts[2]), line)
        raise FlowError(f"line {line}: unsupported instruction: {text}")

    @staticmethod
    def expr(source: str, line: int) -> str:
        source = source.strip()
        if not source or len(source) > MAX_EXPR: raise FlowError(f"line {line}: invalid expression")
        try: ast.parse(source, mode="eval")
        except SyntaxError as exc: raise FlowError(f"line {line}: invalid expression") from exc
        return source

    @staticmethod
    def call(source: str, line: int) -> ast.Call:
        try: n = ast.parse(source, mode="eval").body
        except SyntaxError as exc: raise FlowError(f"line {line}: invalid call") from exc
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Name) or n.keywords:
            raise FlowError(f"line {line}: call expects name(...)")
        _ident(n.func.id, line, "function name"); return n


def parse_lines(lines: Iterable[str]) -> list[Statement]:
    return Parser(lines).parse()


def _modules(nodes: list[Statement], current: Path, root: Path, stack: tuple[Path, ...], depth: int) -> list[Statement]:
    if depth > MAX_MODULE_DEPTH: raise FlowError("module nesting limit exceeded")
    out: list[Statement] = []
    for n in nodes:
        if n.op == "use":
            rel = Path(n.args[0])
            if rel.is_absolute() or rel.suffix != ".syn": raise FlowError(f"line {n.line}: module path must be relative .syn")
            target = (current.parent / rel).resolve()
            try: target.relative_to(root)
            except ValueError as exc: raise FlowError(f"line {n.line}: module path escapes program root") from exc
            if target in stack: raise FlowError("module cycle: " + " -> ".join(p.name for p in (*stack, target)))
            if not target.is_file(): raise FlowError(f"line {n.line}: module not found: {rel}")
            out += _modules(parse_lines(target.read_text().splitlines()), target, root, (*stack, target), depth + 1)
        else:
            out.append(Statement(n.op, n.args, n.line, tuple(_modules(list(n.body), current, root, stack, depth)), tuple(_modules(list(n.else_body), current, root, stack, depth))))
    return out


def parse_file(path: str | Path) -> list[Statement]:
    source = Path(path).resolve()
    if not source.is_file(): raise FlowError(f"program not found: {source}")
    if source.suffix != ".syn": raise FlowError("Synapse Flow programs must use .syn")
    return _modules(parse_lines(source.read_text().splitlines()), source, source.parent, (source,), 0)


class Runtime:
    def __init__(self, *, max_steps: int = MAX_STEPS, max_repeat: int = MAX_REPEAT, max_call_depth: int = MAX_CALL_DEPTH):
        self.variables: dict[str, Any] = {}
        self.state_names: set[str] = set()
        self.functions: dict[str, Statement] = {}
        self.results: list[dict[str, Any]] = []
        self.max_steps, self.max_repeat, self.max_call_depth = max_steps, max_repeat, max_call_depth
        self.steps = self.call_depth = 0

    def run(self, nodes: list[Statement]) -> list[dict[str, Any]]:
        self.execute(nodes); return self.results

    def value(self, source: str, line: int) -> Any:
        try: return SafeExpression(self.variables).evaluate(source)
        except FlowError as exc: raise FlowError(f"line {line}: {exc}") from exc
        except (TypeError, ValueError, ZeroDivisionError, KeyError, IndexError) as exc: raise FlowError(f"line {line}: expression failed: {exc}") from exc

    def execute(self, nodes: Iterable[Statement]) -> None:
        for n in nodes:
            self.steps += 1
            if self.steps > self.max_steps: raise FlowError(f"line {n.line}: execution step limit exceeded")
            if n.op in {"let", "state"}:
                name, expr = n.args
                if name in self.variables: raise FlowError(f"line {n.line}: name already defined: {name}")
                self.variables[name] = self.value(expr, n.line)
                if n.op == "state": self.state_names.add(name)
            elif n.op == "set":
                name, expr = n.args
                if name not in self.variables: raise FlowError(f"line {n.line}: cannot set undefined name: {name}")
                self.variables[name] = self.value(expr, n.line)
            elif n.op == "emit": self.results.append({"line": n.line, "emit": self.value(n.args[0], n.line)})
            elif n.op == "assert":
                if not self.value(n.args[0], n.line): raise FlowError(f"line {n.line}: assertion failed: {n.args[0]}")
                self.results.append({"line": n.line, "assert": True})
            elif n.op == "if": self.execute(n.body if self.value(n.args[0], n.line) else n.else_body)
            elif n.op == "repeat":
                count = self.value(n.args[0], n.line)
                if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= self.max_repeat:
                    raise FlowError(f"line {n.line}: repeat count must be 0..{self.max_repeat}")
                for _ in range(count): self.execute(n.body)
            elif n.op == "fn":
                if n.args[0] in self.functions: raise FlowError(f"line {n.line}: function already defined: {n.args[0]}")
                self.functions[n.args[0]] = n
            elif n.op == "call": self.call(n.args[0], n.line)
            elif n.op == "profile": self.results.append({"line": n.line, "profile": set_profile(n.args[0])})
            elif n.op == "cosmos": self.results.append({"line": n.line, "cosmos": cosmos_probe()})
            elif n.op == "service": self.service(n)
            elif n.op == "use": raise FlowError(f"line {n.line}: use requires parse_file()")
            else: raise FlowError(f"line {n.line}: unsupported runtime operation: {n.op}")

    def service(self, n: Statement) -> None:
        name = n.args[1]
        if not SERVICE.fullmatch(name): raise FlowError(f"line {n.line}: invalid service name")
        try: p = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, check=False, timeout=2)
        except (OSError, subprocess.TimeoutExpired) as exc: raise FlowError(f"line {n.line}: service check failed: {exc}") from exc
        self.results.append({"line": n.line, "service": name, "active": p.returncode == 0, "detail": (p.stdout or p.stderr).strip()})

    def call(self, source: str, line: int) -> None:
        node = Parser.call(source, line); fn = self.functions.get(node.func.id)
        if fn is None: raise FlowError(f"line {line}: unknown function: {node.func.id}")
        params = fn.args[1:]
        if len(node.args) != len(params): raise FlowError(f"line {line}: {node.func.id} expects {len(params)} argument(s)")
        if self.call_depth >= self.max_call_depth: raise FlowError(f"line {line}: function call depth limit exceeded")
        ev = SafeExpression(self.variables); values = [ev.node(x) for x in node.args]
        old = {p: (p in self.variables, self.variables.get(p)) for p in params}
        for p, v in zip(params, values): self.variables[p] = v
        self.call_depth += 1
        try: self.execute(fn.body)
        finally:
            self.call_depth -= 1
            for p, (had, value) in old.items():
                if had: self.variables[p] = value
                else: self.variables.pop(p, None)


def apply(instructions: list[Statement]) -> list[dict[str, Any]]:
    return Runtime().run(instructions)


def run_file(path: str | Path) -> list[dict[str, Any]]:
    return Runtime().run(parse_file(path))


def check_file(path: str | Path) -> dict[str, Any]:
    nodes = parse_file(path); counts: dict[str, int] = {}
    def walk(items: Iterable[Statement]) -> None:
        for n in items:
            counts[n.op] = counts.get(n.op, 0) + 1; walk(n.body); walk(n.else_body)
    walk(nodes)
    return {"ok": True, "path": str(Path(path)), "statements": sum(counts.values()), "operations": dict(sorted(counts.items()))}


def repl() -> int:
    runtime = Runtime(); print("Synapse Flow v1 REPL. :vars, :quit")
    while True:
        try: raw = input("syn> ").strip()
        except EOFError: print(); return 0
        if not raw: continue
        if raw in {":q", ":quit", "quit", "exit"}: return 0
        if raw == ":vars": print(runtime.variables); continue
        if raw.lower().startswith(("if ", "repeat ", "fn ")):
            print("blocks belong in .syn files; REPL accepts single-line statements"); continue
        try:
            before = len(runtime.results); runtime.execute(parse_lines(["SYNAPSE/1", raw]))
            for result in runtime.results[before:]: print(result)
        except FlowError as exc: print(f"error: {exc}")
