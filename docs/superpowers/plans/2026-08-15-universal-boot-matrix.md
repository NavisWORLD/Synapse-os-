# Synapse Universal Boot Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Synapse OS build and validation system architecture-aware for amd64, arm64, and riscv64 while keeping certification evidence explicit.

**Architecture:** A JSON architecture registry is consumed by a small Python helper, the live-build script, the QEMU smoke runner, the hardware detector, and CI. amd64 remains the required certified VM gate; arm64 and riscv64 receive complete build/boot machinery and manual promotion gates.

**Tech Stack:** Debian 13 live-build, Python 3, POSIX shell, QEMU, GitHub Actions, JSON hardware profiles.

## Global Constraints

- Accepted build architectures are exactly `amd64`, `arm64`, and `riscv64`.
- Unknown architectures fail closed.
- `amd64` is `vm-certified`.
- `arm64` and `riscv64` begin as `experimental`.
- ASUS CX1700CKA / `GALLOP` begins as `physical-target`, not `physical-certified`.
- Firmware flashing is outside this subsystem.

---

### Task 1: Architecture registry

**Files:**
- Create: `build/architectures.json`
- Create: `scripts/arch_matrix.py`
- Create: `tests/test_arch_matrix.py`

**Interfaces:**
- Produces: `load_registry()`, `normalize_arch()`, `profile_for_arch()`, and CLI `shell|json|validate` modes.

- [ ] Write tests asserting alias normalization (`x86_64→amd64`, `aarch64→arm64`, `riscv64→riscv64`), exact kernel-package mappings, and unknown-architecture rejection.
- [ ] Run the tests and verify failure because the registry/helper do not exist.
- [ ] Implement the registry and helper with schema validation and shell-safe export output.
- [ ] Run `PYTHONPATH=. python3 -m unittest tests.test_arch_matrix -v`.

### Task 2: Architecture-aware live build

**Files:**
- Modify: `build/build.sh`
- Modify: `build/config/package-lists/synapse.list.chroot`

**Interfaces:**
- Consumes: `scripts/arch_matrix.py shell $SYNAPSE_ARCH`.
- Produces: `out/SynapseOS-<version>-<arch>.iso` and checksum.

- [ ] Remove the hard-coded `linux-image-amd64` source-list entry and write a test that inspects the generated architecture configuration.
- [ ] Load the architecture profile before `lb config` and append the correct kernel package to the generated package list.
- [ ] Detect host architecture; when target differs, require the profile's qemu-static binary and pass `--bootstrap-qemu-arch` and `--bootstrap-qemu-static` to live-build.
- [ ] Keep amd64's current hybrid ISO behavior and reject unsupported architecture/image combinations with a clear error.

### Task 3: Cross-architecture QEMU gate

**Files:**
- Create: `scripts/qemu-smoke.sh`
- Modify: `.github/workflows/build-vm-smoke.yml`
- Create: `.github/workflows/experimental-arch-vm.yml`

**Interfaces:**
- `scripts/qemu-smoke.sh <arch> <iso>` waits for `SYNAPSE_VM_READY` or fails on `SYNAPSE_VM_FAIL:`/timeout.

- [ ] Write shell-level command-generation checks for all three registry profiles.
- [ ] Implement ISO kernel/initrd extraction and architecture-specific QEMU commands using the registry's machine, CPU, and serial console.
- [ ] Replace duplicated amd64 QEMU command construction in the required workflow with `scripts/qemu-smoke.sh amd64`.
- [ ] Add `pull_request` to the required workflow so branch changes receive source/SDK validation.
- [ ] Add a manually dispatchable `experimental-arch-vm.yml` accepting `arm64` or `riscv64`, installing qemu-user-static plus the corresponding system emulator, building the image, verifying SHA-256, and running the same guest gate.

### Task 4: Hardware certification registry

**Files:**
- Create: `hardware/profiles.json`
- Create: `src/synapse/hardware.py`
- Create: `tests/test_hardware.py`
- Modify: `build/build.sh`
- Modify: `src/synapse/phone_bootstrap.py`

**Interfaces:**
- Produces: normalized hardware probe with `arch`, `hwid`, DMI fields, `profile_id`, and `certification_state`.

- [ ] Write pure matching tests for `GALLOP` + amd64 selecting `asus-cx1700cka-gallop`, generic arm64 remaining unverified, and mismatched architecture refusing the profile.
- [ ] Implement runtime architecture normalization plus DMI/ChromeOS HWID collection and profile matching.
- [ ] Copy `hardware/profiles.json` into `/usr/share/synapse/hardware/profiles.json` during image generation.
- [ ] Add hardware data to Phone Bootstrap's `/v1/device` payload without changing its authentication boundary.

### Task 5: Documentation and certification gate

**Files:**
- Create: `docs/ARCHITECTURES.md`
- Create: `docs/HARDWARE_CERTIFICATION.md`
- Modify: `README.md`

- [ ] Document the three architecture states and exact commands for required amd64 and experimental arm64/riscv64 gates.
- [ ] Document the ASUS CX1700CKA / GALLOP physical acceptance checklist: live boot, storage visibility, keyboard/touchpad, display, Wi-Fi, audio, suspend/resume, battery reporting, installer launch, installed-system reboot, Phone Bootstrap, COSMOS service activation.
- [ ] State that physical certification changes only after evidence from the real laptop is recorded.
