# Synapse OS Architecture

## Layer model

1. **Linux substrate** — Debian 13 userspace and Debian kernel packages.
2. **Desktop plane** — KDE Plasma, SDDM, NetworkManager, PipeWire/WirePlumber.
3. **Responsiveness plane** — zram, power profile integration, conservative sysctl settings.
4. **Synapse control plane** — Python CLI + read-mostly telemetry agent.
5. **COSMOS bridge plane** — local service discovery/probing only; no mutation of COSMOS state.
6. **Language/SDK plane** — `.syn` declarations plus Python/C++/Rust surfaces.

## Why this is not a forked kernel yet

A custom kernel is only useful when it has measured hardware-specific wins and a maintenance plan. Version 0.1 keeps the kernel mainstream and moves experimentation into observable, reversible userspace policies. A later kernel flavor can be added behind benchmark gates.

## Agent data path

`synapse-agent.service` samples local machine state and atomically publishes JSON at:

```text
/run/synapse/status.json
```

It does not send telemetry off the laptop. SDKs read this file locally.

## COSMOS relationship

Synapse OS does not bundle private weights, memories, secrets, or `.env` files. It only knows the expected localhost service ports, so existing COSMOS installations can attach without being absorbed into the OS repository.
