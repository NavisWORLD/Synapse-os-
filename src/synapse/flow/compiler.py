from __future__ import annotations
import ast, math, operator
from pathlib import Path
from typing import Any, Callable, Iterable
from .model import BytecodeModule, CodeObject, Expr, FlowError, Instruction, Program, Stmt
from .parser import parse_file
from .types import TypeChecker

BIN_OPS = {ast.Add:"add", ast.Sub:"sub", ast.Mult:"mul", ast.Div:"div", ast.FloorDiv:"floordiv", ast.Mod:"mod", ast.Pow:"pow"}
CMP_OPS = {ast.Eq:"eq", ast.NotEq:"ne", ast.Lt:"lt", ast.LtE:"le", ast.Gt:"gt", ast.GtE:"ge", ast.In:"in", ast.NotIn:"notin"}

class Compiler:
    def __init__(self, program: Program):
        self.program = program; self.functions = set(program.functions); self.code = []; self.loop_stack = []; self.hidden = 0
    def compile(self, optimize: bool = True) -> BytecodeModule:
        types = TypeChecker(self.program).check()
        main = self.code_object("<main>", [], [], "none", self.program.body)
        funcs = {name:self.code_object(name, [n for n,_ in st.params], [t for _,t in st.params], st.return_type or "none", st.body) for name,st in self.program.functions.items()}
        if optimize:
            main.instructions = optimize_instructions(main.instructions)
            for code in funcs.values(): code.instructions = optimize_instructions(code.instructions)
        return BytecodeModule(self.program.source_name, self.program.source_hash, main, funcs, {"types":types})
    def code_object(self, name:str, params:list[str], param_types:list[str], return_type:str, body:Iterable[Stmt]) -> CodeObject:
        old_code, old_loops = self.code, self.loop_stack; self.code, self.loop_stack = [], []
        self.block(body)
        if not self.code or self.code[-1].op != "RETURN": self.emit("CONST",None); self.emit("RETURN")
        result = CodeObject(name, params, param_types, return_type, self.code); self.code, self.loop_stack = old_code, old_loops; return result
    def emit(self, op:str, arg:Any=None, line:int=0) -> int:
        self.code.append(Instruction(op,arg,line)); return len(self.code)-1
    def patch(self, idx:int, target:int) -> None:
        ins=self.code[idx]; self.code[idx]=Instruction(ins.op,target,ins.line)
    def block(self, body:Iterable[Stmt]) -> None:
        for st in body:
            if st.op in {"let","state","set"}: self.expr(st.expr); self.emit("STORE",st.name,st.line)
            elif st.op=="emit": self.expr(st.expr); self.emit("EMIT",line=st.line)
            elif st.op=="assert": self.expr(st.expr); self.emit("ASSERT",line=st.line)
            elif st.op=="expr": self.expr(st.expr); self.emit("POP",line=st.line)
            elif st.op=="return":
                self.emit("CONST",None,st.line) if st.expr is None else self.expr(st.expr); self.emit("RETURN",line=st.line)
            elif st.op=="if":
                self.expr(st.expr); jf=self.emit("JUMP_IF_FALSE",None,st.line); self.block(st.body)
                if st.else_body:
                    je=self.emit("JUMP",None,st.line); self.patch(jf,len(self.code)); self.block(st.else_body); self.patch(je,len(self.code))
                else: self.patch(jf,len(self.code))
            elif st.op=="while":
                start=len(self.code); self.expr(st.expr); jf=self.emit("JUMP_IF_FALSE",None,st.line); breaks=[]; cont=[]; self.loop_stack.append((start,breaks,cont)); self.block(st.body); self.emit("JUMP",start,st.line); end=len(self.code); self.patch(jf,end); [self.patch(i,end) for i in breaks]; [self.patch(i,start) for i in cont]; self.loop_stack.pop()
            elif st.op=="repeat":
                self.hidden+=1; counter=f"__repeat_{self.hidden}"; self.expr(st.expr); self.emit("STORE",counter,st.line); start=len(self.code); self.emit("LOAD",counter,st.line); self.emit("CONST",0,st.line); self.emit("COMPARE","gt",st.line); jf=self.emit("JUMP_IF_FALSE",None,st.line); breaks=[]; cont=[]; self.loop_stack.append((start,breaks,cont)); self.block(st.body); cont_target=len(self.code); self.emit("LOAD",counter,st.line); self.emit("CONST",1,st.line); self.emit("BINARY","sub",st.line); self.emit("STORE",counter,st.line); self.emit("JUMP",start,st.line); end=len(self.code); self.patch(jf,end); [self.patch(i,end) for i in breaks]; [self.patch(i,cont_target) for i in cont]; self.loop_stack.pop()
            elif st.op in {"break","continue"}:
                if not self.loop_stack: raise FlowError(f"line {st.line}: {st.op} outside loop")
                idx=self.emit("JUMP",None,st.line); self.loop_stack[-1][1 if st.op=="break" else 2].append(idx)
    def expr(self, expr:Expr|None) -> None:
        assert expr is not None; self.node(ast.parse(expr.source,mode="eval").body, expr.line)
    def node(self,node:ast.AST,line:int)->None:
        if isinstance(node,ast.Constant): self.emit("CONST",node.value,line); return
        if isinstance(node,ast.Name):
            const={"true":True,"false":False,"none":None,"pi":math.pi,"tau":math.tau,"e":math.e,"phi":(1+math.sqrt(5))/2}
            self.emit("CONST",const[node.id.lower()],line) if node.id.lower() in const else self.emit("LOAD",node.id,line); return
        if isinstance(node,(ast.List,ast.Tuple)):
            for x in node.elts:self.node(x,line)
            self.emit("BUILD_LIST" if isinstance(node,ast.List) else "BUILD_TUPLE",len(node.elts),line); return
        if isinstance(node,ast.Dict):
            for k,v in zip(node.keys,node.values):
                if k is None: raise FlowError(f"line {line}: map unpacking is not allowed")
                self.node(k,line); self.node(v,line)
            self.emit("BUILD_MAP",len(node.keys),line); return
        if isinstance(node,ast.Subscript): self.node(node.value,line); self.node(node.slice,line); self.emit("SUBSCRIPT",line=line); return
        if isinstance(node,ast.UnaryOp): self.node(node.operand,line); self.emit("UNARY","not" if isinstance(node.op,ast.Not) else "neg" if isinstance(node.op,ast.USub) else "pos",line); return
        if isinstance(node,ast.BinOp):
            self.node(node.left,line); self.node(node.right,line); op=BIN_OPS.get(type(node.op));
            if not op: raise FlowError(f"line {line}: unsupported binary operator")
            self.emit("BINARY",op,line); return
        if isinstance(node,ast.BoolOp):
            for x in node.values:self.node(x,line)
            self.emit("BOOL_N",{"op":"and" if isinstance(node.op,ast.And) else "or","count":len(node.values)},line); return
        if isinstance(node,ast.Compare):
            if len(node.ops)!=1: raise FlowError(f"line {line}: chained comparisons are not supported")
            self.node(node.left,line); self.node(node.comparators[0],line); self.emit("COMPARE",CMP_OPS[type(node.ops[0])],line); return
        if isinstance(node,ast.IfExp):
            self.node(node.test,line); jf=self.emit("JUMP_IF_FALSE",None,line); self.node(node.body,line); je=self.emit("JUMP",None,line); self.patch(jf,len(self.code)); self.node(node.orelse,line); self.patch(je,len(self.code)); return
        if isinstance(node,ast.Call):
            if not isinstance(node.func,ast.Name) or node.keywords: raise FlowError(f"line {line}: only direct calls are allowed")
            for arg in node.args:self.node(arg,line)
            name=node.func.id; self.emit("CALL_FUNC" if name in self.functions else "CALL_BUILTIN",{"name":name,"argc":len(node.args)},line); return
        raise FlowError(f"line {line}: expression node not compilable: {type(node).__name__}")

def optimize_instructions(code:list[Instruction])->list[Instruction]:
    fns:dict[str,Callable[[Any,Any],Any]]={"add":operator.add,"sub":operator.sub,"mul":operator.mul,"div":operator.truediv,"floordiv":operator.floordiv,"mod":operator.mod}
    out=list(code); i=0
    while i+2<len(out):
        a,b,op=out[i:i+3]
        if a.op==b.op=="CONST" and op.op=="BINARY" and op.arg in fns:
            try:value=fns[str(op.arg)](a.arg,b.arg)
            except Exception:i+=1;continue
            if isinstance(value,(type(None),bool,int,float,str)):
                out[i]=Instruction("CONST",value,a.line); out[i+1]=Instruction("NOP",None,b.line); out[i+2]=Instruction("NOP",None,op.line); i+=3;continue
        i+=1
    return out

def compile_program(program:Program,optimize:bool=True)->BytecodeModule:return Compiler(program).compile(optimize)
def compile_file(path:str|Path,optimize:bool=True)->BytecodeModule:return compile_program(parse_file(path),optimize)
def disassemble(module:BytecodeModule)->str:
    lines=[]
    for name,code in [("<main>",module.globals),*sorted(module.functions.items())]:
        lines.append(f"[{name}]"); lines.extend(f"{i:04d} L{ins.line:<4} {ins.op:<16} {ins.arg!r}" for i,ins in enumerate(code.instructions))
    return "\n".join(lines)
