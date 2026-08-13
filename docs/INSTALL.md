# Install Guide

**Installing an operating system can destroy existing data. Back up anything important first.**

1. Build or download the Synapse OS ISO and verify its `.sha256` file.
2. Write the ISO to a USB drive using a trusted image writer.
3. Boot the laptop from USB in UEFI mode.
4. Choose the live session first. Test Wi-Fi, audio, keyboard/trackpad, display brightness, suspend/resume, webcam, and external displays.
5. Open **Install Synapse OS** to launch Calamares.
6. Read the partitioning screen carefully. Dual-boot users should use existing free space rather than erasing the disk.
7. Reboot after installation and remove the USB drive.
8. Run `synapse doctor` and apply all system/firmware updates.

## Before replacing an existing OS

Keep a second bootable recovery USB. If the machine uses BitLocker/FileVault on another installation, record its recovery keys before touching partitions.
