# Synapse OS Apple Intel Target Design

Date: 2026-08-20
Status: Approved design, pending implementation plan
Target repository: `NavisWORLD/Synapse-os-`

## Goal

Add a dedicated `APPLE_INTEL/` subsystem for 2014-2015 Intel MacBook Pro hardware while preserving the existing Chromebook/GALLOP installation path. The subsystem has two layers:

1. A native Synapse OS Apple hardware target for boot, installation, recovery, hardware detection, preflight, and diagnostics.
2. An experimental Apple Bridge for inspecting macOS `.app` bundles and classifying whether a given x86_64 Mach-O application is potentially runnable, experimental, or unsupported.

The first implementation target is pre-T2, non-Touch-Bar Intel MacBook Pro hardware from the 2014-2015 generation.

## Non-goals

- Do not claim general macOS application compatibility.
- Do not emulate macOS or redistribute Apple proprietary frameworks.
- Do not bypass Apple code-signing, DRM, notarization, licensing, or platform security controls.
- Do not replace or modify the existing GALLOP/Chromebook installer flow.
- Do not perform destructive installation until Apple-target preflight has passed and the user explicitly confirms the selected internal disk.

## Repository Layout

```text
APPLE_INTEL/
├── README.md
├── START_HERE_MAC.md
├── INSTALL_SYNAPSE_MAC.command
├── INSTALL_SYNAPSE_MAC.sh
├── RECOVER_SYNAPSE_MAC.command
├── RECOVER_SYNAPSE_MAC.sh
├── hardware/
│   ├── detect_apple_model.sh
│   ├── apple_intel_profiles.json
│   ├── preflight_mac.sh
│   └── diagnostics_mac.sh
├── drivers/
│   ├── README.md
│   ├── wifi/
│   ├── keyboard-trackpad/
│   ├── audio/
│   ├── graphics/
│   ├── applesmc/
│   └── power-sleep/
├── boot/
│   ├── apple_efi_install.sh
│   ├── grub_apple.cfg
│   └── emergency_efi_boot.sh
├── apple-bridge/
│   ├── README.md
│   ├── inspect_app.sh
│   ├── inspect_macho.py
│   ├── compatibility_report.py
│   └── launch_app.sh
└── tests/
    ├── test_detect_apple_model.py
    ├── test_apple_profiles.py
    ├── test_preflight_policy.py
    └── test_apple_bridge.py
```

Empty driver-category directories may be represented by documentation files until a tested implementation exists.

## Architecture

### 1. Hardware identification

`hardware/detect_apple_model.sh` provides one normalized hardware identity record using Linux-visible firmware and DMI data. It must not rely on the user typing a model manually when the machine can expose one.

Expected normalized fields:

- `vendor`
- `product_name`
- `board_name`
- `bios_vendor`
- `architecture`
- `efi_present`
- `profile_id`
- `support_state`

`apple_intel_profiles.json` contains the supported model/profile policy. The initial profile family is pre-T2 Intel MacBook Pro 2014-2015, non-Touch-Bar.

Unknown Apple hardware is not silently treated as supported. It receives an explicit `unknown` or `experimental` support state.

### 2. Apple preflight

`hardware/preflight_mac.sh` is a read-only gate. It verifies at minimum:

- x86_64/amd64 architecture
- EFI boot availability
- Apple hardware identity
- recognized or explicitly experimental profile
- one intended internal install target
- source USB is not the install target
- AC/battery state is safe enough for installation
- kernel sees display/GPU
- keyboard and pointing-device visibility
- internal storage visibility
- network interface visibility
- audio-device visibility

A missing optional device may produce a warning. A condition that risks selecting the wrong disk or producing a non-bootable install is fatal.

Preflight emits both human-readable output and a machine-readable result so later installer logic can consume the same policy without parsing prose.

### 3. Installation flow

The Apple installer wraps the existing Synapse amd64 payload rather than creating a second OS distribution.

Flow:

```text
Synapse USB
  -> Apple EFI Startup Manager (Option key)
  -> EFI Boot
  -> Synapse live environment
  -> Apple hardware detection
  -> Apple preflight
  -> explicit destructive confirmation
  -> partition/install existing Synapse payload
  -> install/repair x86_64 EFI boot entry
  -> write installation receipt
  -> reboot test
```

`INSTALL_SYNAPSE_MAC.command` is a convenience launcher for environments that support Finder-style `.command` execution. `INSTALL_SYNAPSE_MAC.sh` contains the actual shell implementation.

The installer must never infer a destructive target from `/dev/sda` or similar naming alone. Target identity must be based on discovered hardware properties and explicit confirmation.

### 4. EFI boot support

`boot/apple_efi_install.sh` installs or repairs the Synapse EFI boot path using the repository's existing amd64/GRUB assumptions. It should prefer a standards-compliant removable/fallback EFI path when appropriate and maintain a Synapse-specific GRUB configuration.

`emergency_efi_boot.sh` is recovery-only. It repairs boot files from a live USB without reinstalling the root filesystem.

No Apple firmware modification is part of this subsystem.

### 5. Driver support model

The `drivers/` tree is a policy and integration layer, not a repository for copied proprietary Apple binaries.

Initial categories:

- Wi-Fi: detect Broadcom-class devices and report whether the live image has a compatible driver/firmware path.
- Keyboard/trackpad: verify Linux input devices and surface missing support clearly.
- Audio: detect codec/device visibility and basic ALSA/PipeWire presence.
- Graphics: verify the Intel GPU path and framebuffer/DRM availability.
- Apple SMC: detect thermal/battery/fan telemetry availability where Linux exposes it.
- Power/sleep: validate suspend capability only after boot succeeds; sleep failure must not block first installation unless it threatens filesystem integrity.

The first release may classify some device classes as `experimental` rather than claiming support.

## Apple Bridge

### Purpose

The Apple Bridge is an application-inspection and compatibility-classification subsystem. It is separate from boot/install code so failures cannot affect OS startup.

### Inspection pipeline

```text
.app bundle
  -> validate bundle structure
  -> locate executable from Info.plist
  -> inspect Mach-O header
  -> identify CPU architecture
  -> enumerate linked dylibs/framework references
  -> compare against locally available compatibility capabilities
  -> emit compatibility report
```

`inspect_macho.py` must parse enough Mach-O metadata to identify at least file type, CPU architecture, and load-command dependency names without executing the target application.

`compatibility_report.py` produces a stable report with:

- bundle path
- executable path
- architecture
- Mach-O validity
- dependency count
- dependencies recognized locally
- dependencies missing
- classification: `native-tool`, `experimental`, or `unsupported`
- reasons

### Launch policy

`launch_app.sh` is opt-in and only attempts execution when the compatibility report permits an experimental launch path. It must not claim success based only on process creation; the exit status and runtime diagnostics are captured.

The bridge does not provide Apple proprietary frameworks. If a required framework is unavailable, the report states that clearly.

## Error Handling

All destructive scripts use strict shell error handling and stop on unresolved ambiguity.

Fatal installation conditions include:

- not running on x86_64
- EFI unavailable
- no safe internal target
- multiple ambiguous internal targets
- source USB and target identity collision
- insufficient target capacity
- failed bootloader installation
- failed root filesystem verification

Hardware feature gaps such as Wi-Fi, audio, sleep, or camera are recorded individually instead of being collapsed into a generic failure.

Apple Bridge inspection errors never modify the `.app` bundle and never affect system installation state.

## Testing Strategy

Implementation follows test-first development.

Tests cover:

- hardware-profile normalization from representative DMI fixtures
- rejection of unknown/non-Apple hardware as supported hardware
- preflight rejection of ambiguous or unsafe target disks
- preflight acceptance of a representative supported Apple fixture
- Apple profile JSON schema/required fields
- Mach-O parser behavior using synthetic/minimal binary fixtures
- `.app` bundle executable resolution using temporary test bundles
- compatibility classification for supported, missing-dependency, and wrong-architecture cases
- shell syntax checks for all `.sh` and `.command` files

No test may perform a real destructive disk write. Installer write logic must be exercised using temporary files, loopback/disposable virtual disks, or existing project VM mechanisms before any physical-hardware claim is made.

## Compatibility and Isolation

The new subsystem is additive. Existing paths such as `USB_INSTALL_READY/`, GENESIS, GALLOP profiles, and Chromebook tooling remain unchanged unless a shared interface must be extended. Any shared extension must remain backward compatible and be covered by regression tests.

The existing Synapse amd64 ISO remains the source payload. Apple support should be integrated into the build only after the standalone Apple subsystem passes unit and VM-level validation.

## Success Criteria

Phase 1 is complete when:

1. The repository contains the documented `APPLE_INTEL/` structure.
2. Apple model/profile detection is tested and deterministic.
3. Preflight safely distinguishes supported/experimental/unsupported hardware and unsafe install targets.
4. Apple EFI install/recovery scripts are present and syntax-tested.
5. A live Synapse USB can use the Apple preflight without modifying the disk.
6. Apple Bridge can inspect a local x86_64 `.app` bundle and emit a deterministic compatibility report without executing it.
7. Existing GALLOP/Chromebook tests remain unaffected.

Physical-hardware support is not declared complete until a real 2014-2015 Intel MacBook Pro successfully boots the live USB, passes hardware acceptance checks, installs to a disposable/wiped internal target, cold-boots from internal storage, and records the hardware results.

## Future Extension Boundary

After the initial MacBook Pro generation is validated, additional Intel Mac models may be added as new explicit profiles. Apple Silicon is out of scope for this design and requires a separate architecture because its boot chain, architecture, and hardware support model differ materially.
