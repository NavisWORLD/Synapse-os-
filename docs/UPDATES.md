# Updating Synapse OS Nebula (alpha)

This document separates **Debian package maintenance** from **Synapse OS
first-party releases**. The current alpha does **not** include an automatic
Synapse OTA updater, a Synapse APT repository or an in-place first-party
release migration. Do not treat a normal package upgrade as a Synapse OS
version upgrade.

## 1. Back up first

Back up personal files and any Beast/COSMOS memory directories, model
checkpoints, user configuration, keys and receipts **outside the VM or disk
being changed**. Verify that you can read the backup. Never carry forward
authority grants or credentials merely because memory is restored.

Record the installed image version, source commit and SHA-256. If you are
experimenting in a VM, take a snapshot **after** backing up personal data.
Keep the existing bootable image/recovery media.

## 2. Debian package updates (same Synapse image)

On an installed, networked Synapse system with an authorized administrator,
use the ordinary Debian package manager:

```sh
sudo apt update
sudo apt full-upgrade
sudo reboot
synapse doctor
```

Review APT's proposed removals before approving, especially kernels, Plasma,
Calamares, bootloader, graphics drivers, firmware and Synapse dependencies.
Use Debian's official signed repositories; **do not add arbitrary third-party
APT sources** to get a purported Synapse update. In an offline system, package
updates cannot run until the system has safe repository access.

`full-upgrade` updates packages from the configured Debian repositories.
It does **not** install the next Synapse OS release or update the pinned Beast
Box prerelease, a native RAWRPHØS checkpoint or unbundled third-party AI
providers. Restore/run only models whose integrity and compatibility you
have verified.

## 3. New Synapse OS release (new image)

1. Open the official [Synapse OS Releases](https://github.com/NavisWORLD/Synapse-os-/releases).
   Identify the **newer version** and read the release notes and limitations.
   An older alpha's ISO is not interchangeable with a newer tag.
2. Download every ISO part, both checksums and the matching reassembly
   helper. Follow [USB_INSTALL.md](../USB_INSTALL.md) for checksum
   verification. Do not boot, flash or install from a mismatched image.
3. Test the new ISO in a separate disposable VM with
   [VM_INSTALL.md](VM_INSTALL.md). Verify the graphical desktop and the
   applications you actually require.
4. For the current alpha, perform a **fresh installation** to a separate
   disposable VM disk or carefully selected test machine. Do not assume an
   unattended in-place migration exists. Restore ordinary user data and
   optional Beast memory only after checking compatibility and explicit
   authorization. Reconfigure local AI providers and secrets separately.
5. Preserve the old image and receipts until the new install has passed
   your own acceptance checks. File bug reports with the release tag,
   checksum, VM/hardware configuration and redacted guest logs.

For physical-disk installation, a fresh image can erase data. Keep recovery
media, take backups, use the installer preflight and stop if the target is
ambiguous. AMD64 disposable QEMU installation success is **not** proof of
physical hardware compatibility.

## 4. Share the supported route

Share the official release link, this update guide and install instructions.
Synapse's current original material is **source-available under a
noncommercial evaluation license**, not open source. See
[LICENSE](../LICENSE) and [LICENSING.md](LICENSING.md). The public grant does
not authorize third-party redistribution, commercial deployment, hosted
services or AI/ML model-development use; those uses need the separate
permission described there. Debian and other third-party material retain
their own license rights. Do not change a package's original license notices.
