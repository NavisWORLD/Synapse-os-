# Synapse Apple Intel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested `APPLE_INTEL/` subsystem for 2014-2015 non-Touch-Bar Intel MacBook Pro hardware, plus an isolated experimental `.app` inspection bridge, without disturbing GALLOP/Chromebook behavior.

**Architecture:** Keep Apple support additive. A small Python core provides deterministic hardware/profile/preflight logic and Mach-O inspection; shell launchers expose live-USB workflows; the existing GENESIS amd64 writer remains the destructive install engine. The live-image build copies `APPLE_INTEL/` into `/usr/share/synapse/apple-intel` and exposes safe launchers without modifying Apple firmware.

**Tech Stack:** Python 3.11+, POSIX/Bash shell, JSON, Linux sysfs/DMI, `lsblk`, `lspci`, GRUB x86_64 EFI, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-20-synapse-apple-intel-design.md`

## Global Constraints

- Initial physical target: pre-T2, non-Touch-Bar Intel MacBook Pro, 2014-2015 generation.
- Architecture: amd64/x86_64 only for destructive installation.
- Never claim general macOS application compatibility.
- Never redistribute Apple proprietary frameworks or bypass signing/DRM/licensing controls.
- Keep existing GALLOP/Chromebook install flow backward compatible.
- Never infer a destructive target from `/dev/sda` naming alone.
- No test may perform a real destructive disk write.
- Physical support remains `physical-target`/`experimental` until a real Mac passes live boot, acceptance checks, install, and cold boot.

---

### Task 1: Apple model registry and deterministic hardware detection

**Files:**
- Create: `APPLE_INTEL/hardware/apple_intel_profiles.json`
- Create: `APPLE_INTEL/lib/apple_hardware.py`
- Create: `APPLE_INTEL/hardware/detect_apple_model.sh`
- Create: `APPLE_INTEL/tests/test_detect_apple_model.py`
- Create: `APPLE_INTEL/tests/test_apple_profiles.py`

**Interfaces:**
- Produces: `load_profiles(path) -> dict`, `match_profile(probe, registry) -> dict`, `normalize_probe(probe, registry) -> dict`.
- `detect_apple_model.sh` prints one JSON hardware identity record.

- [ ] **Step 1: Write failing profile/detection tests** using representative MacBookPro11,1 / 11,2 / 11,3 / 12,1 fixtures and non-Apple fixtures. Assert unknown hardware never becomes supported.
- [ ] **Step 2: Run** `python3 -m unittest discover -s APPLE_INTEL/tests -p 'test_*apple*py' -v` and confirm import/feature failures.
- [ ] **Step 3: Implement registry and core matcher.** Registry entries must include `id`, `model_identifiers`, `arch`, `support_state`, `touch_bar:false`, and notes. Matcher requires Apple vendor plus explicit model identifier.
- [ ] **Step 4: Implement `detect_apple_model.sh`** to read `/sys/class/dmi/id/{sys_vendor,product_name,board_name,bios_vendor}`, EFI presence, and architecture, then invoke the Python core with no manual model override.
- [ ] **Step 5: Re-run tests** and require PASS.
- [ ] **Step 6: Commit** `feat: add Apple Intel hardware detection`.

### Task 2: Read-only Apple preflight and diagnostics

**Files:**
- Create: `APPLE_INTEL/lib/apple_preflight.py`
- Create: `APPLE_INTEL/hardware/preflight_mac.sh`
- Create: `APPLE_INTEL/hardware/diagnostics_mac.sh`
- Create: `APPLE_INTEL/tests/test_preflight_policy.py`

**Interfaces:**
- Consumes normalized Apple identity from Task 1.
- Produces: `evaluate_preflight(identity, disks, source_disk, capabilities, power) -> dict` with `ok`, `fatal`, `warnings`, `target`, and `checks`.

- [ ] **Step 1: Write failing policy tests** for one safe internal disk, ambiguous internal disks, USB/source collision, non-amd64, missing EFI, unknown Apple profile, and optional-device warnings.
- [ ] **Step 2: Run** `python3 -m unittest APPLE_INTEL.tests.test_preflight_policy -v` and confirm failures.
- [ ] **Step 3: Implement pure preflight policy** where disk ambiguity/source collisions are fatal while Wi-Fi/audio/sleep gaps are warnings.
- [ ] **Step 4: Implement `preflight_mac.sh`** to gather `lsblk -J`, source mount ancestry, power state, `lspci`, `/proc/bus/input/devices`, network interfaces, and audio visibility; emit human text plus JSON at `/run/synapse/apple-preflight.json`.
- [ ] **Step 5: Implement `diagnostics_mac.sh`** as non-destructive reporting for GPU, Broadcom Wi-Fi, input, audio, Apple SMC, battery and suspend capability.
- [ ] **Step 6: Re-run tests** and shell syntax checks.
- [ ] **Step 7: Commit** `feat: add Apple Intel preflight and diagnostics`.

### Task 3: Installer and EFI recovery wrappers around GENESIS

**Files:**
- Create: `APPLE_INTEL/INSTALL_SYNAPSE_MAC.sh`
- Create: `APPLE_INTEL/INSTALL_SYNAPSE_MAC.command`
- Create: `APPLE_INTEL/RECOVER_SYNAPSE_MAC.sh`
- Create: `APPLE_INTEL/RECOVER_SYNAPSE_MAC.command`
- Create: `APPLE_INTEL/boot/apple_efi_install.sh`
- Create: `APPLE_INTEL/boot/emergency_efi_boot.sh`
- Create: `APPLE_INTEL/boot/grub_apple.cfg`
- Create: `APPLE_INTEL/tests/test_shell_contracts.py`

**Interfaces:**
- Installer must run Apple preflight first and refuse on nonzero preflight.
- Destructive install delegates to existing GENESIS flow; it does not implement a second partition writer.
- EFI recovery accepts explicit `--esp` and `--root` arguments and refuses omitted/ambiguous targets.

- [ ] **Step 1: Write failing shell-contract tests** asserting strict mode, preflight invocation before install, no hardcoded `/dev/sda`, explicit destructive confirmation, `grub-install --target=x86_64-efi`, `--removable`, and `--no-nvram`.
- [ ] **Step 2: Run tests** and confirm missing-file failures.
- [ ] **Step 3: Implement installer launchers.** `INSTALL_SYNAPSE_MAC.sh` requires `synapse.genesis=1`, Apple preflight PASS, then launches/points to the installed GENESIS control surface rather than bypassing its arm/challenge safeguards.
- [ ] **Step 4: Implement EFI repair** using mounted explicit ESP/root, root UUID lookup, fallback `EFI/BOOT/BOOTX64.EFI`, and a Synapse GRUB config. Never modify Apple firmware/NVRAM.
- [ ] **Step 5: Implement `.command` wrappers** that resolve their own directory and exec the corresponding `.sh` script.
- [ ] **Step 6: Run shell tests and `bash -n` / `sh -n`.**
- [ ] **Step 7: Commit** `feat: add Apple Intel install and EFI recovery flow`.

### Task 4: Experimental Apple Bridge inspector

**Files:**
- Create: `APPLE_INTEL/apple-bridge/inspect_macho.py`
- Create: `APPLE_INTEL/apple-bridge/compatibility_report.py`
- Create: `APPLE_INTEL/apple-bridge/inspect_app.sh`
- Create: `APPLE_INTEL/apple-bridge/launch_app.sh`
- Create: `APPLE_INTEL/apple-bridge/README.md`
- Create: `APPLE_INTEL/tests/test_apple_bridge.py`

**Interfaces:**
- `inspect_macho(path) -> dict` returns validity, endian, bits, CPU architecture, file type, and dependency names.
- `inspect_bundle(app_path) -> dict` resolves `Contents/Info.plist` `CFBundleExecutable` without execution.
- `compatibility_report(app_path) -> dict` returns `native-tool|experimental|unsupported`, reasons, recognized dependencies, and missing dependencies.

- [ ] **Step 1: Write failing tests** with synthetic 64-bit x86_64 Mach-O headers/load commands, malformed binaries, wrong architecture, temporary `.app` bundles, and missing dependencies.
- [ ] **Step 2: Run** `python3 -m unittest APPLE_INTEL.tests.test_apple_bridge -v` and confirm failures.
- [ ] **Step 3: Implement bounded Mach-O parsing** for magic/header plus dylib load-command names. Reject unsupported/FAT formats explicitly rather than guessing.
- [ ] **Step 4: Implement bundle resolution and deterministic classification.** No proprietary framework emulation.
- [ ] **Step 5: Implement `inspect_app.sh` and opt-in `launch_app.sh`.** Launch is allowed only for a report that explicitly marks an executable path and experimental/native-tool attempt; capture exit status and never equate process spawn with compatibility.
- [ ] **Step 6: Re-run tests** and require PASS.
- [ ] **Step 7: Commit** `feat: add experimental Synapse Apple Bridge inspector`.

### Task 5: Driver policy docs and live-image packaging

**Files:**
- Create: `APPLE_INTEL/README.md`
- Create: `APPLE_INTEL/START_HERE_MAC.md`
- Create: `APPLE_INTEL/drivers/README.md`
- Create: `APPLE_INTEL/drivers/wifi/README.md`
- Create: `APPLE_INTEL/drivers/keyboard-trackpad/README.md`
- Create: `APPLE_INTEL/drivers/audio/README.md`
- Create: `APPLE_INTEL/drivers/graphics/README.md`
- Create: `APPLE_INTEL/drivers/applesmc/README.md`
- Create: `APPLE_INTEL/drivers/power-sleep/README.md`
- Create: `build/hooks/040-apple-intel.hook.chroot`
- Modify: `build/build.sh`
- Modify: `Makefile`
- Create: `tests/test_apple_intel_packaging.py`

**Interfaces:**
- Live amd64 image contains `/usr/share/synapse/apple-intel/` byte-for-byte from source.
- Hook exposes `/usr/local/bin/synapse-apple-preflight`, `synapse-apple-diagnostics`, and `synapse-apple-install` symlinks.

- [ ] **Step 1: Write failing packaging tests** asserting build script copies `APPLE_INTEL`, hook creates launchers, and Makefile syntax-checks Apple scripts.
- [ ] **Step 2: Run packaging tests** and confirm failures.
- [ ] **Step 3: Add documentation** with Option-key boot flow, live-hardware acceptance checklist, Broadcom warning, and explicit statement that physical certification is pending.
- [ ] **Step 4: Integrate live-image copy** only for amd64 where appropriate; preserve all existing rootfs and GALLOP copies.
- [ ] **Step 5: Add hook and Makefile lint coverage.**
- [ ] **Step 6: Re-run Apple tests plus existing hardware/GENESIS tests.**
- [ ] **Step 7: Commit** `build: package Apple Intel target in Synapse live image`.

### Task 6: Verification gate

**Files:** no new production files unless a test exposes a defect.

- [ ] **Step 1: Run** `PYTHONPATH=src:. python3 -m unittest discover -s APPLE_INTEL/tests -v`.
- [ ] **Step 2: Run** `PYTHONPATH=src:. python3 -m unittest tests.test_hardware tests.test_genesis tests.test_genesis_writer -v`.
- [ ] **Step 3: Run shell syntax checks** for every `.sh` and `.command` under `APPLE_INTEL/` plus `build/hooks/040-apple-intel.hook.chroot`.
- [ ] **Step 4: Run** `SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=amd64 ./build/build.sh` to verify the build path still resolves.
- [ ] **Step 5: Inspect git diff / committed tree** and confirm no GALLOP/Chromebook files were deleted or behavior silently relaxed.
- [ ] **Step 6: Record actual status:** repository/VM checks may pass, but physical Mac support remains unverified until real hardware acceptance and cold boot.
