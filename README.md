# Synapse OS 🧠⚡

**A Cory-tuned Linux workstation built around low-latency interaction, local AI, creative engineering, and the COSMOS/CST ecosystem.**

Synapse OS is a reproducible Debian-based live/installable operating-system project. It does **not** claim literal faster-than-light computation; instead, “FTL” is the engineering theme for reducing *human-visible latency*: fast boot, responsive desktop behavior, compressed-memory swap, hardware-aware power profiles, local-first tools, and a single command surface for COSMOS services.

> Status: **Nebula alpha**. `amd64` is the required VM-certified build path. `arm64` and `riscv64` have architecture-aware build/QEMU machinery and remain explicitly **experimental** until their promotion gates pass. The ASUS Chromebook CX1700CKA / `GALLOP` is Reference Hardware #1 and remains a physical certification target until the real-device checklist passes.

## What is real in this repository

- Bootable/installable **Debian 13 (trixie) amd64 live ISO recipe** with required QEMU guest gate
- Architecture registry and build profiles for **amd64 / arm64 / riscv64**
- Manual ARM64 and RISC-V full-image/QEMU promotion workflow
- Architecture-specific Debian kernel selection and foreign-bootstrap configuration
- **Stable C ABI v1** compiled natively inside each generated image
- C, C++, Rust, and Python SDK surfaces over the same native contract
- KDE Plasma desktop + Wayland-capable stack
- **Synapse Nebula visual system**: cosmic wallpaper, boot splash, login theme, application iconography and dark defaults
- **Native Synapse Control GUI** for system status, performance profiles, COSMOS status and recovery launchers
- Calamares graphical installer
- PipeWire + WirePlumber audio stack
- zram compressed swap configuration
- `power-profiles-daemon` integration
- Synapse telemetry agent (`synapse-agent.service`)
- `synapse` system CLI: status, doctor, profiles, COSMOS probes, benchmark, `.syn` plans
- COSMOS port map for 11434 / 11435 / 11501 / 8765 / 8081 / 8090
- Phone Bootstrap local API/UI for authenticated laptop discovery and COSMOS installation
- Hardware certification registry with `GALLOP` as the first physical target
- Local validation via `make check`
- GitHub Actions ISO build + generated-filesystem verification + QEMU guest smoke test
- Recovery, hardware, architecture, install, performance, and UI manuals

## Compatibility model

Synapse separates **language compatibility**, **architecture buildability**, **VM certification**, and **physical hardware certification** so a source port is never mislabeled as a proven boot target.

| Target | State |
|---|---|
| C ABI v1 | required local/CI gate |
| C++ adapter | required local/CI gate |
| Rust adapter | required CI gate when Rust toolchain is present |
| Python adapter | required local/CI gate |
| amd64 image | `vm-certified` required gate |
| arm64 image | `experimental` promotion gate |
| riscv64 image | `experimental` promotion gate |
| ASUS CX1700CKA / GALLOP | `physical-target` |

See [`docs/ARCHITECTURES.md`](docs/ARCHITECTURES.md) and [`docs/HARDWARE_CERTIFICATION.md`](docs/HARDWARE_CERTIFICATION.md).

## Universal native ABI

The portable language boundary is `sdk/c/`:

```text
               Synapse C ABI v1
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        C            C++           Rust
        │                           │
        └─────────────┬─────────────┘
                      │
                   Python
                  (ctypes)
```

The ABI exposes version discovery, opaque status-file reads, and timed service reachability. C++ and Rust wrap it with safer language-native APIs; Python uses the ABI when installed and retains a pure-Python development fallback. No architecture-specific SDK binary is committed to Git.

## Nebula UI

The shell follows one rule: **cosmic outside, familiar inside**.

A Windows user should immediately recognize the desktop pattern: application launcher, bottom panel, file manager, settings, terminal, system tray and large obvious launchers. The Synapse layer adds the personality without replacing normal Linux navigation.

### Synapse Control

Launch **Synapse Control** from the application menu or desktop. It provides four friendly surfaces:

- **Overview** — CPU, RAM, storage, network, kernel and COSMOS reachability
- **Performance** — `balanced`, `pulse`, `quiet`, `auto`, plus a same-hardware microbenchmark
- **COSMOS** — live reachability for the local COSMOS service map
- **Recovery** — system doctor, KDE settings, installer and terminal launch points

The visual stack includes:

```text
GRUB      → Synapse Nebula installed-system boot theme
Plymouth  → SYNAPSE OS / NEBULA // CST graphical boot splash
SDDM      → cosmic login greeter
Plasma    → dark familiar desktop + Synapse vector wallpaper
Control   → native PyQt 6 Synapse system dashboard
```

See [`docs/UI.md`](docs/UI.md).

## One-command developer validation

```bash
make check
```

This validates the Python control plane, Nebula UI source syntax/assets, C ABI, C++ adapter, Python adapter, Rust adapter when Cargo is available, architecture registry, dry-run build profiles, and QEMU command profiles.

## Build an image

On a Debian-family amd64 build host:

```bash
sudo apt-get update
sudo apt-get install -y live-build debootstrap rsync xorriso squashfs-tools
sudo env SYNAPSE_ARCH=amd64 ./build/build.sh
```

Architecture configuration can be inspected without root or a full build:

```bash
SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=amd64 ./build/build.sh
SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=arm64 ./build/build.sh
SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=riscv64 ./build/build.sh
```

Foreign ARM64/RISC-V image generation requires the matching `qemu-*-static` emulator. Full experimental promotion is defined in `.github/workflows/experimental-arch-vm.yml`.

See [`docs/BUILD.md`](docs/BUILD.md), [`docs/INSTALL.md`](docs/INSTALL.md), and [`docs/ARCHITECTURES.md`](docs/ARCHITECTURES.md).

## VM certification path

The hosted workflow deliberately separates “the image exists” from “the OS booted.”

```text
SOURCE + SDK CHECKS
    ↓
BUILD FULL IMAGE
    ↓
VERIFY SHA-256
    ↓
OPEN filesystem.squashfs
    ↓
VERIFY SYNAPSE + NATIVE ABI + PLASMA + CALAMARES + UI ASSETS
    ↓
BOOT KERNEL/INITRAMFS IN ARCH-SPECIFIC QEMU
    ↓
RUN IN-GUEST SYNAPSE SMOKE TEST
    ↓
SYNAPSE_VM_READY
```

The guest verifies Synapse OS identity, CLI, native ABI, hardware detector, Control dependencies, Plasma, Calamares, PipeWire, NetworkManager, Python package, system services and Nebula theme assets.

## Phone Bootstrap

The authenticated local bootstrap daemon listens on port `8787` when enabled. The phone UI can connect over a trusted routed USB/local link, identify the laptop, send the `hey, I'm here` handshake, and start the fixed-purpose COSMOS install/service activation job.

See [`PHONE_BOOTSTRAP.md`](PHONE_BOOTSTRAP.md) and [`phone-bootstrap/README.md`](phone-bootstrap/README.md).

## The Synapse command surface

```bash
synapse status
synapse doctor
synapse profile get
synapse profile set pulse
synapse cosmos probe
synapse bench
synapse apply /usr/share/synapse/examples/pulse.syn
```

### Profiles

| Profile | Intent | PowerProfiles mapping |
|---|---|---|
| `pulse` | plugged-in / compilation / creative burst | `performance` |
| `balanced` | default daily workstation | `balanced` |
| `quiet` | battery / thermals / focus | `power-saver` |
| `auto` | AC→balanced, battery→quiet | adaptive |

Synapse deliberately avoids brittle “magic” kernel hacks that can make one laptop benchmark faster while breaking another. Hardware-specific tuning belongs behind detected capabilities and explicit evidence.

## COSMOS bridge

Synapse OS knows the project service map without owning or rewriting COSMOS:

| Service | Port |
|---|---:|
| Ollama | 11434 |
| Helper brain | 11435 |
| Native/CST bridge | 11501 |
| Emotional/sensory API | 8765 |
| COSMOS web | 8081 |
| COSMOS web fallback | 8090 |

`synapse cosmos probe` performs local TCP reachability only. This keeps the OS layer non-destructive and lets the existing COSMOS runtime remain its own lineage.

## Synapse Flow language

A tiny declarative control language lives in [`language/`](language/). Example:

```text
SYNAPSE/1
profile pulse
cosmos probe
service check NetworkManager
```

It is intentionally constrained: `.syn` plans cannot execute arbitrary shell commands. That makes them shareable system intentions rather than disguised scripts.

## Repository map

```text
.github/      required amd64 CI + experimental architecture promotion gates
build/        live-build image recipe, architecture registry and hooks
hardware/     evidence-based physical hardware profiles
rootfs/       files injected into the live/installed system
src/          Synapse Python control plane and hardware detection
language/     .syn specification and examples
sdk/c/        stable native ABI v1
sdk/cpp/      C++ wrapper
sdk/rust/     safe Rust wrapper
sdk/python/   Python native/fallback wrapper
tests/        unit tests
scripts/      repository, architecture and QEMU validation helpers
docs/         engineering and user manuals
```

## Performance philosophy

The target is *latency you can feel*: avoiding disk swap where possible, using compressed RAM, maintaining sane power/thermal policy, keeping audio modern, and making local AI/service state observable. No software can transmit information or execute physical computation faster than light; the name is a performance metaphor, not a physics claim.

## Safety

Installing an OS can overwrite existing storage if the installer is instructed to do so. Test the live environment first, keep backups, verify the SHA-256 checksum, and read the recovery guide. Hardware-specific proprietary GPU drivers are not silently forced into the image. Firmware/write-protection changes are not automated by Phone Bootstrap.

## License

Synapse-specific original code is MIT licensed. The generated image contains Debian and third-party packages under their own licenses. See [`docs/LICENSING.md`](docs/LICENSING.md).
