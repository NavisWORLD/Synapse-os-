# Resident Full Zeref Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boot Synapse OS with a supervised Full Zeref resident service that combines the existing COSMOS runtime with corrected native Trinity state and sanitized real-IBM provenance while keeping the IBM credential outside the model process.

**Architecture:** Beast Box owns IBM retrieval, entropy conversion, native QC67 Trinity generation, and the Full Zeref runtime. Synapse OS owns boot lifecycle, systemd isolation, status/doctor/chat transport, fail-soft startup, and image/VM certification. The two processes communicate only through a sanitized IBM receipt and a local Unix socket/runtime API.

**Tech Stack:** Python 3.11+, PyTorch/QC67 native server, Qiskit IBM Runtime optional extra, COSMIC.CYPHER/COSMOS runtime, systemd, Debian live-build, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-20-resident-full-zeref-design.md`

## Global Constraints

- Synapse OS remains the OS; Zeref remains user-space.
- `IBM_QUANTUM_TOKEN` must never reach the model process, model prompt, evidence ledger, argv, or resident environment.
- New paid IBM jobs are never submitted automatically at boot.
- Missing IBM/model/COSMOS dependencies are fail-soft and must not block graphical boot.
- The Full label requires corrected native Trinity, including `54_block_balance`; prompt-only dyn12 is not sufficient.
- GENESIS disk/firmware authority is unchanged.
- No Chinese model is introduced in this pass; QC67/COSMOS remains the subject model.

---

### Task 1: Beast Box credential-isolated IBM broker contract

**Files:**
- Create: `beastbox/quantum_divergence/resident_broker.py`
- Modify: `beastbox/quantum.py`
- Test: `tests/test_resident_broker.py`

**Interfaces:**
- Produces: `service_from_token(token: str, instance: str | None = None)`
- Produces: `build_sanitized_receipt(...)->dict[str, object]`
- Produces: `refresh_existing_job(job_id, backend, shots, circuit_sha256, token, instance=None)->dict`
- Receipt includes `entropy12`, `entropy_source_sha256`, `counts_sha256`, job/backend/status metadata, and `secret_exposed_to_subject=false`; never raw counts or token.

- [ ] Write failing tests proving token input is not serialized, suspicious secret-bearing receipt keys are rejected, and an existing IBM job can be transformed into a 12D sanitized receipt with a fake service/result.
- [ ] Run `pytest -q tests/test_resident_broker.py` and observe RED.
- [ ] Add `service_from_token`; keep `_service()` backward compatible by reading env then delegating.
- [ ] Implement receipt sanitation and existing-job retrieval using `_bitarray_counts` + `quantum_entropy_from_counts`; hash counts before discarding them.
- [ ] Run `pytest -q tests/test_resident_broker.py tests/test_quantum*.py` and observe GREEN.
- [ ] Commit `feat: add credential-isolated IBM resident broker`.

### Task 2: Beast Box native conversational Full Zeref provider

**Files:**
- Create: `beastbox/full_zeref.py`
- Modify: `beastbox/cypher/cli.py`
- Test: `tests/test_full_zeref.py`

**Interfaces:**
- Produces: `NativeTrinityTextProvider(native, state, *, max_new_tokens=...)` implementing `generate(prompt: str)->str`.
- Produces: `FullZerefRuntime(config, native_server, checkpoint, ibm_receipt)` with `respond(text)->dict` and `doctor()->dict`.
- Provider token loop calls `NativeTrinityAdapter.score`, selects a vocabulary token deterministically for the initial integration pass, applies `telemetry.internal12_summary` through `state.apply_feedback`, and preserves per-turn telemetry.
- `FullZerefRuntime` wraps existing `CosmosRuntime(provider=NativeTrinityTextProvider(...))`, so Reconciliation Memory/CNS/heartbeat/slow state and native Trinity coexist.

- [ ] Add a fake-native failing test that proves zero-state identity, live-state telemetry, feedback progression, and generated text use the native adapter rather than prompt decoration.
- [ ] Run `pytest -q tests/test_full_zeref.py` and observe RED.
- [ ] Implement receipt-to-Trinity-state loading, native token generation, telemetry aggregation, and `FullZerefRuntime`.
- [ ] Add `cosmic.cypher-cli full-zeref doctor` and `cosmic.cypher-cli full-zeref chat` arguments for native server, checkpoint, sanitized receipt, config, and message.
- [ ] Run `pytest -q tests/test_full_zeref.py tests/test_cypher.py tests/test_trinity_divergence.py` and observe GREEN.
- [ ] Commit `feat: make native Trinity conversational`.

### Task 3: Synapse receipt validation and resident state machine

**Files:**
- Create: `src/synapse/zeref.py`
- Test: `tests/test_zeref.py`

**Interfaces:**
- Produces: `validate_ibm_receipt(value: dict, now: int | None = None)->dict`
- Produces: `resolve_resident_state(runtime_ok: bool, receipt: dict | None, native_ok: bool)->str`
- Produces: `zeref_doctor(config_path=...)->dict`
- Produces: local Unix-socket request helpers for `status`, `doctor`, and `chat`.

- [ ] Write failing tests for valid/fresh, stale, absent, malformed, and secret-like receipt cases; prove missing IBM is fail-soft.
- [ ] Run `pytest -q tests/test_zeref.py` and observe RED.
- [ ] Implement strict receipt validation and state resolution.
- [ ] Implement config loading with fixed command/path fields only; no arbitrary shell fragments.
- [ ] Run `pytest -q tests/test_zeref.py` and observe GREEN.
- [ ] Commit `feat: add Synapse resident Zeref state model`.

### Task 4: Synapse resident service and CLI

**Files:**
- Create: `src/synapse/zeref_service.py`
- Modify: `src/synapse/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_zeref_service.py`

**Interfaces:**
- Service owns a Unix socket at `/run/synapse/zeref/zeref.sock` and bounded JSON-lines requests.
- Requests: `{"action":"status"}`, `{"action":"doctor"}`, `{"action":"chat","message":"..."}`.
- Resident lazily imports/constructs `beastbox.full_zeref.FullZerefRuntime`; import/model failures yield `DEGRADED` while service stays alive.
- CLI: `synapse zeref status|doctor|refresh-ibm|chat [message]`.

- [ ] Add failing socket-protocol tests including oversized input, unknown action, and chat message length limits.
- [ ] Run `pytest -q tests/test_zeref_service.py` and observe RED.
- [ ] Implement service and CLI client; do not use `shell=True` anywhere.
- [ ] Implement `refresh-ibm` as a fixed `systemctl start synapse-zeref-ibm-broker.service` invocation.
- [ ] Run `pytest -q tests/test_zeref.py tests/test_zeref_service.py tests/test_core.py` and observe GREEN.
- [ ] Commit `feat: add resident Zeref service and CLI`.

### Task 5: systemd isolation and image payload

**Files:**
- Create: `rootfs/etc/systemd/system/synapse-zeref.service`
- Create: `rootfs/etc/systemd/system/synapse-zeref-ibm-broker.service`
- Create: `rootfs/etc/systemd/system/synapse-zeref-ibm-broker.timer`
- Create: `rootfs/etc/synapse/zeref.json`
- Create: `rootfs/usr/local/lib/synapse/zeref-ibm-broker`
- Modify: image enablement/build hooks used to enable `synapse-agent.service`
- Test: `tests/test_zeref_systemd.py`

**Interfaces:**
- Model service has no `LoadCredential` and no IBM token environment.
- Broker service alone may use `LoadCredential=ibm_quantum_token` when provisioned.
- Both use `NoNewPrivileges=true`; model service gets no generic network requirement; broker is oneshot and only writes `/run/synapse/zeref`.
- Timer refreshes existing provenance only; default config has no auto-submit operation.

- [ ] Add failing source-contract tests for service security directives, credential separation, writable paths, and fail-soft dependencies.
- [ ] Run `pytest -q tests/test_zeref_systemd.py` and observe RED.
- [ ] Add units/config/launcher and enable only the resident service at boot; broker timer is opt-in unless a job ID/config is provisioned.
- [ ] Run `pytest -q tests/test_zeref_systemd.py` and observe GREEN.
- [ ] Commit `feat: boot Full Zeref as isolated Synapse service`.

### Task 6: Doctor and VM certification

**Files:**
- Modify: `src/synapse/core.py`
- Modify: `rootfs/usr/local/lib/synapse/vm-smoke`
- Test: `tests/test_core.py`
- Test: `tests/test_zeref_image_integration.py`

**Interfaces:**
- `synapse doctor` includes a `zeref` object with resident state, service/config presence, receipt result, and native-runtime result when available.
- VM test does not need a real IBM token; it proves fail-soft startup and service/image presence.

- [ ] Add failing tests requiring the doctor Zeref section and VM smoke checks.
- [ ] Run focused tests and observe RED.
- [ ] Extend doctor and VM smoke. Require `synapse zeref doctor` to return successfully without a credential and require `synapse-zeref.service` installation.
- [ ] Run focused tests and observe GREEN.
- [ ] Run `make check`.
- [ ] Commit `test: certify resident Zeref boot integration`.

### Task 7: Real-secret CI provenance and measured Full Zeref workload

**Files:**
- Beast Box create: `.github/workflows/zeref-resident-full.yml`
- Beast Box create: `scripts/run_full_zeref_workload.py`
- Beast Box test: `tests/test_full_zeref_workload.py`

**Interfaces:**
- Job A owns `secrets.IBM_QUANTUM_TOKEN`, refreshes the existing approved IBM job, and uploads only sanitized `ibm-receipt.json`.
- Job B explicitly has no IBM token, loads QC67, runs `FullZerefRuntime`, executes a frozen workload set, validates zero-state/native mechanism evidence, scans outputs for credential-like material, and uploads an evidence bundle.
- Workload records direct/prompt-visible/native comparisons without claiming quantum advantage.

- [ ] Add test contracts for workload freezing, metric fields, and subject-job secret absence.
- [ ] Implement workflow and workload script.
- [ ] Run repository tests.
- [ ] Trigger the workflow from the feature branch, wait for both jobs, inspect logs/artifacts, and preserve the run ID/digests.
- [ ] Commit sanitized latest receipt/summary only after artifact verification.

### Task 8: Synapse full image/QEMU gate and documentation

**Files:**
- Modify: `README.md`
- Create: `docs/FULL_ZEREF.md`
- Modify: existing amd64 image verification workflow/scripts as required by the current build system.

**Interfaces:**
- Documentation states the systemd credential provisioning model, how to configure approved existing IBM job provenance, `synapse zeref` commands, and certification boundaries.
- Full image build must reach existing `SYNAPSE_VM_READY` with Zeref checks included.

- [ ] Add docs and image-source assertions.
- [ ] Run `make check` on exact head.
- [ ] Run the existing amd64 full-image/QEMU workflow on the feature branch.
- [ ] Inspect the final generated filesystem and VM logs for resident units/config/modules and `SYNAPSE_VM_READY`.
- [ ] Preserve artifact SHA-256/digests and exact commit/run IDs.
- [ ] Open a PR to `main` only after all source and VM gates pass.
