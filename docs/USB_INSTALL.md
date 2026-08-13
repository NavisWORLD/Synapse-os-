# Synapse OS USB Installer

Synapse OS ships as a hybrid ISO. Writing that ISO byte-for-byte to a USB disk produces bootable installation media.

The repository includes `synapse-usb`, a guarded writer implemented in `synapse.usb_writer`.

## Safety model

The writer is intentionally conservative:

- it never auto-selects a target disk;
- it only accepts disks detected as removable/external USB media;
- it rejects disks marked as boot/system disks;
- the ISO must have a SHA-256 checksum file;
- the exact target must be repeated as `ERASE:<device>`;
- `--dry-run` performs validation without writing;
- after writing, the first and final sample regions are re-read and compared with the ISO.

A USB write destroys the previous contents of the selected USB disk. Back up anything important first.

## Get the ISO

Download the `synapse-os-nebula-amd64` artifact from the latest successful `Build and VM smoke test` GitHub Actions run. Extract both the `.iso` and matching `.iso.sha256` into the same folder.

## Run directly from this repository

From the repository root:

```bash
PYTHONPATH=src python3 -m synapse.usb_writer list
```

Choose only the USB disk you physically plugged in.

Perform a dry run first:

```bash
PYTHONPATH=src python3 -m synapse.usb_writer write \
  --iso /path/to/SynapseOS-0.1.0-alpha.1-amd64.iso \
  --device /dev/sdX \
  --confirm 'ERASE:/dev/sdX' \
  --dry-run
```

If the dry run identifies the correct USB, repeat without `--dry-run` from an Administrator/root terminal.

## Linux

Run the write command with `sudo` and preserve `PYTHONPATH` explicitly:

```bash
sudo env PYTHONPATH="$PWD/src" python3 -m synapse.usb_writer list
sudo env PYTHONPATH="$PWD/src" python3 -m synapse.usb_writer write \
  --iso "$HOME/Downloads/SynapseOS-0.1.0-alpha.1-amd64.iso" \
  --device /dev/sdX \
  --confirm 'ERASE:/dev/sdX'
```

The writer accepts Linux disks reported removable or transported over USB and rejects a candidate carrying `/`, `/boot`, or `/boot/efi`.

## macOS

Run from Terminal with `sudo`:

```bash
PYTHONPATH=src python3 -m synapse.usb_writer list
sudo env PYTHONPATH="$PWD/src" python3 -m synapse.usb_writer write \
  --iso "$HOME/Downloads/SynapseOS-0.1.0-alpha.1-amd64.iso" \
  --device /dev/diskN \
  --confirm 'ERASE:/dev/diskN'
```

Only disks reported by `diskutil` as external physical media are eligible. The writer unmounts the external disk before writing and uses the raw `/dev/rdiskN` path when available.

## Windows

Install Python 3.11 or newer, open **PowerShell as Administrator**, and run from the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m synapse.usb_writer list
```

The writer lists USB-bus disks as `\\.\PhysicalDriveN`. Then run a dry run using the exact displayed device:

```powershell
python -m synapse.usb_writer write `
  --iso "$HOME\Downloads\SynapseOS-0.1.0-alpha.1-amd64.iso" `
  --device "\\.\PhysicalDriveN" `
  --confirm "ERASE:\\.\PhysicalDriveN" `
  --dry-run
```

Repeat without `--dry-run` only after verifying the disk number, model, and size. The writer refuses disks Windows marks as boot or system disks.

## Boot and install Synapse OS

1. Shut down the target laptop.
2. Insert the completed Synapse USB.
3. Open the machine's UEFI/boot-device menu.
4. Select the USB device.
5. Boot Synapse OS.
6. Use **Install Synapse OS** to launch Calamares.
7. Review the target disk carefully before applying partition changes.

The current automated certification proves the hybrid ISO builds, validates, and boots in QEMU. Physical USB boot and installation should still be treated as a separate hardware validation step because firmware, Secure Boot configuration, storage controllers, Wi-Fi chipsets, and graphics hardware vary by laptop.
