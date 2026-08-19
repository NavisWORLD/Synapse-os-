# Synapse OS Phone → USB Kit

This folder is the phone-first staging kit for Synapse OS Nebula.

It is designed so you can download the small helper bundle and the large release parts on your iPhone, keep them together, and move them onto external USB storage without hunting through the repository.

## Important: staging is not flashing

**Copying these files onto a USB drive does not make the USB bootable.** A bootable Synapse installer is created only after the verified ISO is reconstructed and **flashed as a disk image** to the USB.

The iPhone Files app can store and move the release files, but ordinary file copying is not the same thing as raw-writing an ISO image to a USB device.

## What to download on your iPhone

Open the latest Synapse OS GitHub Release:

https://github.com/NavisWORLD/Synapse-os-/releases/latest

Download:

1. `SynapseOS-Phone-USB-Kit.zip`
2. every `SynapseOS-Nebula-amd64.iso.part-*` file

The ZIP contains this start guide, the release checklist, both reassembly helpers, and the SHA-256 checksum files. The large ISO parts stay separate so GitHub can distribute them safely.

## iPhone folder layout

In the Files app, keep everything together like this:

```text
SynapseOS-USB/
├── START_HERE.html
├── README.md
├── RELEASE_FILES.txt
├── SynapseOS-Nebula-amd64.iso.part-000
├── SynapseOS-Nebula-amd64.iso.part-001
├── ...
├── SynapseOS-Nebula-amd64.iso.parts.sha256
├── SynapseOS-Nebula-amd64.iso.sha256
├── reassemble-usb-installer.ps1
└── reassemble-usb-installer.sh
```

You may store that folder on an external USB drive connected to the iPhone. That makes the USB a **transfer/staging drive**, not yet a bootable installer.

## Turn the staged files into the bootable installer

On Windows, macOS, or Linux, copy/open the staged folder and run the matching reassembly helper. It verifies every part and reconstructs:

```text
SynapseOS-Nebula-amd64.iso
```

Then use a raw image writer such as Rufus, balenaEtcher, or the documented `dd` procedure to flash that ISO to the USB drive.

Full instructions are in the repository root:

https://github.com/NavisWORLD/Synapse-os-/blob/main/USB_INSTALL.md

## GALLOP / ASUS CX1700CKA

Once the USB has actually been flashed and verified, it is the boot media for the supported amd64/UEFI path and the GALLOP physical target. The Chromebook still needs legitimate supported UEFI preparation before it can boot the Synapse USB.

If the Chromebook is organization-managed, management must be removed by the owning organization. This kit is not an enrollment-bypass mechanism.

## Short version

**Phone:** download + store + move the kit and all ISO parts.

**Computer/raw-writer:** verify + reconstruct + flash the ISO.

**Chromebook:** insert the flashed USB + select the UEFI USB boot entry + boot Synapse/GENESIS.
