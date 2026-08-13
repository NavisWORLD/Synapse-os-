# Synapse Flow (`.syn`)

Synapse Flow is the state-oriented language layer of Synapse OS.

Version 1 supports bindings and state, expressions and math helpers, conditional blocks, bounded repetition, named procedures, relative modules, structured output, assertions, and the original Synapse OS control statements.

Every program begins with:

```text
SYNAPSE/1
```

Example:

```text
SYNAPSE/1
state coherence = 0.4
let gain = phi
repeat 4
    set coherence = clamp(coherence + 0.1 * gain, 0, 1)
end
emit round(coherence, 4)
```

Existing programs using `profile`, `cosmos probe`, and `service check` remain compatible.

See `V1.md` for the quickstart and `SPEC.md` for the complete v1 contract.
