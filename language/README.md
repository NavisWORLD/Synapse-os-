# Synapse Flow (`.syn`)

Synapse Flow is a deliberately small declarative language for expressing safe workstation intent.

## Version 1 grammar

```text
file        := "SYNAPSE/1" NEWLINE instruction*
instruction := profile | cosmos | service
profile     := "profile" ("pulse" | "balanced" | "quiet" | "auto")
cosmos      := "cosmos probe"
service     := "service check" SERVICE_NAME
```

Comments start with `#`. There is no shell escape, no arbitrary command execution, and no filesystem mutation instruction in version 1.

Run a plan with:

```bash
synapse apply language/examples/pulse.syn
```
