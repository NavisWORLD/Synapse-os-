# Synapse OS Nebula UI

Synapse OS follows a **cosmic outside, familiar inside** design rule: the visual identity is unmistakably Synapse/CST, while navigation stays close to a conventional desktop so a Windows user can quickly find files, settings, apps, recovery and installation.

## Visual language

- Deep-space navy and black surfaces
- Cyan and violet neural-line accents
- Soft white and gold highlights
- Rounded, readable control surfaces
- Dark Breeze-compatible application styling
- Synapse node emblem for OS-owned launchers
- Nebula wallpaper with a central CST/synapse graph

The visual layer is branding, not a scientific visualization or a faster-than-light computation claim.

## Desktop navigation

KDE Plasma provides the familiar shell foundation: a bottom taskbar and application launcher, Dolphin file manager, KDE System Settings, Konsole terminal, and standard network/audio/power controls.

Synapse adds prominent entries for **Synapse Control**, **COSMOS**, **Synapse Recovery**, and **Install Synapse OS**.

## Synapse Control

`/usr/local/bin/synapse-control` is a native PyQt 6 application layered over the existing Synapse control plane.

### Overview

Shows CPU, RAM, root filesystem usage, active network interfaces, kernel information and COSMOS reachability.

### Performance

Exposes `balanced`, `pulse`, `quiet`, and `auto` profiles plus the Synapse microbenchmark. The benchmark is a same-hardware comparison tool.

### COSMOS

Probes the local service map on ports 11434, 11435, 11501, 8765, 8081 and 8090.

### Recovery

Provides simple launch points for `synapse doctor`, KDE System Settings, Calamares and Konsole.

## Boot and login branding

The image contains three coordinated layers:

1. **GRUB theme** for installed-system boot selection.
2. **Plymouth theme** for the `SYNAPSE OS / NEBULA // CST` graphical splash.
3. **SDDM theme** for the cosmic Synapse login greeter.

The live-build hook selects the Synapse SDDM and Plymouth themes and configures the installed GRUB theme while preserving normal Linux recovery paths.

## Wallpaper

The default vector wallpaper is `/usr/share/wallpapers/SynapseOS/contents/images/3840x2160.svg` so it remains sharp across laptop and external-monitor resolutions.

## VM validation contract

The GitHub Actions pipeline checks the generated live filesystem for the Synapse identity, CLI, native Control app, Plasma, Calamares, PipeWire, NetworkManager, Python package, wallpaper, SDDM theme, Plymouth theme and GRUB theme.

The QEMU guest must run the Synapse smoke test and print `SYNAPSE_VM_READY` before the runtime boot gate is considered successful.
