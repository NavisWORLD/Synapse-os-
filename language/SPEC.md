# Synapse Flow v1 Specification

Synapse Flow is the state-oriented language layer of Synapse OS. Source files use `.syn` and begin with `SYNAPSE/1`.

## Core statements

```text
let name = expression
state name = expression
set name = expression
emit expression
assert expression

if expression
    ...
else
    ...
end

repeat expression
    ...
end

fn name(a, b)
    ...
end
call name(1, 2)

use helpers.syn
```

The original workstation operations remain compatible:

```text
profile pulse
profile balanced
profile quiet
profile auto
cosmos probe
service check NetworkManager
```

## Expressions

v1 supports numbers, strings, booleans, `none`, lists, tuples, dictionaries, indexing, arithmetic, comparisons, boolean logic, and conditional expressions.

Constants:

```text
true false none pi tau e phi
```

Pure functions:

```text
abs bool clamp float int len max mean min round str sqrt sin cos tanh log
```

`phi` is `(1 + sqrt(5)) / 2`.

## Determinism and bounds

A run is capped at 100,000 executed statements. `repeat` accepts integer counts from 0 through 10,000. Function calls are capped at 32 nested levels. Module nesting is capped at 16 levels.

## Modules

`use path.syn` resolves relative to the current program. Imported files must stay beneath the entry program directory. Absolute paths, missing modules, cycles, and paths that escape that root are rejected.

## Safety boundary

Expressions are evaluated by an allowlisted AST interpreter. Attribute access, arbitrary function calls, and import syntax are not accepted by the expression runtime. OS-facing statements are explicit: profile selection, localhost COSMOS probing, and validated `systemctl is-active` service checks.

Synapse Flow is therefore a bounded domain-specific language, not a general shell replacement.

## Compatibility

Existing programs such as the following remain valid:

```text
SYNAPSE/1
profile pulse
cosmos probe
service check NetworkManager
```

The Python API retains `Instruction` as an alias of the v1 `Statement` node for earlier callers.
