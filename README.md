# Synapse OS 🧠⚡

**A Cory-tuned Linux workstation built around low-latency interaction, local AI, creative engineering, and the COSMOS/CST ecosystem.**

Synapse OS is a reproducible Debian-based live/installable operating-system project. It does **not** claim literal faster-than-light computation; instead, “FTL” is the engineering theme for reducing *human-visible latency*: fast boot, responsive desktop behavior, compressed-memory swap, hardware-aware power profiles, local-first tools, and a single command surface for COSMOS services.

> Status: **0.1.0-alpha.1 — Nebula**. The project builds an amd64 hybrid live ISO with Debian `live-build`, validates the generated live filesystem, and includes a QEMU guest boot gate before the image should be considered ready for physical installation.

## What is real in this repository

- Bootable/installable **Debian 13 (trixie) amd64 live ISO recipe**
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
- Safe `pulse`, `balanced`, `quiet`, and `auto` performance profiles
- Synapse Flow `.syn` declarative control language
- Python, C++, and Rust SDK surfaces
- Local validation via `make check`
- GitHub Actions ISO build + generated-filesystem verification + QEMU guest smoke test
- Recovery, hardware, architecture, install, performance, and UI manuals

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

This validates the Python control plane, Nebula UI source syntax/assets, shell scripts, C++ SDK example and Rust SDK when Cargo is available.

## Build the ISO

On a Debian-family amd64 build host:

```bash
sudo apt-get update
sudo apt-get install -y live-build debootstrap rsync xorriso squashfs-tools
sudo ./build/build.sh
```

Expected output:

```text
out/SynapseOS-0.1.0-alpha.1-amd64.iso
out/SynapseOS-0.1.0-alpha.1-amd64.iso.sha256
```

See [`docs/BUILD.md`](docs/BUILD.md) and [`docs/INSTALL.md`](docs/INSTALL.md) before installing to physical hardware.

## VM certification path

The hosted workflow deliberately separates “the ISO exists” from “the OS booted.”

```text
SOURCE CHECKS
    ↓
BUILD FULL ISO
    ↓
VERIFY SHA-256
    ↓
OPEN filesystem.squashfs
    ↓
VERIFY SYNAPSE + PLASMA + CALAMARES + UI ASSETS
    ↓
BOOT KERNEL/INITRAMFS IN QEMU WITH THE ISO AS LIVE MEDIA
    ↓
RUN IN-GUEST SYNAPSE SMOKE TEST
    ↓
SYNAPSE_VM_READY
```

The guest verifies Synapse OS identity, the CLI, native Control application dependencies, Plasma, Calamares, PipeWire, NetworkManager, the Synapse Python package, system services and Nebula theme assets. A physical-laptop install should wait until this chain is green.

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

Synapse deliberately avoids brittle “magic” kernel hacks that can make one laptop benchmark faster while breaking another. Hardware-specific tuning belongs behind detected capabilities and explicit user choice.

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
.github/      hosted ISO + VM validation
build/        live-build ISO recipe and hooks
rootfs/       files injected into the live/installed system
src/          Synapse Python control plane
language/     .syn specification and examples
sdk/          Python / C++ / Rust integration surfaces
tests/        unit tests
scripts/      repository validation helpers
docs/         engineering and user manuals
```

## Performance philosophy

The target is *latency you can feel*: avoiding disk swap where possible, using compressed RAM, maintaining sane power/thermal policy, keeping audio modern, and making local AI/service state observable. No software can transmit information or execute physical computation faster than light; the name is a performance metaphor, not a physics claim.

## Safety

Installing an OS can overwrite existing storage if the installer is instructed to do so. Test the live environment first, keep backups, verify the SHA-256 checksum, and read the recovery guide. Hardware-specific proprietary GPU drivers are not silently forced into the image.

## License

Synapse-specific original code is MIT licensed. The generated ISO contains Debian and third-party packages under their own licenses. See [`docs/LICENSING.md`](docs/LICENSING.md).
