# Synapse Flow v2 compiler track

Synapse Flow v2 now has two compiled execution targets:

1. `.synb` bytecode executed by the dedicated Synapse VM.
2. A C11 native backend for the statically typed scalar subset.

The native backend is intentionally narrower than bytecode. It accepts scalar `int`, `float`, `bool`, `str`, typed functions, returns, branching, loops, assertions, arithmetic, and supported math helpers. Dynamic containers, `any`, package/network builtins, and other bytecode-only features are rejected instead of silently changing semantics.

## Native command

```bash
synflow native program.syn -o program
./program
```

`synflow native` locates `cc`, `gcc`, or `clang`, emits C11 into an isolated temporary directory, compiles with optimization and warnings enabled, links `libm`, and returns a native executable. Use `--keep-c` to preserve the generated C next to the output for inspection.

The VM certification now requires the same typed smoke program to pass:

```text
SYNAPSE/2 source
    -> static type check
    -> .synb compile
    -> Synapse VM run
    -> C11 native compile
    -> native executable run
    -> SYNAPSE_VM_READY
```

Network access remains denied by default. Programs must receive an explicit network capability and destination-host permission from the launcher.
