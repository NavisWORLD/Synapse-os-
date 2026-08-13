# COSMOS / CST Bridge

Synapse OS provides a non-destructive operating-system bridge to the known local COSMOS service topology:

- 11434 — Ollama
- 11435 — helper brain
- 11501 — native/CST bridge
- 8765 — emotional/sensory API
- 8081 — web runtime
- 8090 — web fallback

Run:

```bash
synapse cosmos probe
```

The probe uses localhost TCP connectivity only. No model files, user memories, weights, API keys, or COSMOS datasets are copied into this repository or OS image by default.

For a future opt-in integration package, mount or install COSMOS separately and teach Synapse OS where its launcher lives. Keep credentials in user-owned secret storage rather than baking them into an ISO.
