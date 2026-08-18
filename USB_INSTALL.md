# Synapse OS USB Installer

This guide covers the complete amd64/UEFI USB installation path for Synapse OS Nebula, including the ASUS Chromebook CX1700CKA / GALLOP GENESIS target.

The ready-to-flash image is published through GitHub Releases as:

```text
SynapseOS-Nebula-amd64.iso
SynapseOS-Nebula-amd64.iso.sha256
```

The release pipeline does not publish an ISO until the source checks pass, the live image boots in QEMU, the real GENESIS writer installs Synapse OS to a disposable virtual disk, and that installed disk cold-boots successfully.

## What you need

- an 8 GB or larger USB drive;
- a computer that can write an ISO image to that USB drive;
- the Synapse OS release ISO and its matching SHA-256 file;
- an amd64 machine with UEFI boot support;
- for the current physical GENESIS v1 hardware target, an ASUS Chromebook CX1700CKA / board GALLOP prepared for supported UEFI boot.

**Writing the image destroys all data on the USB drive.** Double-check the selected USB device before flashing.

## 1. Download the release

Open the repository's GitHub Releases page and download both:

```text
SynapseOS-Nebula-amd64.iso
SynapseOS-Nebula-amd64.iso.sha256
```

Do not use an incomplete browser download or an ISO whose checksum does not match.

## 2. Verify SHA-256

### Windows PowerShell

```powershell
Get-FileHash .\SynapseOS-Nebula-amd64.iso -Algorithm SHA256
Get-Content .\SynapseOS-Nebula-amd64.iso.sha256
```

The hashes must match exactly.

### macOS

```bash
shasum -a 256 SynapseOS-Nebula-amd64.iso
cat SynapseOS-Nebula-amd64.iso.sha256
```

The hashes must match exactly.

### Linux

```bash
sha256sum -c SynapseOS-Nebula-amd64.iso.sha256
```

Expected result:

```text
SynapseOS-Nebula-amd64.iso: OK
```

## 3. Flash the USB

### Windows: Rufus

1. Insert the USB drive.
2. Open Rufus.
3. Select the correct USB under **Device**.
4. Select `SynapseOS-Nebula-amd64.iso` as the boot image.
5. Start the write.
6. If Rufus asks whether to use ISO mode or DD image mode, use DD image mode for the most literal copy of the tested release image.
7. Wait until Rufus reports completion before removing the USB.

### Windows/macOS/Linux: balenaEtcher

1. Open balenaEtcher.
2. Choose `SynapseOS-Nebula-amd64.iso`.
3. Choose the correct USB target.
4. Flash and allow Etcher to verify the write.

### Linux: `dd`

First identify the USB device carefully. Replace `/dev/sdX` with the actual whole USB device, not a numbered partition such as `/dev/sdX1`.

```bash
sudo dd if=SynapseOS-Nebula-amd64.iso of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

### macOS: `dd`

First identify the USB disk:

```bash
diskutil list
```

Replace `N` below with the actual USB disk number. Unmount the whole disk before writing:

```bash
diskutil unmountDisk /dev/diskN
sudo dd if=SynapseOS-Nebula-amd64.iso of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Using `/dev/rdiskN` writes through the raw disk device; `/dev/diskN` is still used for the `diskutil` unmount/eject operations.

**Never guess the output device. `dd` will overwrite whatever device you name.**

## 4. Boot the USB

For a normal UEFI PC, use the machine's UEFI boot menu and select the USB device.

For the ASUS CX1700CKA / GALLOP after supported Full UEFI firmware preparation:

1. Power the laptop completely off.
2. Insert the Synapse USB.
3. Power on.
4. At the edk2/MrChromebox splash, press `Esc` for the boot menu.
5. Select the USB UEFI entry.
6. Allow the Synapse live image to boot.

If the machine was originally a managed Chromebook, organizational management must be legitimately removed by the owning organization before repurposing it. GENESIS is not an enrollment-bypass mechanism.

## 5. Choose GENESIS for a phone-controlled install

The boot menu contains a dedicated **GENESIS / failsafe installer** path. Choose that entry when you want the authenticated phone-controlled installer.

That entry starts the system with:

```text
synapse.genesis=1
```

The marker is intentionally required before the destructive GENESIS API will start.

A normal live boot remains non-destructive.

## 6. Connect the phone

Once the GENESIS environment is running, the installer service listens on port `8787`.

On the laptop, read the one-boot pairing token:

```bash
sudo cat /run/synapse-genesis/token
```

Find the laptop IP address:

```bash
hostname -I
```

The phone and laptop must share a routed trusted connection, such as the same local network or supported USB tethering/networking.

On the phone, open the included `GENESIS.html` control surface and enter:

```text
Laptop API: http://<laptop-ip>:8787
Pairing token: <one-boot token>
```

Press **CONNECT**.

## 7. Review GENESIS preflight

GENESIS will not unlock installation until the required checks pass. The current v1 physical destructive installer checks include:

- supported hardware profile;
- amd64 architecture;
- UEFI boot mode;
- `synapse.genesis=1` kernel marker;
- adequate power state;
- exactly one eligible internal target disk;
- verified Synapse image size and SHA-256;
- expected Synapse license/provenance markers.

For the current ASUS physical target, the expected hardware profile is the CX1700CKA / GALLOP family.

The phone cannot submit an arbitrary disk path, image path, shell command, firmware operation, or executable command to GENESIS.

## 8. Install Synapse OS

When every preflight item is ready, press and hold:

```text
INSTALL SYNAPSE OS
```

for 2.5 seconds.

The server creates a short-lived one-time authorization bound to the exact device fingerprint, target-disk fingerprint, and verified image SHA-256.

The real GENESIS writer then performs the installation:

```text
internal disk
  -> GPT
  -> 512 MiB FAT32 EFI System Partition
  -> ext4 Synapse root partition
  -> verified Synapse root filesystem
  -> UUID-based fstab
  -> x86_64 UEFI GRUB
  -> GENESIS installation receipt
```

This replaces the operating system on the selected internal target disk.

Do not remove power while the writer is active.

## 9. First boot

Wait until GENESIS reports a complete installation and preserve the receipt displayed by the phone.

Then:

1. power the machine off;
2. remove the installer USB;
3. power the machine back on;
4. allow UEFI/GRUB to boot Synapse OS from internal storage.

The expected chain is:

```text
UEFI
  -> GRUB
  -> Synapse OS
  -> Synapse services
  -> COSMOS deployment/runtime
```

## What is inside the USB image

The release image carries the complete install environment rather than a network stub. The build verification checks for the Synapse control/runtime binaries, GENESIS writer and API service, hardware profiles, `GENESIS.html`, phone bootstrap, KDE Plasma desktop components, Calamares, PipeWire, NetworkManager, native SDK/ABI components, Synapse visual assets, licensing/provenance files, and the verified `filesystem.squashfs` root filesystem.

The destructive install therefore does not depend on cloning the operating-system payload from GitHub while the disk is being rewritten.

GitHub is the source/build/release system; the USB already carries the install payload.

## Recovery and boundaries

- Keep any original Chromebook firmware backup somewhere off the device if the machine was converted from stock firmware.
- A failed firmware flash is a different recovery problem from a failed Synapse disk installation.
- GENESIS does not disable Chromebook firmware write protection or bypass factory/enterprise security controls.
- The ASUS CX1700CKA / GALLOP remains a physical target until a complete real-hardware install, first boot, hardware acceptance pass, and evidence capture are completed.
