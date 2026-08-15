# Synapse Universal Boot Matrix Design

## Goal

Make Synapse OS architecture-aware for Debian 13 `amd64`, `arm64`, and `riscv64` while certifying only architectures and hardware that have passed explicit boot gates.

## Source of truth

`build/architectures.json` defines each architecture's Debian name, normalized runtime aliases, kernel package, QEMU system binary, virtual machine, CPU model, serial console, foreign-bootstrap emulator, and support state.

Initial states:

- `amd64`: `vm-certified`; physical certification target is ASUS CX1700CKA / ChromeOS board `GALLOP`.
- `arm64`: `experimental`; build and QEMU boot machinery is present but not labeled certified until its gate passes.
- `riscv64`: `experimental`; build and QEMU boot machinery is present but not labeled certified until its gate passes.

## Build behavior

`build/build.sh` accepts `SYNAPSE_ARCH=amd64|arm64|riscv64`, rejects unknown architectures, injects the architecture-specific Debian kernel metapackage into the generated live-build configuration, and uses live-build's foreign-bootstrap QEMU options when the target differs from the build host.

No precompiled SDK binaries are stored in Git. Native components are compiled inside the target image.

## VM boot gate

`scripts/qemu-smoke.sh` owns architecture-specific QEMU command construction. It extracts `/live/vmlinuz` and `/live/initrd.img`, starts the image with the architecture's virtual machine/CPU/console settings, and waits for the existing `SYNAPSE_VM_READY` marker emitted by the in-guest smoke service.

The normal CI workflow keeps `amd64` as the required build/boot gate. A separate manually dispatchable workflow performs full experimental `arm64` or `riscv64` build + QEMU boot tests. Passing one of those gates is the prerequisite to changing its support state to `vm-certified`.

## Hardware certification

`hardware/profiles.json` is a machine-readable certification registry. Each profile records architecture, board/HWID match tokens, state, and notes. `src/synapse/hardware.py` probes runtime architecture, DMI identity, and ChromeOS HWID when exposed, then reports the best matching profile.

The first physical target is `asus-cx1700cka-gallop`. Its initial state is `physical-target`; it does not become `physical-certified` until Synapse OS boots and the hardware acceptance checklist passes on the actual laptop.

## Phone Bootstrap integration

`GET /v1/device` includes normalized architecture and hardware-profile information so the phone UI can show whether a connected laptop is a known target, VM-certified architecture, experimental architecture, or unknown platform.

## Safety and correctness

- The architecture registry never claims unrun tests passed.
- Firmware flashing is not part of this build matrix.
- Phone Bootstrap does not receive raw-disk or firmware endpoints.
- Unknown hardware remains usable as generic Linux hardware but is labeled `unverified`.
