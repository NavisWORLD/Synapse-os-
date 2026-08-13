from __future__ import annotations
import ast, hashlib, re
from pathlib import Path
from typing import Iterable
from .model import Expr, FlowError, MAX_EXPR, Program, Stmt, TYPE_NAMES

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _ident(name: str, line: int) -> str:
    if not IDENT.fullmatch(name) or name.startswith("__"):
        raise FlowError(f"line {line}: invalid identifier {name}")
    return name

def _type(name: str, line: int) -> str:
    value = name.strip().lower()
    if value not in TYPE_NAMES:
        raise FlowError(f"line {line}: unknown type {name}")
    return value

class Parser:
    def __init__(self, lines: Iterable[str], source_name: str = "<memory>"):
        self.lines = [(n, s.strip()) for n, s in enumerate(lines, 1) if s.strip() and not s.strip().startswith("#")]
        self.i = 0
        self.source_name = source_name
    def parse(self) -> Program:
        if not self.lines: raise FlowError("missing SYNAPSE/2 header")
        line, text = self.lines[0]
        if text != "SYNAPSE/2": raise FlowError(f"line {line}: expected SYNAPSE/2 header")
        self.i = 1
        body, stop = self.block(set())
        if stop is not None:
            line, text = self.lines[self.i]; raise FlowError(f"line {line}: unexpected {text}")
        funcs, main = {}, []
        for st in body:
            if st.op == "fn":
                assert st.name
                if st.name in funcs: raise FlowError(f"line {st.line}: duplicate function {st.name}")
                funcs[st.name] = st
            else: main.append(st)
        raw = "\n".join(text for _, text in self.lines)
        return Program(main, funcs, self.source_name, hashlib.sha256(raw.encode()).hexdigest())
    def block(self, stops: set[str]) -> tuple[list[Stmt], str | None]:
        out = []
        while self.i < len(self.lines):
            line, text = self.lines[self.i]; low = text.lower()
            if low in stops or low in {"else", "end"}: return out, low
            if low.startswith("if "):
                expr = self.expr(text[3:], line); self.i += 1; body, stop = self.block({"else", "end"}); other = []
                if stop == "else": self.i += 1; other, stop = self.block({"end"})
                if stop != "end": raise FlowError(f"line {line}: if block missing end")
                self.i += 1; out.append(Stmt("if", line, expr=expr, body=tuple(body), else_body=tuple(other))); continue
            if low.startswith("while "):
                expr = self.expr(text[6:], line); self.i += 1; body, stop = self.block({"end"})
                if stop != "end": raise FlowError(f"line {line}: while block missing end")
                self.i += 1; out.append(Stmt("while", line, expr=expr, body=tuple(body))); continue
            if low.startswith("repeat "):
                expr = self.expr(text[7:], line); self.i += 1; body, stop = self.block({"end"})
                if stop != "end": raise FlowError(f"line {line}: repeat block missing end")
                self.i += 1; out.append(Stmt("repeat", line, expr=expr, body=tuple(body))); continue
            if low.startswith("fn "): out.append(self.function(text, line)); continue
            out.append(self.simple(text, line)); self.i += 1
        return out, None
    def function(self, text: str, line: int) -> Stmt:
        m = re.fullmatch(r"fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*->\s*([A-Za-z]+)", text, re.I)
        if not m: raise FlowError(f"line {line}: expected fn name(arg: type) -> type")
        name = _ident(m.group(1), line); params = []
        if m.group(2).strip():
            for part in m.group(2).split(","):
                pm = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z]+)\s*", part)
                if not pm: raise FlowError(f"line {line}: invalid parameter declaration")
                pname, ptype = _ident(pm.group(1), line), _type(pm.group(2), line)
                if any(pname == old for old, _ in params): raise FlowError(f"line {line}: duplicate parameter {pname}")
                params.append((pname, ptype))
        ret = _type(m.group(3), line); self.i += 1; body, stop = self.block({"end"})
        if stop != "end": raise FlowError(f"line {line}: function block missing end")
        self.i += 1; return Stmt("fn", line, name=name, params=tuple(params), return_type=ret, body=tuple(body))
    def simple(self, text: str, line: int) -> Stmt:
        for op in ("let", "state"):
            m = re.fullmatch(rf"{op}\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z]+)\s*=\s*(.+)", text, re.I)
            if m: return Stmt(op, line, name=_ident(m.group(1), line), type_name=_type(m.group(2), line), expr=self.expr(m.group(3), line))
        m = re.fullmatch(r"set\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", text, re.I)
        if m: return Stmt("set", line, name=_ident(m.group(1), line), expr=self.expr(m.group(2), line))
        low = text.lower()
        if low.startswith("return"):
            rest = text[6:].strip(); return Stmt("return", line, expr=self.expr(rest, line) if rest else None)
        if low.startswith("emit "): return Stmt("emit", line, expr=self.expr(text[5:], line))
        if low.startswith("assert "): return Stmt("assert", line, expr=self.expr(text[7:], line))
        if low == "break": return Stmt("break", line)
        if low == "continue": return Stmt("continue", line)
        return Stmt("expr", line, expr=self.expr(text, line))
    @staticmethod
    def expr(source: str, line: int) -> Expr:
        source = source.strip()
        if not source or len(source) > MAX_EXPR: raise FlowError(f"line {line}: invalid expression")
        try: ast.parse(source, mode="eval")
        except SyntaxError as exc: raise FlowError(f"line {line}: invalid expression") from exc
        return Expr(source, line)

def parse_lines(lines: Iterable[str], source_name: str = "<memory>") -> Program:
    return Parser(lines, source_name).parse()

def parse_file(path: str | Path) -> Program:
    p = Path(path).resolve()
    if p.suffix != ".syn" or not p.is_file(): raise FlowError("Synapse Flow v2 source must be an existing .syn file")
    return parse_lines(p.read_text(encoding="utf-8").splitlines(), str(p))
