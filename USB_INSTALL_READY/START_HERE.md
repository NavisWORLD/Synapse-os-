# START HERE — Synapse OS USB installer

This folder is the computer-side staging kit for the **Synapse OS Nebula amd64/UEFI installer** used by the ASUS Chromebook CX1700CKA / GALLOP target.

## Windows — easiest custom-tool path

1. Insert an **8 GB or larger USB drive**. Everything on that USB will be erased later.
2. Run `DOWNLOAD_INSTALLER_WINDOWS.ps1` from PowerShell. It downloads every ISO release part, both SHA-256 files, and the official reassembly helpers from the latest GitHub Release.
3. Run the newly downloaded `reassemble-usb-installer.ps1`. Do not continue unless it ends with `Reassembled and verified`.
4. Run `VERIFY_INSTALLER.ps1` if you want an extra checksum pass.
5. Double-click `FLASH_USB_WINDOWS.cmd`. Approve the Administrator prompt.
6. The Synapse flasher lists only eligible USB disks, verifies the ISO, makes you type a confirmation bound to the selected USB, writes the raw image, then reads the written image back and verifies SHA-256.
7. Continue only if the final message is exactly `BOOTABLE USB VERIFIED`.
8. Safely remove the USB, insert it into the GALLOP Chromebook, open the MrChromebox/edk2 Boot Menu, and choose the USB UEFI entry.

If Python 3 is not installed on the computer, use **Rufus** or **balenaEtcher** to flash `SynapseOS-Nebula-amd64.iso`. Copying the ISO file onto a normal USB filesystem is not enough; it must be written as a disk image.

## macOS / Linux

Run, in order:

```bash
chmod +x DOWNLOAD_INSTALLER_MAC_LINUX.sh reassemble-usb-installer.sh VERIFY_INSTALLER.sh FLASH_USB_MAC_LINUX.sh
./DOWNLOAD_INSTALLER_MAC_LINUX.sh
./reassemble-usb-installer.sh
./VERIFY_INSTALLER.sh
./FLASH_USB_MAC_LINUX.sh
```

The flasher requires `sudo` because raw removable-disk writes require elevated privileges.

## What the custom flasher refuses to do

The flasher does not accept an arbitrary target path. It discovers removable USB disks, rejects internal/system/boot disks, requires enough capacity for the image, re-probes the selected device before writing, requires an exact destructive confirmation phrase, and verifies the complete written image by SHA-256 read-back.

## Important boundary

The repository can validate the image-building logic and file-backed writer behavior, but this does not prove a specific physical USB stick or specific PC USB controller until you perform the real write and receive the read-back verification on that machine.
