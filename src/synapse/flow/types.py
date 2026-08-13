from __future__ import annotations
import ast
from typing import Any, Iterable
from .model import Expr, FlowError, FunctionSig, MAX_CONTAINER, Program, Stmt

BUILTIN_TYPES: dict[str, tuple[tuple[str, ...], str]] = {
    "abs": (("any",), "any"), "bool": (("any",), "bool"),
    "clamp": (("any", "any", "any"), "any"), "float": (("any",), "float"),
    "int": (("any",), "int"), "len": (("any",), "int"),
    "max": (("any", "any"), "any"), "mean": (("list",), "float"),
    "min": (("any", "any"), "any"), "round": (("any",), "any"),
    "str": (("any",), "str"), "sqrt": (("any",), "float"),
    "sin": (("any",), "float"), "cos": (("any",), "float"),
    "tanh": (("any",), "float"), "log": (("any",), "float"),
    "http_get": (("str",), "str"), "http_json": (("str",), "any"),
    "http_post_json": (("str", "any"), "any"), "dns_lookup": (("str",), "list"),
    "tcp_probe": (("str", "int"), "bool"),
    "ai_chat": (("str", "str", "str", "str"), "str"),
}
CONSTANT_TYPES = {"true": "bool", "false": "bool", "none": "none", "pi": "float", "tau": "float", "e": "float", "phi": "float"}

def compatible(expected: str, actual: str) -> bool:
    return expected == "any" or actual == "any" or expected == actual or (expected == "float" and actual == "int")

class TypeChecker:
    def __init__(self, program: Program):
        self.program = program
        self.functions = {name: FunctionSig(name, st.params, st.return_type or "none") for name, st in program.functions.items()}
        self.global_types: dict[str, str] = {}
        self.state_names: set[str] = set()
        self.current_return = "none"
        self.loop_depth = 0
    def check(self) -> dict[str, Any]:
        self.block(self.program.body, self.global_types)
        for name, st in self.program.functions.items():
            env = dict(self.global_types); env.update(st.params)
            old = self.current_return; self.current_return = st.return_type or "none"
            self.block(st.body, env); self.current_return = old
            if (st.return_type or "none") != "none" and not self.contains_return(st.body):
                raise FlowError(f"line {st.line}: function {name} must return {st.return_type}")
        return {"globals": dict(self.global_types), "states": sorted(self.state_names),
                "functions": {k: {"params": list(v.params), "return": v.return_type} for k, v in self.functions.items()}}
    @staticmethod
    def contains_return(body: Iterable[Stmt]) -> bool:
        for st in body:
            if st.op == "return": return True
            if st.op == "if" and (TypeChecker.contains_return(st.body) or TypeChecker.contains_return(st.else_body)): return True
        return False
    def block(self, body: Iterable[Stmt], env: dict[str, str]) -> None:
        for st in body:
            if st.op in {"let", "state"}:
                assert st.name and st.type_name and st.expr
                if st.name in env: raise FlowError(f"line {st.line}: name already defined: {st.name}")
                actual = self.expr_type(st.expr, env)
                if not compatible(st.type_name, actual): raise FlowError(f"line {st.line}: cannot assign {actual} to {st.type_name}")
                env[st.name] = st.type_name
                if st.op == "state": self.state_names.add(st.name)
            elif st.op == "set":
                assert st.name and st.expr
                if st.name not in env: raise FlowError(f"line {st.line}: unknown name {st.name}")
                actual = self.expr_type(st.expr, env)
                if not compatible(env[st.name], actual): raise FlowError(f"line {st.line}: cannot assign {actual} to {env[st.name]}")
            elif st.op in {"emit", "expr"}:
                assert st.expr; self.expr_type(st.expr, env)
            elif st.op == "assert":
                assert st.expr
                if self.expr_type(st.expr, env) not in {"bool", "any"}: raise FlowError(f"line {st.line}: assert requires bool")
            elif st.op == "if":
                assert st.expr
                if self.expr_type(st.expr, env) not in {"bool", "any"}: raise FlowError(f"line {st.line}: if requires bool")
                self.block(st.body, dict(env)); self.block(st.else_body, dict(env))
            elif st.op in {"while", "repeat"}:
                assert st.expr
                actual = self.expr_type(st.expr, env); expected = {"bool", "any"} if st.op == "while" else {"int", "any"}
                if actual not in expected: raise FlowError(f"line {st.line}: {st.op} has wrong expression type")
                self.loop_depth += 1; self.block(st.body, dict(env)); self.loop_depth -= 1
            elif st.op in {"break", "continue"}:
                if self.loop_depth <= 0: raise FlowError(f"line {st.line}: {st.op} outside loop")
            elif st.op == "return":
                actual = "none" if st.expr is None else self.expr_type(st.expr, env)
                if not compatible(self.current_return, actual): raise FlowError(f"line {st.line}: return {actual}, expected {self.current_return}")
    def expr_type(self, expr: Expr, env: dict[str, str]) -> str:
        return self.node(ast.parse(expr.source, mode="eval").body, env, expr.line)
    def node(self, node: ast.AST, env: dict[str, str], line: int) -> str:
        if isinstance(node, ast.Constant):
            if node.value is None: return "none"
            if type(node.value) is bool: return "bool"
            if type(node.value) is int: return "int"
            if type(node.value) is float: return "float"
            if type(node.value) is str: return "str"
            raise FlowError(f"line {line}: unsupported literal")
        if isinstance(node, ast.Name):
            if node.id.lower() in CONSTANT_TYPES: return CONSTANT_TYPES[node.id.lower()]
            if node.id in env: return env[node.id]
            raise FlowError(f"line {line}: unknown name {node.id}")
        if isinstance(node, (ast.List, ast.Tuple)):
            if len(node.elts) > MAX_CONTAINER: raise FlowError(f"line {line}: container too large")
            for item in node.elts: self.node(item, env, line)
            return "list"
        if isinstance(node, ast.Dict):
            if len(node.keys) > MAX_CONTAINER: raise FlowError(f"line {line}: map too large")
            for k, v in zip(node.keys, node.values):
                if k is not None: self.node(k, env, line)
                self.node(v, env, line)
            return "map"
        if isinstance(node, ast.Subscript): self.node(node.value, env, line); self.node(node.slice, env, line); return "any"
        if isinstance(node, ast.UnaryOp):
            inner = self.node(node.operand, env, line)
            if isinstance(node.op, ast.Not): return "bool"
            if inner not in {"int", "float", "any"}: raise FlowError(f"line {line}: numeric unary operator expected")
            return inner
        if isinstance(node, ast.BinOp):
            a, b = self.node(node.left, env, line), self.node(node.right, env, line)
            if isinstance(node.op, ast.Add) and a == b == "str": return "str"
            if a not in {"int", "float", "any"} or b not in {"int", "float", "any"}: raise FlowError(f"line {line}: numeric operator requires numbers")
            if "any" in {a, b}: return "any"
            if isinstance(node.op, ast.Div): return "float"
            return "float" if "float" in {a, b} else "int"
        if isinstance(node, ast.BoolOp):
            for item in node.values: self.node(item, env, line)
            return "bool"
        if isinstance(node, ast.Compare):
            self.node(node.left, env, line)
            for item in node.comparators: self.node(item, env, line)
            return "bool"
        if isinstance(node, ast.IfExp):
            if self.node(node.test, env, line) not in {"bool", "any"}: raise FlowError(f"line {line}: conditional expression requires bool")
            a, b = self.node(node.body, env, line), self.node(node.orelse, env, line); return a if a == b else "any"
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords: raise FlowError(f"line {line}: only direct calls are allowed")
            name = node.func.id
            if name in self.functions:
                sig = self.functions[name]
                if len(node.args) != len(sig.params): raise FlowError(f"line {line}: {name} expects {len(sig.params)} arguments")
                for raw, (_, want) in zip(node.args, sig.params):
                    actual = self.node(raw, env, line)
                    if not compatible(want, actual): raise FlowError(f"line {line}: {name} expected {want}, got {actual}")
                return sig.return_type
            if name not in BUILTIN_TYPES: raise FlowError(f"line {line}: unknown function {name}")
            params, ret = BUILTIN_TYPES[name]
            if len(node.args) != len(params): raise FlowError(f"line {line}: {name} expects {len(params)} arguments")
            for raw, want in zip(node.args, params):
                actual = self.node(raw, env, line)
                if not compatible(want, actual): raise FlowError(f"line {line}: {name} expected {want}, got {actual}")
            return ret
        raise FlowError(f"line {line}: expression node not allowed: {type(node).__name__}")
