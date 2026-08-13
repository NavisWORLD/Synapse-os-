from __future__ import annotations
import math, operator
from typing import Any, Callable
from .model import BytecodeModule, CodeObject, FlowError, MAX_CALL_DEPTH, MAX_STEPS, RuntimeCapabilities

class VM:
    def __init__(self,module:BytecodeModule,capabilities:RuntimeCapabilities|None=None,trace:Callable[[dict[str,Any]],None]|None=None):
        self.module=module; self.capabilities=capabilities or RuntimeCapabilities(); self.trace=trace; self.globals={}; self.output=[]; self.steps=0; self.call_depth=0
    def run(self)->dict[str,Any]:
        value=self.execute(self.module.globals,{},True); return {"return":value,"globals":dict(self.globals),"output":list(self.output),"steps":self.steps}
    def execute(self,code:CodeObject,locals_:dict[str,Any],is_global:bool=False)->Any:
        self.call_depth+=1
        if self.call_depth>MAX_CALL_DEPTH: raise FlowError("call depth limit exceeded")
        stack=[]; ip=0
        try:
            while ip<len(code.instructions):
                ins=code.instructions[ip]; self.steps+=1
                if self.steps>MAX_STEPS: raise FlowError(f"line {ins.line}: execution step limit exceeded")
                if self.trace:self.trace({"function":code.name,"ip":ip,"line":ins.line,"op":ins.op,"arg":ins.arg,"stack_depth":len(stack)})
                ip+=1; op=ins.op
                if op=="NOP":pass
                elif op=="CONST":stack.append(ins.arg)
                elif op=="LOAD":
                    if ins.arg in locals_:stack.append(locals_[ins.arg])
                    elif ins.arg in self.globals:stack.append(self.globals[ins.arg])
                    else:raise FlowError(f"line {ins.line}: unknown name {ins.arg}")
                elif op=="STORE":
                    value=stack.pop()
                    if is_global or ins.arg in self.globals:self.globals[ins.arg]=value
                    else:locals_[ins.arg]=value
                elif op=="POP":stack.pop()
                elif op in {"BUILD_LIST","BUILD_TUPLE"}:
                    n=int(ins.arg); vals=stack[-n:] if n else []
                    if n:del stack[-n:]
                    stack.append(list(vals) if op=="BUILD_LIST" else tuple(vals))
                elif op=="BUILD_MAP":
                    n=int(ins.arg); vals=stack[-2*n:] if n else []
                    if n:del stack[-2*n:]
                    stack.append({vals[i]:vals[i+1] for i in range(0,len(vals),2)})
                elif op=="SUBSCRIPT":idx=stack.pop(); target=stack.pop(); stack.append(target[idx])
                elif op=="UNARY":v=stack.pop(); stack.append(not v if ins.arg=="not" else -v if ins.arg=="neg" else +v)
                elif op=="BINARY":b,a=stack.pop(),stack.pop(); stack.append(self.binary(str(ins.arg),a,b,ins.line))
                elif op=="COMPARE":b,a=stack.pop(),stack.pop(); stack.append(self.compare(str(ins.arg),a,b))
                elif op=="BOOL_N":
                    count=int(ins.arg["count"]); vals=stack[-count:]; del stack[-count:]; stack.append(all(vals) if ins.arg["op"]=="and" else any(vals))
                elif op=="JUMP":ip=int(ins.arg)
                elif op=="JUMP_IF_FALSE":
                    if not stack.pop():ip=int(ins.arg)
                elif op in {"CALL_FUNC","CALL_BUILTIN"}:
                    argc=int(ins.arg["argc"]); args=stack[-argc:] if argc else []
                    if argc:del stack[-argc:]
                    stack.append(self.call_function(str(ins.arg["name"]),list(args)) if op=="CALL_FUNC" else self.call_builtin(str(ins.arg["name"]),list(args),ins.line))
                elif op=="EMIT":self.output.append(stack.pop())
                elif op=="ASSERT":
                    if not stack.pop():raise FlowError(f"line {ins.line}: assertion failed")
                elif op=="RETURN":return stack.pop() if stack else None
                else:raise FlowError(f"unknown opcode {op}")
        finally:self.call_depth-=1
        return None
    @staticmethod
    def binary(op:str,a:Any,b:Any,line:int)->Any:
        fns={"add":operator.add,"sub":operator.sub,"mul":operator.mul,"div":operator.truediv,"floordiv":operator.floordiv,"mod":operator.mod}
        if op=="pow":
            if not isinstance(b,(int,float)) or abs(b)>32:raise FlowError(f"line {line}: exponent outside safe range")
            return a**b
        try:return fns[op](a,b)
        except Exception as exc:raise FlowError(f"line {line}: binary operation failed: {exc}") from exc
    @staticmethod
    def compare(op:str,a:Any,b:Any)->bool:
        return {"eq":lambda:a==b,"ne":lambda:a!=b,"lt":lambda:a<b,"le":lambda:a<=b,"gt":lambda:a>b,"ge":lambda:a>=b,"in":lambda:a in b,"notin":lambda:a not in b}[op]()
    def call_function(self,name:str,args:list[Any])->Any:
        code=self.module.functions.get(name)
        if code is None:raise FlowError(f"unknown function {name}")
        if len(args)!=len(code.params):raise FlowError(f"{name} expects {len(code.params)} arguments")
        return self.execute(code,dict(zip(code.params,args)))
    def call_builtin(self,name:str,args:list[Any],line:int)->Any:
        pure={"abs":abs,"bool":bool,"float":float,"int":int,"len":len,"max":max,"min":min,"round":round,"str":str,"sqrt":math.sqrt,"sin":math.sin,"cos":math.cos,"tanh":math.tanh,"log":math.log,"mean":lambda x:sum(x)/len(x),"clamp":lambda v,lo,hi:max(lo,min(hi,v))}
        if name in pure:
            try:return pure[name](*args)
            except Exception as exc:raise FlowError(f"line {line}: {name} failed: {exc}") from exc
        from ..net import NetworkClient
        net=NetworkClient(self.capabilities)
        if name=="http_get":return net.get_text(str(args[0]))
        if name=="http_json":return net.get_json(str(args[0]))
        if name=="http_post_json":return net.post_json(str(args[0]),args[1])
        if name=="dns_lookup":return net.dns_lookup(str(args[0]))
        if name=="tcp_probe":return net.tcp_probe(str(args[0]),int(args[1]))
        if name=="ai_chat":return net.ai_chat(str(args[0]),str(args[1]),str(args[2]),str(args[3]))
        raise FlowError(f"line {line}: unknown builtin {name}")
