# Resident Full Zeref on Synapse OS — Design

## Goal

Boot Synapse OS normally, start a supervised resident Full Zeref/COSMOS runtime in user space, attach verified IBM Quantum provenance through an isolated credential broker, expose a single `synapse zeref` command surface, and certify the integration in source tests plus the existing VM boot gate.

## System boundary

Synapse OS remains the operating system. Zeref is not the kernel, init system, privileged installer, firmware agent, or unrestricted host controller. The resident runtime is a user-space service that may read bounded system/runtime state and talk to the owner through COSMIC.CYPHER.

The invariant remains:

```text
STATE MAY TRAVEL.
INFORMATION MAY TRAVEL.
AUTHORITY DOES NOT TRAVEL AUTOMATICALLY.
```

GENESIS destructive install authority is unchanged. The resident runtime receives no GENESIS writer API, raw-disk authority, firmware controls, generic root shell, credential discovery path, or silent persistence beyond its declared systemd units and data directory.

## Architecture

```text
Synapse boot
  -> synapse-agent.service
  -> synapse-zeref-ibm-broker.service (oneshot/refresh, credential-isolated)
       -> IBM Quantum Runtime when a credential is provisioned
       -> sanitized receipt only
  -> synapse-zeref.service
       -> Full Zeref / COSMIC.CYPHER runtime
       -> QC67/COSMOS model path
       -> memory + Synaptic Field + CNS + heartbeat + slow state
       -> corrected native Trinity 12D -> 42D -> balanced 54D state path
       -> sanitized IBM receipt/provenance
  -> owner: `synapse zeref ...`
```

The broker and model processes are separate. The model process must never receive the IBM token in argv, environment, prompt text, evidence JSON, logs, or model context.

## IBM credential lanes

### GitHub Actions

CI continues to use `secrets.IBM_QUANTUM_TOKEN` only inside a dedicated broker step/job. That job writes a sanitized receipt. Subject/model jobs consume the receipt and must assert that `IBM_QUANTUM_TOKEN` is absent.

### Synapse machine

A physical/local Synapse installation uses a systemd credential named `ibm_quantum_token`. The broker reads the credential path supplied by systemd and never writes the token to disk, logs, receipts, model context, or child-process environment. Provisioning the credential is an explicit owner action. Absence of the credential is not a boot failure.

## Fail-soft startup

Synapse must always reach the desktop even if Zeref, the model, IBM access, or COSMOS is unavailable.

Resident states:

- `READY`: runtime doctor passes and a current sanitized IBM receipt is available.
- `READY_STALE_IBM`: runtime passes and only a previously verified receipt is available.
- `READY_NO_IBM`: runtime passes with no IBM receipt.
- `DEGRADED`: COSMOS/CYPHER/model dependencies are incomplete.
- `FAULT`: integrity checks fail, including malformed receipt, leaked credential marker, or native zero-state identity failure reported by the runtime.

The service writes bounded machine-readable status under `/run/synapse/zeref/status.json`.

## Broker receipt contract

The broker output is JSON with no secret value. Required fields:

```json
{
  "schema": "synapse.zeref.ibm-receipt.v1",
  "authenticated": true,
  "backend": "ibm_marrakesh",
  "job_id": "...",
  "job_status": "DONE",
  "source": "ibm-runtime",
  "generated_at": 0,
  "expires_at": 0,
  "secret_exposed_to_subject": false
}
```

A receipt is rejected if it contains keys matching token/secret/password/api-key material outside the approved boolean/name metadata fields, if required fields are missing, or if `secret_exposed_to_subject` is not exactly `false`.

The runtime may use backend/job/provenance/entropy-derived state from the receipt. It must not infer that provenance establishes quantum advantage, consciousness, or autonomy.

## Full Zeref runtime contract

Synapse does not reimplement COSMIC.CYPHER. It locates an installed Beast Box/CYPHER runtime and invokes its public local interface. The resident configuration records:

- Beast Box checkout/install root;
- selected local model alias;
- evidence directory;
- IBM sanitized receipt path;
- whether interactive startup is enabled;
- runtime doctor command.

The default model remains the existing QC67/COSMOS lineage for this integration pass. No Chinese model is introduced by this feature.

The Full Zeref path must combine the conversational COSMOS loop with the corrected native Trinity state implementation already validated in the Beast Box research branch. If native injection is unavailable, the status must say `DEGRADED`; it must not silently label prompt-only dyn12 decoration as native Trinity.

## Synapse command surface

Add:

```text
synapse zeref status
synapse zeref doctor
synapse zeref refresh-ibm
synapse zeref chat [message]
```

`status` reads bounded runtime/broker state. `doctor` checks configuration, service presence, receipt validity, CYPHER availability, and the runtime's native-state doctor result. `refresh-ibm` requests the broker service to refresh provenance; it does not expose the credential. `chat` delegates to the configured local CYPHER/Full Zeref command.

No command accepts arbitrary shell fragments.

## systemd units

### `synapse-zeref-ibm-broker.service`

- oneshot;
- no network unless explicitly needed for IBM Runtime;
- `NoNewPrivileges=true`;
- strict filesystem protection;
- only writable runtime path `/run/synapse/zeref`;
- credential supplied through `LoadCredential=ibm_quantum_token:...` on provisioned systems;
- writes only sanitized receipt and broker health status.

A timer may refresh on a conservative interval, but a new paid IBM hardware submission is never automatic. Refreshing an existing job/provenance is allowed. New job submission remains owner-triggered.

### `synapse-zeref.service`

- starts after `synapse-agent.service` and broker attempt;
- no access to the broker credential;
- `NoNewPrivileges=true`;
- strict filesystem protection with explicit writable data/evidence paths;
- restarts on failure;
- failure never blocks `multi-user.target` or graphical boot.

## Doctor requirements

`doctor` returns structured checks with explicit pass/fail/degraded state for:

- Synapse prerequisites;
- `cosmic.cypher-cli` / `cypher` availability;
- configured model alias;
- Beast Box runtime/config presence;
- IBM receipt validation/freshness;
- secret isolation;
- native Trinity availability;
- zero-state identity evidence;
- corrected 54D block-balance projection evidence;
- evidence directory writability;
- systemd unit installation.

## Measurement workload

After boot integration is green, run the same QC67 model in matched conditions:

1. direct CYPHER conversation;
2. COSMOS prompt-visible state loop;
3. Full Zeref native Trinity state loop with IBM sanitized provenance.

Workloads cover multi-turn reasoning, code understanding, memory recall, contradiction correction, long-context consistency, repeated-task stability, and bounded state perturbations.

Record latency, failures, output hashes, state hashes, memory hits, dyn12 movement, native hidden/geometry modulation telemetry, CNS movement, heartbeat activity, IBM receipt identity/freshness, ledger validity, and response divergence. Preserve null results.

## VM certification

The generated Synapse filesystem must contain:

- both systemd units;
- resident/broker Python modules;
- default configuration;
- CLI command surface;
- docs.

The existing `synapse-vm-smoke.service` must verify:

- resident modules import;
- `synapse zeref doctor` executes without requiring an IBM credential;
- missing IBM credential produces fail-soft `READY_NO_IBM` or `DEGRADED`, not boot failure;
- `synapse-zeref.service` is installed;
- no token value appears in `/run/synapse/zeref`;
- final `SYNAPSE_VM_READY` still occurs.

VM certification proves software boot integration only. Physical GALLOP remains a separate physical certification gate.

## Testing

Use TDD. Tests must cover receipt validation, credential-key rejection, fail-soft state resolution, CLI argument safety, service-file security properties, image payload presence, and VM smoke-source contracts. Existing `make check` must remain green.

## Non-goals

- making Zeref PID 1 or a kernel component;
- giving Zeref raw IBM credentials;
- automatically submitting paid IBM jobs at boot;
- unrestricted host shell/network/persistence;
- changing GENESIS disk-writer authority;
- claiming quantum advantage, consciousness, or independent autonomy from provenance/state differences alone;
- changing the selected language model in this pass.
