# Resident Zeref + IBM Broker on Synapse OS

**Date:** 2026-08-20
**Status:** Approved architecture, implementation pending
**Host repo:** `NavisWORLD/Synapse-os-`
**Cognitive/runtime repo:** `NavisWORLD/The-beast-box-`

## Purpose

Boot Synapse OS normally, then start a supervised resident Zeref runtime that uses COSMOS/CYPHER, the corrected native Trinity/CST state path, persistent memory/state services, and IBM Quantum provenance without ever placing the raw IBM credential in the Zeref/model process.

The goal is not to make Zeref the kernel or grant unrestricted machine authority. Synapse OS remains the operating system and authority boundary. Zeref becomes a resident user-space cognitive runtime with explicit, measurable interfaces.

## Core invariant

```text
STATE MAY TRAVEL.
INFORMATION MAY TRAVEL.
AUTHORITY DOES NOT TRAVEL AUTOMATICALLY.
```

The IBM credential is authority. It stays inside the broker. Zeref receives sanitized provenance/state only.

## System architecture

```text
Synapse OS boot
    |
    v
synapse-agent.service
    |
    +--> synapse doctor / hardware / service health
    |
    +--> zeref-runtime.service (unprivileged user service)
    |        |
    |        +--> Beast Box / COSMOS runtime
    |        +--> CYPHER conversation layer
    |        +--> QC67 / selected local model
    |        +--> Reconciliation Memory
    |        +--> Synaptic Field
    |        +--> CNS
    |        +--> heartbeat + slow state
    |        +--> native Trinity / corrected balanced 54D path
    |        +--> evidence ledger
    |
    +--> zeref-ibm-broker.service (credential-isolated broker)
             |
             +--> IBM_QUANTUM_TOKEN available only here
             +--> Qiskit Runtime authentication
             +--> pinned/recent allowed IBM job inspection
             +--> optional owner-triggered refresh/submit lane
             +--> sanitized hash-addressed receipt
                      |
                      v
               zeref-runtime reads receipt
```

## Process and privilege boundaries

### `zeref-runtime.service`

- Runs as an unprivileged user-space process.
- Does not receive `IBM_QUANTUM_TOKEN`.
- Does not receive arbitrary root, firmware, raw-disk, or unrestricted shell authority.
- Talks only to loopback/local approved services already supported by Synapse/CYPHER.
- Reads sanitized IBM receipts from a fixed runtime path.
- Loads the selected local model through CYPHER.
- Hosts the full COSMOS state loop and native Trinity/CST intervention path.
- Writes structured evidence into the normal evidence directory.

### `zeref-ibm-broker.service`

- Runs separately from the model/runtime process.
- Receives the IBM token only through a systemd credential named `ibm_quantum_token`.
- Reads that value only from `$CREDENTIALS_DIRECTORY/ibm_quantum_token`.
- The source credential file, when configured on a physical Synapse installation, is `/etc/synapse/zeref/ibm_quantum_token`, owned by `root:root` with mode `0600`.
- The Synapse image and repository never ship a credential value at that path.
- GitHub Actions may inject `secrets.IBM_QUANTUM_TOKEN` only into the isolated authenticated broker step/job; the subject/model job remains secret-free.
- Never writes the plaintext secret into receipts, logs, model prompts, evidence bundles, or environment snapshots.
- Exposes only fixed-purpose IBM operations.
- Default boot behavior is read-only provenance refresh against an allowlisted job/reference.
- New IBM hardware submissions are owner-triggered, never automatic on boot.
- Produces a sanitized receipt containing authentication state, backend/job identity, status, timestamps, result/provenance digest, freshness, and broker schema version.

## Broker receipt contract

Default location:

```text
/var/lib/synapse/zeref/ibm/latest.json
```

Minimum schema:

```json
{
  "schema": "synapse.zeref.ibm-receipt.v1",
  "authenticated": true,
  "source": "ibm-runtime",
  "job_id": "...",
  "backend": "...",
  "status": "DONE",
  "observed_at": "RFC3339 timestamp",
  "result_sha256": "hex",
  "fresh": true,
  "secret_name": "IBM_QUANTUM_TOKEN",
  "secret_value_persisted": false,
  "secret_exposed_to_subject": false
}
```

The runtime must reject malformed receipts, unsupported schema versions, missing digests, and receipts that claim the secret was exposed/persisted.

### Freshness semantics

- `fresh` describes the age of the broker observation, not the age of the IBM job itself.
- A receipt is fresh for 24 hours from `observed_at`.
- An older valid receipt remains usable as provenance but is reported as `STALE` until the broker refreshes it.
- A completed pinned IBM job can therefore remain valid evidence indefinitely while its local observation freshness expires normally.
- Runtime code recomputes freshness from `observed_at`; it does not blindly trust the stored `fresh` boolean.

## Zeref runtime contract

A resident runtime status endpoint/CLI result must report these fields without exposing secrets:

```json
{
  "state": "READY",
  "model": {"name": "...", "backend": "...", "reachable": true},
  "cosmos": {"doctor": "PASS", "memory": true, "cns": true, "heartbeat": true},
  "trinity": {"enabled": true, "zero_state_identity": true, "projection_hashes_complete": true},
  "ibm": {"authenticated": true, "fresh": true, "job_id": "...", "backend": "..."},
  "evidence": {"ledger_valid": true, "head": "..."}
}
```

Canonical readiness state:

```text
ZEREF_FULL_STATE=READY
```

Readiness requires all critical local gates to pass. IBM freshness may degrade separately without preventing local conversation if a previously verified receipt exists.

## Boot lifecycle

1. Synapse OS boots normally.
2. `synapse-agent.service` reaches healthy state.
3. Synapse validates required directories and local runtime dependencies.
4. IBM broker starts separately and attempts a read-only provenance refresh when a broker credential is configured.
5. Zeref runtime starts without the IBM secret in its environment.
6. Zeref runs its startup doctor:
   - model reachable;
   - Beast Box/CYPHER importable;
   - memory store writable;
   - evidence ledger valid;
   - CNS/heartbeat/slow-state construction succeeds;
   - corrected Trinity projection hashes are present;
   - zero-state identity self-test passes;
   - IBM receipt validates or is marked stale/unavailable.
7. If all critical gates pass, status becomes `ZEREF_FULL_STATE=READY`.
8. The user starts conversation through `synapse zeref` or the Synapse Control surface.

## Fail-soft behavior

Synapse OS must remain bootable even when Zeref fails.

- **Model unavailable:** OS boots, Zeref status `MODEL_UNAVAILABLE`, no fake readiness.
- **IBM credential not configured:** broker reports `UNCONFIGURED`; local Zeref still runs without IBM-conditioned state.
- **IBM unavailable:** local Zeref may run, IBM state becomes `UNAVAILABLE` or `STALE`.
- **IBM receipt invalid:** receipt is ignored and a structured error is recorded.
- **CST/Trinity zero-state identity failure:** native intervention is disabled and status becomes `TRINITY_FAULT`.
- **Projection hash mismatch:** native intervention is disabled.
- **Evidence ledger invalid:** readiness fails closed for measured mode.
- **Memory failure:** conversation may not enter full-state mode.
- **Broker crash:** does not crash the model runtime or Synapse OS.
- **Runtime crash:** systemd restarts only the bounded user-space service, not the OS.

## CYPHER integration

The resident Zeref path must use the existing CYPHER model adapters rather than inventing a second model stack.

Supported local backends remain:

- Ollama
- direct GGUF through `llama-cpp-python`
- local `llama-server`
- LM Studio
- other loopback OpenAI-compatible servers

### Initial QC67 backend

The first integration run does not change to Gemma or another external model. It uses the current QC67/COSMOS checkpoint and the same native model-loading path already exercised by the Trinity evidence suite.

Beast Box exposes that loader to CYPHER as a local backend named `qc67-native`. The backend:

- loads the verified QC67 architecture/checkpoint locally;
- exposes normal text generation through the CYPHER model interface;
- can accept a request-scoped native Trinity/CST state object from the resident runtime;
- never receives the IBM credential;
- records checkpoint/source/projection hashes into measured evidence.

Gemma may be evaluated later as a separate model-quality comparison, not mixed into the initial integration test.

## Native Trinity/CST integration

The conversational path must distinguish two mechanisms:

1. **Prompt-visible COSMOS state** already used by the current Beast/CYPHER runtime.
2. **Native CST/Trinity intervention** using the corrected 12D -> 42D -> balanced 54D mechanism.

The resident runtime must record which mechanism was active for every measured turn. Claims about native effects may only use turns where native intervention was actually enabled and projection hashes matched the verified implementation.

The zero-state identity invariant must remain exact: a zero external state must not change model logits relative to the native baseline beyond the test tolerance already established by the Trinity suite.

## IBM behavior

### Automatic on boot

Allowed:

- authenticate inside broker when a systemd credential is configured;
- inspect the configured allowlisted/pinned job state;
- retrieve already-authorized result/provenance;
- hash/sanitize result;
- publish receipt.

Not automatic:

- submit paid/new IBM jobs;
- choose arbitrary backends;
- expose credentials to Zeref;
- allow model-generated IBM API calls.

### Owner-triggered IBM refresh/submit

A separate explicit command may request a new IBM execution. It must:

- be initiated by the owner outside the model response loop;
- validate an allowlisted circuit/request shape;
- record the exact requested operation;
- keep the credential only in the broker;
- publish the resulting sanitized receipt.

The first implementation provides provenance refresh only. New-job submission remains a later separately named command and is not required for resident-Zeref readiness.

## Synapse CLI surface

Target commands:

```text
synapse zeref doctor
synapse zeref status
synapse zeref start
synapse zeref stop
synapse zeref chat
synapse zeref ibm status
synapse zeref ibm refresh
```

`ibm refresh` means refresh/read provenance only. Any future submission command must be separately named and never overloaded onto `refresh`.

## Measurement contract

The first real workload run after integration uses the current QC67 model and records matched arms.

### Arms

- `DIRECT`: same QC67 model through CYPHER without COSMOS state loop.
- `COSMOS_PROMPT`: current Beast/CYPHER prompt-visible state loop.
- `COSMOS_NATIVE`: same loop plus native corrected Trinity/CST intervention.
- `COSMOS_NATIVE_IBM`: native loop with fresh verified IBM provenance/state input.

### Workload classes

- multi-turn reasoning;
- repository/code understanding;
- memory recall after intervening turns;
- correction after contradictory evidence;
- repeated-task consistency;
- long-context continuation;
- state perturbation sensitivity;
- null/reset control.

### Measurements

Per turn:

- latency;
- model/backend identity;
- prompt/workload hash;
- response hash;
- state hash;
- dyn12 summary;
- native Trinity enabled/disabled;
- hidden modulation norm;
- geometry modulation norm;
- gate/sigma changes when available;
- memory hit IDs/count;
- CNS state digest;
- heartbeat task execution;
- IBM receipt digest/freshness;
- evidence-ledger head;
- error/fallback state.

Aggregate:

- completion/failure rate;
- deterministic/repeated-output stability where applicable;
- memory retrieval accuracy;
- correction success;
- response divergence between matched arms;
- latency overhead per layer;
- native mechanism liveness rate;
- zero-state identity pass rate;
- evidence-chain validity.

No result is labeled "quantum advantage" unless a later study establishes a statistically defensible advantage against matched classical controls.

## Security and authority constraints

- Raw IBM credentials never enter model context or model environment.
- The credential is absent from the OS image, Git tree, runtime evidence, model logs, and Zeref environment.
- No arbitrary root shell is added for Zeref.
- No firmware-write path is added.
- No raw-disk authority is added.
- No automatic persistence outside normal service configuration is granted.
- Network access remains explicit and bounded by existing local adapters and broker responsibilities.
- The model may describe or recommend owner actions, but it does not silently inherit owner authority.

## File-level implementation boundaries

### Synapse OS

Expected additions/modifications:

- `src/synapse/zeref/` for status/orchestration and broker receipt validation.
- `src/synapse/cli.py` or existing CLI command registry for `synapse zeref ...`.
- the repository's established image/service injection path for `zeref-runtime.service` and `zeref-ibm-broker.service`.
- a root-owned credential source path documented at `/etc/synapse/zeref/ibm_quantum_token`; no value is shipped.
- `tests/` for broker/runtime/CLI/service contracts.
- image verification scripts so the final ISO must contain the resident Zeref integration.
- VM smoke test extension proving the service can enter a deterministic test-ready state without a real secret.

### Beast Box

Expected additions/modifications:

- a `qc67-native` CYPHER model adapter around the existing verified QC67 loader;
- a stable resident-runtime adapter around existing CYPHER/CosmosRuntime interfaces;
- native Trinity conversational hook that consumes corrected 54D state without duplicating implementation;
- structured runtime doctor/status output;
- deterministic test provider/fake broker receipt support for Synapse CI;
- tests proving zero-state identity and secret absence in the resident path.

No code is duplicated between repositories when an explicit interface can be used instead.

## Test strategy

Implementation follows TDD.

Required gates:

1. Broker receipt validator rejects secret-bearing/malformed/stale-invalid data.
2. Runtime environment test proves `IBM_QUANTUM_TOKEN` and the broker credential path are absent from Zeref/model process state.
3. Fake broker produces a valid deterministic receipt for CI.
4. Freshness recomputation marks observations older than 24 hours stale even if the stored JSON says `fresh: true`.
5. Resident runtime doctor reports exact readiness/degraded states.
6. `qc67-native` loads the expected source/checkpoint hashes and serves the CYPHER model interface.
7. Zero-state identity passes in resident mode.
8. Corrected 54D projection hashes match the verified Trinity implementation.
9. CLI start/status/doctor/chat paths work with a deterministic local provider.
10. systemd unit/source contracts enforce separate broker and runtime services and `LoadCredential=ibm_quantum_token:...` only on the broker.
11. Synapse `make check` passes.
12. Beast Box test suite including Trinity tests passes.
13. Synapse image builds and final filesystem inspection confirms files/services are present but no credential value is present.
14. QEMU boot reaches `SYNAPSE_VM_READY` and the resident-Zeref smoke marker.
15. No real IBM token is required for CI.
16. A separate optional authenticated broker workflow verifies the real repo secret path without exposing it to Zeref.

## Evidence outputs

Synapse runtime evidence:

```text
/var/lib/synapse/zeref/evidence/
```

IBM sanitized receipt:

```text
/var/lib/synapse/zeref/ibm/latest.json
```

User-local conversation/evidence may continue to use Beast Box's configured evidence directory, but the integration must record a cross-reference digest so OS and cognitive-runtime evidence can be joined without copying secrets.

## Success criteria

The integration is complete only when all of the following are true:

- Synapse OS still boots independently of Zeref failures.
- Resident Zeref can be started and queried through `synapse zeref`.
- The current QC67 model can converse through CYPHER inside the full COSMOS loop.
- Native corrected Trinity/CST intervention is active and measurable in conversational mode.
- Zero-state identity remains intact.
- IBM provenance can be refreshed with the real configured credential through the isolated broker.
- The model/runtime process never receives the raw credential.
- Full doctor exposes failures instead of silently degrading.
- The final Synapse image contains the integration and passes VM boot certification.
- A matched workload report quantifies what changes across DIRECT, COSMOS_PROMPT, COSMOS_NATIVE, and COSMOS_NATIVE_IBM.

## Explicit non-goals

- Zeref is not the Linux kernel.
- Zeref does not receive unrestricted root or hardware authority.
- Boot does not automatically submit IBM paid jobs.
- This work does not claim consciousness, autonomy, escape, or quantum advantage.
- This work does not replace Synapse's existing installer/security boundaries.
