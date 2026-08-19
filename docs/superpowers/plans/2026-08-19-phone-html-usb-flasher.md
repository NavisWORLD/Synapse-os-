# Phone HTML USB Flasher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-file phone UI that can probe for direct WebUSB mass-storage access and, when available, safely raw-flash and verify a Synapse OS ISO, while also providing a fixed-purpose authenticated local helper on port 8788 for platforms that block direct browser mass-storage access.

**Architecture:** `phone-bootstrap/FLASH_USB.html` owns the mobile state machine and direct WebUSB Bulk-Only-Transport/SCSI adapter. `src/synapse/usb_flash.py` owns server-side image verification, removable-USB selection, one-time arming, raw writing, and read-back verification. `src/synapse/usb_flash_server.py` exposes only fixed-purpose authenticated flasher routes and serves the same HTML for same-origin fallback mode.

**Tech Stack:** HTML/CSS/vanilla JavaScript, WebUSB when exposed by the browser, USB Mass Storage Bulk-Only Transport + SCSI READ/WRITE(10), Python 3 stdlib HTTP server/threading/hashlib/os/subprocess, Linux `lsblk`/`findmnt` for the local-helper inventory boundary, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-19-phone-html-usb-flasher-design.md`

## Global Constraints

- Direct browser mode must never report success unless a real USB write and read-back verification completed.
- Local helper binds to port `8788` by default and requires a one-boot pairing token for every destructive/read endpoint except health/UI.
- Real helper mode may target only a uniquely identified `TYPE=disk`, `RM=1`, `TRAN=usb` block device with enough capacity.
- Internal SSD/eMMC/NVMe, source media, ambiguous targets, undersized targets, changed target fingerprints, and changed image hashes fail closed.
- No `/shell`, `/exec`, arbitrary command, arbitrary block path, or request-controlled image/repository URL.
- Destructive authorization expires, is exactly-once, and is bound to target fingerprint + image SHA-256 + image byte size.
- `HOLD TO FLASH USB` requires 2500 ms.
- Full-image SHA-256 must match before write; full read-back SHA-256 over the original image byte length must match before `BOOTABLE USB VERIFIED`.
- Physical iPhone + adapter success is separate from CI/software verification.

---

### Task 1: Define flasher core contracts with failing tests

**Files:**
- Create: `tests/test_usb_flash.py`
- Create: `src/synapse/usb_flash.py`

**Interfaces:**
- Produces `UsbFlashError(code: str, message: str)`.
- Produces immutable `UsbDevice` records and `parse_usb_inventory(payload) -> list[UsbDevice]`.
- Produces `select_usb_target(devices, *, image_size: int, source_disk_path: str | None) -> UsbDevice`.
- Produces `UsbFlashManager(...).image_status()`, `.preflight()`, `.arm()`, `.start(challenge_id, acknowledgement)`, `.status()`, `.receipt()`.

- [ ] Write tests that require removable+USB+disk identity, reject internal/ambiguous/source/undersized media, and assert deterministic target fingerprints.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_usb_flash -v` and confirm failure because the module/contracts do not exist.
- [ ] Implement only inventory parsing and target policy.
- [ ] Re-run the focused tests until the inventory/target-policy group passes.
- [ ] Add failing tests for image SHA verification, arm binding/expiry/replay, target/image revalidation, simulation write, and read-back mismatch.
- [ ] Run focused tests and confirm those new assertions fail before manager implementation.
- [ ] Implement the manager, bounded writer, full read-back hash verification, receipt, and deterministic simulation path.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_usb_flash -v` and require zero failures.

### Task 2: Add the authenticated fixed-purpose helper API

**Files:**
- Create: `src/synapse/usb_flash_server.py`
- Create: `tests/test_usb_flash_http.py`

**Interfaces:**
- Public: `GET /`, `GET /FLASH_USB.html`, `GET /v1/health`.
- Authenticated reads: `GET /v1/capabilities`, `/v1/devices`, `/v1/image`, `/v1/flash/status`, `/v1/flash/receipt`.
- Authenticated actions: `POST /v1/hello`, `/v1/image/prepare`, `/v1/flash/arm`, `/v1/flash/start`.
- Request bodies may carry only `message`, or `challenge_id` + `acknowledgement` for start; all disk/image/path/command/url control fields are rejected.

- [ ] Write HTTP tests for public health, auth enforcement, stable error shape, fixed routes, forbidden control fields, arm/start pass-through, and serving `FLASH_USB.html`.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_usb_flash_http -v` and confirm failure before server implementation.
- [ ] Implement the stdlib `ThreadingHTTPServer` entrypoint with CORS/no-store, token file support, fixed image/checksum CLI options, and no generic execution surface.
- [ ] Re-run the focused HTTP tests and require zero failures.

### Task 3: Build the direct-browser HTML flasher

**Files:**
- Create: `phone-bootstrap/FLASH_USB.html`
- Create: `tests/test_usb_flash_html.py`

**Interfaces:**
- Capability probe exposes `navigator.usb`, secure-context status, filesystem APIs, browser UA, and exact failures.
- Local image input requires `.iso` plus a SHA-256 sidecar or pasted expected digest.
- Direct transport only accepts USB Mass Storage interface class `0x08`, SCSI transparent subclass `0x06`, Bulk-Only protocol `0x50`.
- Direct writer uses SCSI READ CAPACITY(10), WRITE(10), SYNCHRONIZE CACHE(10), READ(10), and full read-back SHA-256.
- Helper adapter speaks the Task 2 routes and shares the same `CAPABILITY CHECK → DEVICE SELECTION → IMAGE READY → PREFLIGHT → ARMED → FLASHING → VERIFYING → BOOTABLE USB VERIFIED/FAILED` state machine.

- [ ] Write source-contract tests asserting all explicit states, 2500 ms hold, WebUSB capability probe, mass-storage class/subclass/protocol checks, CBW/CSW signatures, WRITE(10)/READ(10)/SYNC CACHE opcodes, helper routes, and absence of fake-success shortcut strings.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_usb_flash_html -v` and confirm failure because `FLASH_USB.html` does not exist.
- [ ] Implement the responsive single-file UI based on GENESIS visual language.
- [ ] Implement streaming/incremental SHA-256 in JavaScript so multi-GB ISOs are not loaded into RAM at once.
- [ ] Implement WebUSB device selection and protected-interface/error reporting.
- [ ] Implement the bounded MSC BOT/SCSI adapter and full source/read-back verification path.
- [ ] Implement helper connection/token/preflight/arm/start/status/receipt fallback using `:8788`.
- [ ] Re-run the HTML source tests and require zero failures.

### Task 4: Package the helper and HTML into Synapse OS without auto-enabling privileged access

**Files:**
- Create: `rootfs/usr/local/bin/synapse-usb-flash-server`
- Modify: `build/build.sh`
- Modify: `tests/test_usb_flash_html.py`

**Interfaces:**
- Launcher executes `python3 -m synapse.usb_flash_server` with the installed Python package path.
- Built image contains `/usr/share/synapse/FLASH_USB.html`.
- No systemd unit is enabled by default; the helper is an explicit owner-started privileged tool.

- [ ] Extend tests to require the launcher, build staging of `FLASH_USB.html`, and no auto-enabled flasher service.
- [ ] Run focused tests and confirm the new packaging assertions fail.
- [ ] Add the launcher and build-copy step.
- [ ] Re-run focused tests and require zero failures.

### Task 5: Document the exact phone test and safe helper flow

**Files:**
- Create: `FLASH_USB.md`
- Modify: `USB_INSTALL.md`
- Modify: `README.md`

**Interfaces:**
- Documentation distinguishes direct browser experiment from local-helper mode and from GENESIS OS installation.
- First physical test stops after capability/device detection; destructive flashing is a separate explicit checkpoint.

- [ ] Add `FLASH_USB.md` with direct-phone test, helper launch syntax, token/IP discovery, image/checksum selection, destructive warning, and verification result interpretation.
- [ ] Link it from `USB_INSTALL.md` and the root README.
- [ ] Add/extend source-contract tests for the docs links.
- [ ] Run the focused tests and require zero failures.

### Task 6: Run the complete repository verification and prepare review

**Files:**
- No new implementation files unless verification finds a root-cause defect.

- [ ] Run `make check` in CI and require zero failures (intentional SDK skips are allowed only if already part of baseline policy).
- [ ] Run the amd64 build/VM gate and require ISO build, SHA verification, generated-filesystem inspection, QEMU live boot, disposable GENESIS install, and cold boot to pass.
- [ ] Inspect the PR diff for forbidden generic execution routes and accidental internal-disk target controls.
- [ ] Confirm `phone-bootstrap/FLASH_USB.html` exists on the exact verified head.
- [ ] Export that exact verified HTML to the conversation for the physical iPhone capability test.

## Self-review

- Spec coverage: direct-browser capability probing, real direct BOT/SCSI path, helper fallback, image integrity, target policy, one-time arm, full read-back verification, packaging, docs, and physical-vs-CI boundary are all mapped to tasks.
- Placeholder scan: no TODO/TBD/implement-later steps remain.
- Type consistency: `UsbFlashManager` and API route names are identical across Tasks 1–3; the UI uses the same `/v1/flash/*` names the server exposes.
