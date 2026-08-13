# Synapse OS 🧠⚡

**A Cory-tuned Linux workstation built around low-latency interaction, local AI, creative engineering, and the COSMOS/CST ecosystem.**

Synapse OS is a reproducible Debian-based live/installable operating-system project. It does **not** claim literal faster-than-light computation; instead, “FTL” is the engineering theme for reducing *human-visible latency*: fast boot, responsive desktop behavior, compressed-memory swap, hardware-aware power profiles, local-first tools, and a single command surface for COSMOS services.

> Status: **0.1.0-alpha.1 — Nebula**. The repo can validate its control plane now and is structured to build an amd64 hybrid live ISO with Debian `live-build`.

## What is real in this repository

- Bootable/installable **Debian 13 (trixie) amd64 live ISO recipe**
- KDE Plasma desktop + Wayland-capable stack
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
- Recovery, hardware, architecture, install, and performance manuals

> Hosted GitHub Actions automation is **not included in this commit**. The OS source and local validation are present; the hosted CI/release workflow remains a separate follow-up.

## One-command developer validation

```bash
make check
```

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

`synapse cosmos probe` performs local TCP reachability only. This keeps the OS layer non-destructive and lets your existing COSMOS runtime remain its own lineage.

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
build/       live-build ISO recipe and hooks
rootfs/      files injected into the live/installed system
src/         Synapse Python control plane
language/    .syn specification and examples
sdk/         Python / C++ / Rust integration surfaces
tests/       unit tests
scripts/     repository validation helpers
docs/        engineering and user manuals
```

## Performance philosophy

The target is *latency you can feel*: avoiding disk swap where possible, using compressed RAM, maintaining sane power/thermal policy, keeping audio modern, and making local AI/service state observable. No software can transmit information or execute physical computation faster than light; the name is a performance metaphor, not a physics claim.

## Safety

Installing an OS can erase data. Test the live environment first, keep backups, verify the SHA-256 checksum, and read the recovery guide. Hardware-specific proprietary GPU drivers are not silently forced into the image.

## License

Synapse-specific original code is MIT licensed. The generated ISO contains Debian and third-party packages under their own licenses. See [`docs/LICENSING.md`](docs/LICENSING.md).
