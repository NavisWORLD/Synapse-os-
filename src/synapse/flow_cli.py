from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
from .debugger import Debugger
from .flow import BytecodeModule, FlowError, RuntimeCapabilities, TypeChecker, VM, compile_file, disassemble, parse_file
from .packages import Manifest, PackageError, RegistryClient


def _module(path:str)->BytecodeModule:
    p=Path(path); return BytecodeModule.from_bytes(p.read_bytes()) if p.suffix==".synb" else compile_file(p)

def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="synflow",description="Synapse Flow v2 compiler, VM and developer tools")
    sub=p.add_subparsers(dest="cmd",required=True)
    c=sub.add_parser("check");c.add_argument("source")
    c=sub.add_parser("compile");c.add_argument("source");c.add_argument("-o","--output");c.add_argument("--no-opt",action="store_true")
    c=sub.add_parser("run");c.add_argument("program");c.add_argument("--net",action="store_true");c.add_argument("--allow-host",action="append",default=[])
    c=sub.add_parser("disasm");c.add_argument("program")
    c=sub.add_parser("debug");c.add_argument("program");c.add_argument("--break-line",action="append",type=int,default=[])
    c=sub.add_parser("pkg-check");c.add_argument("manifest",nargs="?",default="synapse.toml")
    c=sub.add_parser("pkg-resolve");c.add_argument("registry");c.add_argument("name");c.add_argument("--version")
    c=sub.add_parser("pkg-install");c.add_argument("registry");c.add_argument("name");c.add_argument("--version")
    sub.add_parser("lsp");return p

def main(argv:list[str]|None=None)->int:
    args=parser().parse_args(argv)
    try:
        if args.cmd=="check":print(json.dumps(TypeChecker(parse_file(args.source)).check(),indent=2,sort_keys=True))
        elif args.cmd=="compile":
            mod=compile_file(args.source,optimize=not args.no_opt);out=Path(args.output or str(Path(args.source).with_suffix(".synb")));out.write_bytes(mod.to_bytes());print(out)
        elif args.cmd=="run":
            if args.net and not args.allow_host: raise FlowError("--net requires at least one --allow-host grant")
            result=VM(_module(args.program),RuntimeCapabilities(network=args.net,allowed_hosts=frozenset(args.allow_host))).run();print(json.dumps(result,indent=2,sort_keys=True))
        elif args.cmd=="disasm":print(disassemble(_module(args.program)))
        elif args.cmd=="debug":print(json.dumps(Debugger(_module(args.program),breakpoints=set(args.break_line)).run(),indent=2,sort_keys=True))
        elif args.cmd=="pkg-check":print(json.dumps(Manifest.load(args.manifest).__dict__,indent=2,sort_keys=True))
        elif args.cmd in {"pkg-resolve","pkg-install"}:
            client=RegistryClient(args.registry);spec=client.resolve(args.name,args.version)
            print(client.install(spec) if args.cmd=="pkg-install" else json.dumps(spec.__dict__,indent=2,sort_keys=True))
        elif args.cmd=="lsp":
            from .lsp import serve;return serve()
        return 0
    except (FlowError,PackageError,OSError) as exc:
        print(f"synflow: {exc}",file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
