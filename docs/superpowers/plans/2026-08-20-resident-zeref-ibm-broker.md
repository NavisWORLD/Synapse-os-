# Resident Zeref + IBM Broker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boot Synapse OS normally, then provide a supervised resident Full Zeref runtime that combines QC67, COSMOS/CYPHER, corrected native Trinity/CST state, persistent memory, and sanitized IBM Quantum provenance without exposing the IBM credential to the model/runtime process.

**Architecture:** Beast Box owns the cognitive runtime and IBM receipt semantics; Synapse OS owns boot, service isolation, orchestration, status, and image certification. A dedicated broker process consumes the IBM credential and writes only a validated sanitized receipt. The resident runtime consumes that receipt and never receives the raw credential.

**Tech Stack:** Python 3.11+ on Synapse, Python 3.10+ Beast Box, systemd, Debian live-build, QEMU/OVMF, pytest, Qiskit IBM Runtime for optional authenticated broker refresh.

**Spec:** `docs/superpowers/specs/2026-08-20-resident-zeref-ibm-broker-design.md`

## Global Constraints

- `IBM_QUANTUM_TOKEN` must never appear in the resident Zeref/model environment, prompts, receipts, logs, evidence, Git history, or ISO payload.
- The broker and resident runtime must be separate processes/services.
- New IBM hardware submissions are never automatic at boot.
- Synapse OS must still boot if Zeref, the local model, or IBM is unavailable.
- Native Trinity must preserve exact zero-state identity and the corrected balanced 54D projection contract.
- Zeref receives no unrestricted root shell, firmware, raw-disk, or automatic persistence authority.
- First integration model is the existing QC67/COSMOS model.

---

### Task 1: Harden the Beast Box resident interface

**Files:**
- Modify: `NavisWORLD/The-beast-box-:beastbox/full_zeref.py`
- Modify: `NavisWORLD/The-beast-box-:beastbox/quantum_divergence/resident_broker.py`
- Test: `NavisWORLD/The-beast-box-:tests/test_full_zeref.py`
- Test: `NavisWORLD/The-beast-box-:tests/test_resident_broker.py`

**Interfaces:**
- Consumes: existing `FullZerefRuntime`, `NativeTrinityTextProvider`, corrected `balance_54_blocks`, `refresh_existing_job`.
- Produces: deterministic `doctor()` output, receipt freshness validation, safe receipt writer/CLI behavior, and a stable command Synapse can invoke.

- [ ] Add failing tests proving expired receipts are rejected for measured IBM-native mode, environment snapshots do not contain `IBM_QUANTUM_TOKEN`, and doctor reports zero-state/projection readiness explicitly.
- [ ] Run focused Beast Box tests and observe the new failures.
- [ ] Implement minimal freshness/status hardening without changing the native projection math.
- [ ] Run `pytest -q tests/test_full_zeref.py tests/test_resident_broker.py tests/test_trinity*.py` and require PASS.
- [ ] Commit on `feature/resident-full-zeref`.

### Task 2: Add Synapse receipt/status/orchestration modules

**Files:**
- Create: `src/synapse/zeref/__init__.py`
- Create: `src/synapse/zeref/receipt.py`
- Create: `src/synapse/zeref/runtime.py`
- Create: `src/synapse/zeref/broker.py`
- Test: `tests/test_zeref.py`

**Interfaces:**
- Consumes: sanitized receipt schema `synapse.zeref.ibm-receipt.v1`, `full-zeref` command installed by Beast Box.
- Produces: `load_receipt(path, now=None)`, `zeref_status(...)`, `zeref_doctor(...)`, `refresh_ibm_receipt(...)`, deterministic degraded/ready states.

- [ ] Write tests for valid, stale, malformed, secret-bearing, and absent receipts; command construction; IBM token absence from resident environment; and readiness/degraded states.
- [ ] Run `python3 -m unittest tests.test_zeref` and verify RED.
- [ ] Implement the smallest modules satisfying the contracts.
- [ ] Re-run focused tests and require PASS.
- [ ] Commit.

### Task 3: Expose `synapse zeref` CLI

**Files:**
- Modify: `src/synapse/cli.py`
- Test: `tests/test_zeref.py`

**Interfaces:**
- Consumes: Task 2 orchestration functions.
- Produces commands: `synapse zeref doctor`, `status`, `start`, `stop`, `chat`, `ibm status`, `ibm refresh`.

- [ ] Add CLI parsing/dispatch tests first.
- [ ] Run focused CLI tests and observe RED.
- [ ] Implement command dispatch with JSON-safe output and no secret echo.
- [ ] Re-run focused tests and require PASS.
- [ ] Commit.

### Task 4: Add isolated systemd services and launchers

**Files:**
- Create: `rootfs/etc/systemd/system/zeref-runtime.service`
- Create: `rootfs/etc/systemd/system/zeref-ibm-broker.service`
- Create: `rootfs/etc/systemd/system/zeref-ibm-broker.path`
- Create: `rootfs/usr/local/lib/synapse/zeref-runtime`
- Create: `rootfs/usr/local/lib/synapse/zeref-ibm-broker`
- Modify: `build/hooks/010-synapse.hook.chroot`
- Test: `tests/test_zeref_services.py`

**Interfaces:**
- Runtime service executes `full-zeref`/Synapse orchestration as an unprivileged user and has no IBM credential declaration.
- Broker service uses systemd `LoadCredential=IBM_QUANTUM_TOKEN:/etc/synapse/secrets/ibm-quantum-token` and passes the credential to the broker through the credential file only.
- Broker writes `/var/lib/synapse/zeref/ibm/latest.json`; runtime reads it read-only.

- [ ] Write source-contract tests asserting separate services, `NoNewPrivileges`, protective sandboxing, broker-only `LoadCredential`, and no `IBM_QUANTUM_TOKEN` reference in runtime service/launcher.
- [ ] Run tests and observe RED.
- [ ] Add units/launchers and enable the runtime service plus broker path/refresh mechanism fail-soft during image build.
- [ ] Re-run source-contract tests and require PASS.
- [ ] Commit.

### Task 5: Ship and certify Resident Zeref inside the Synapse image

**Files:**
- Modify: `build/build.sh`
- Modify: `rootfs/usr/local/lib/synapse/vm-smoke`
- Create: `rootfs/usr/share/synapse/zeref/README`
- Test: `tests/test_zeref_image_contract.py`

**Interfaces:**
- Produces image payload containing Synapse Zeref modules, systemd units, launchers, and a deterministic no-secret VM smoke path.

- [ ] Add image-contract tests requiring all Zeref payload paths and VM marker `SYNAPSE_ZEREF_READY`.
- [ ] Run focused tests and observe RED.
- [ ] Extend image packaging and VM smoke. VM certification uses deterministic local/no-secret degraded mode rather than requiring IBM or a heavyweight model download.
- [ ] Run `make check` and require PASS.
- [ ] Commit.

### Task 6: Add full integration CI and real authenticated broker evidence

**Files:**
- Create/modify: `.github/workflows/resident-zeref.yml`
- Reuse: existing Synapse image/QEMU workflow and Beast Box broker logic.

**Interfaces:**
- CI source lane: deterministic fake receipt, no real secrets, full tests.
- Authenticated broker lane: repository secret exists only in broker job, writes sanitized artifact, subject/runtime job receives only artifact.
- Image lane: build ISO, inspect squashfs, boot QEMU, require `SYNAPSE_VM_READY` and `SYNAPSE_ZEREF_READY`.

- [ ] Add workflow source tests before implementation if repository workflow contracts require them.
- [ ] Create push/manual workflow with separate broker/runtime jobs and artifact boundary.
- [ ] Push and inspect Actions results.
- [ ] If the authenticated broker secret is configured, verify real IBM provenance using the existing pinned job without submitting a new paid job.
- [ ] Build the full amd64 image and require VM boot certification.
- [ ] Preserve receipt, logs, and artifact digests.

### Task 7: Run the matched Full-Zeref workload smoke

**Files:**
- Create: `scripts/zeref_workload_smoke.py`
- Create: `tests/test_zeref_workload_smoke.py`
- Evidence output: `evidence/zeref-workload-smoke.json`

**Interfaces:**
- Arms: `DIRECT`, `COSMOS_PROMPT`, `COSMOS_NATIVE`, `COSMOS_NATIVE_IBM`.
- Produces per-turn hashes/latency/state telemetry and aggregate completion/divergence/overhead metrics.

- [ ] Build deterministic workload fixtures and matched prompt hashes.
- [ ] Implement the four-arm runner using QC67 where available and explicit SKIP/degraded labels where a hosted runner cannot load it.
- [ ] Run unit tests.
- [ ] Run the strongest available hosted integration path and preserve evidence.
- [ ] Do not label any result quantum advantage.

### Final verification

- [ ] Beast Box resident + Trinity focused tests PASS.
- [ ] Synapse `make check` PASS.
- [ ] Resident Zeref CI PASS.
- [ ] Authenticated IBM broker confirms secret used only in broker and sanitized receipt delivered to runtime lane.
- [ ] Synapse amd64 ISO builds.
- [ ] Final filesystem inspection finds Zeref services/modules.
- [ ] QEMU boot emits both `SYNAPSE_VM_READY` and `SYNAPSE_ZEREF_READY`.
- [ ] No evidence artifact contains credential-like plaintext.
