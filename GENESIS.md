# COSMOS // GENESIS v1

GENESIS is the authenticated Synapse OS installation path controlled from [`phone-bootstrap/GENESIS.html`](phone-bootstrap/GENESIS.html).

It is deliberately separate from the normal Phone Bootstrap COSMOS installer.

## User flow

1. Prepare the owned Chromebook for a supported alternate Synapse OS boot path. GENESIS does not bypass firmware write protection or make a factory-locked Chromebook accept another operating system.
2. Boot the Synapse OS installer media and select the separate **GENESIS / failsafe installer boot entry**. That entry adds the kernel marker `synapse.genesis=1`. Normal live boot does not enable the destructive installer API.
3. Establish a trusted routed connection between the phone and laptop, such as a trusted local network or a USB networking/tethering path supported by the two devices.
4. On the laptop, read the fresh one-boot pairing token:

   ```bash
   sudo cat /run/synapse-genesis/token
   ```

5. Find the laptop address if needed:

   ```bash
   hostname -I
   ```

6. On the phone, open:

   ```text
   http://<laptop-ip>:8787/GENESIS.html
   ```

7. Enter the pairing token and press **CONNECT**.
8. Review hardware identity, target identity, power state, image verification, architecture, and provenance checks.
9. When every preflight check is ready, press and hold **INSTALL SYNAPSE OS** for 2.5 seconds.
10. GENESIS binds a short-lived one-time authorization to the verified device, target, and image hash.
11. Follow the progress display until the installer reports success or a stable error code.
12. Preserve the installation receipt shown by the phone, shut down the installer environment, remove the installer media, and boot the installed Synapse OS disk.

## What the phone can and cannot do

The HTML is the control surface. It does not create privileged services inside a browser. The dedicated installer environment starts the fixed-purpose root API on `0.0.0.0:8787` only when both of these are true:

- the boot command line contains `synapse.genesis=1`;
- `/run/live/medium/synapse-genesis/manifest.json` exists.

The phone cannot choose an arbitrary disk path, image path, shell command, repository URL, firmware action, or executable command. Request fields that attempt to provide those values are rejected.

There is no generic `/shell` or `/exec` endpoint.

## Safety model

GENESIS is fail-closed. Installation remains unavailable unless the dedicated installer environment, pairing token, target identity, image integrity, architecture, power checks, and one-time authorization all validate.

The target selector accepts only one uniquely identified eligible internal disk. Removable media, USB disks, source installer media, loop devices, zram, optical devices, and ambiguous multi-disk situations are rejected.

Immediately before a destructive write, the writer rechecks the target fingerprint and SHA-256 of the staged Synapse root filesystem. The writer itself also requires root and the exact `synapse.genesis=1` kernel marker.

GENESIS does not automate Chromebook firmware write-protection removal or firmware-security bypass.

The normal Synapse desktop Phone Bootstrap service is separate from GENESIS and is explicitly disabled during a GENESIS boot session.

## Phone API

Public liveness:

```text
GET /v2/health
```

Authenticated reads:

```text
GET /v2/device
GET /v2/preflight
GET /v2/image
GET /v2/install/status
GET /v2/install/receipt
```

Authenticated actions:

```text
POST /v2/hello
POST /v2/install/arm
POST /v2/install/start
```

The final start request carries only the one-time challenge ID and its server-bound acknowledgement. Disk and image selection remain server-side.

## Installation layout

GENESIS v1 creates an amd64 UEFI installation with:

- GPT partition table;
- 512 MiB FAT32 EFI System Partition;
- ext4 Synapse root partition using the remainder of the target;
- the verified `filesystem.squashfs` extracted to the root partition;
- UUID-based `/etc/fstab`;
- removable-path x86_64 UEFI GRUB installed without modifying firmware NVRAM;
- a generated Synapse OS GRUB entry;
- the GENESIS receipt embedded under `/var/lib/synapse/genesis/receipt.json`.

The v1 destructive writer is deliberately amd64-only. ARM64 and RISC-V remain compatibility/build targets until separate destructive-install boot gates exist for those architectures.

## Image integrity and provenance

Each final installer ISO carries `/synapse-genesis/manifest.json`. The manifest identifies the exact installer payload with its version, architecture, byte size, SHA-256, build commit, Synapse Source License identifier, and Zenodo DOI `10.5281/zenodo.17574447`.

The final ISO build extracts the manifest and root filesystem back out of the remastered ISO and verifies them again before publishing the checksum.

GENESIS v1 reports this as SHA-256 integrity verification. It does not claim a detached cryptographic release signature until a real signing-key pipeline exists.

## Automated certification gates

The required amd64 workflow must pass all of the following before GENESIS is considered software-verified:

1. repository unit, language, architecture, license, and provenance checks;
2. full Synapse OS amd64 ISO build;
3. final ISO SHA-256 verification;
4. final ISO inspection proving GENESIS HTML, writer, privileged service, runtime modules, boot marker, manifest, license, and Zenodo provenance are present;
5. live Synapse OS QEMU boot to `SYNAPSE_VM_READY`;
6. a disposable installed-disk test where the real GENESIS writer partitions and formats only a temporary `/dev/nbdN` device backed by a sparse CI file, installs Synapse, installs GRUB, disconnects the NBD target, and cold-boots the resulting virtual disk under UEFI to `SYNAPSE_VM_READY`.

The disposable installed-disk gate must never name or select a physical laptop disk.

## Chromebook preparation boundary

GENESIS does not make a factory-locked Chromebook accept an alternate operating system. Any required Developer Mode, supported alternate boot/UEFI preparation, or other physical ownership step remains a deliberate manual hardware-preparation step.

## Current certification state

Software/VM verification and physical hardware certification are separate.

The ASUS Chromebook CX1700CKA / GALLOP remains `physical-target`, not `physical-certified`, until the actual laptop successfully completes preflight, installation, first boot, hardware acceptance checks, and evidence capture.
