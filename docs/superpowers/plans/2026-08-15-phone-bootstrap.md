# Synapse Phone Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated phone-to-laptop bootstrap UI/API that reads Synapse OS hardware and installs/activates COSMOS from the configured GitHub repository.

**Architecture:** A Python standard-library HTTP daemon owns laptop inspection and the fixed-purpose installer. A single-file HTML client calls the daemon over a routed local/USB link. A per-user systemd service runs the daemon without root privileges.

**Tech Stack:** Python 3.11+ standard library, HTML/CSS/JavaScript `fetch`, systemd user service, Git, optional Docker/Docker Compose.

## Global Constraints

- No arbitrary shell endpoint.
- No wipe, raw-disk, firmware or reimage endpoint.
- Install destination defaults to `$HOME/COSMOS`.
- Existing dirty COSMOS checkouts are preserved, never reset.
- Mutating and device-detail API routes require a pairing token.
- Browser transport is ordinary HTTP over a trusted routed local connection; WebUSB is not required.

---

### Task 1: Laptop API and installer

**Files:**
- Create: `src/synapse/phone_bootstrap.py`
- Test: `tests/test_phone_bootstrap.py`

**Interfaces:**
- Produces: `device_snapshot() -> dict`, `InstallManager.start() -> dict`, `main(argv) -> int`
- HTTP: `GET /v1/health`, `GET /v1/device`, `POST /v1/hello`, `POST /v1/install/start`, `GET /v1/install/status`

- [ ] Write tests for payload shape and destructive-guard behavior.
- [ ] Run `PYTHONPATH=src python3 -m unittest tests.test_phone_bootstrap -v` and verify the initial failures.
- [ ] Implement the standard-library API, pairing token, Git checkout rules, background state machine and Docker activation adapter.
- [ ] Run the unit tests and `python3 -m py_compile src/synapse/phone_bootstrap.py`.

### Task 2: Phone HTML

**Files:**
- Create: `phone-bootstrap/phone-bootstrap.html`
- Create: `phone-bootstrap/README.md`
- Create: `PHONE_BOOTSTRAP.md`
- Create: `rootfs/usr/share/synapse/phone-bootstrap.html`

**Interfaces:**
- Consumes the Task 1 `/v1` endpoints.

- [ ] Build fields for API URL and pairing token plus Connect, Hello and Install controls.
- [ ] Render laptop facts and install progress.
- [ ] Add install confirmation and polling.
- [ ] Smoke-check that the HTML contains `/v1/install/start`, `/v1/device`, and the handshake text.

### Task 3: Synapse OS startup integration

**Files:**
- Create: `rootfs/usr/local/bin/synapse-phone-bootstrap`
- Create: `rootfs/usr/lib/systemd/user/synapse-phone-bootstrap.service`
- Create: `build/hooks/020-phone-bootstrap.hook.chroot`

**Interfaces:**
- Wrapper starts `python3 -m synapse.phone_bootstrap` with the image Python path.
- Global user unit binds `0.0.0.0:8787`, writes the token under `%t`, and installs into `%h/COSMOS`.

- [ ] Add the wrapper and user unit.
- [ ] Add the live-build hook to set wrapper mode and globally enable the user unit.
- [ ] Run `sh -n rootfs/usr/local/bin/synapse-phone-bootstrap` and `sh -n build/hooks/020-phone-bootstrap.hook.chroot`.

### Task 4: Repository verification and docs

**Files:**
- Create: `PHONE_BOOTSTRAP.md`
- Create: `phone-bootstrap/README.md`

- [ ] Document Phone Bootstrap usage and security boundaries.
- [ ] Run the repository unit/lint gates available in the execution environment.
- [ ] Inspect the final branch diff for accidental unrelated changes.
