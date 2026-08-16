# COSMOS // GENESIS v1

GENESIS is the authenticated Synapse OS installation path controlled from [`phone-bootstrap/GENESIS.html`](phone-bootstrap/GENESIS.html).

It is deliberately separate from the normal Phone Bootstrap COSMOS installer.

## User flow

1. Boot a supported Synapse installer environment that has been deliberately prepared for GENESIS mode.
2. Establish a trusted local connection between the phone and laptop.
3. Open `http://<laptop-ip>:8787/GENESIS.html` on the phone.
4. Enter the fresh pairing token displayed/stored by the installer environment.
5. Press **CONNECT**.
6. Review hardware identity, target identity, power state, image verification, architecture, and provenance checks.
7. When every preflight check is ready, press and hold **INSTALL SYNAPSE OS** for 2.5 seconds.
8. GENESIS binds a short-lived one-time authorization to the verified device, target, and image hash.
9. Follow the progress display until the installer reports success or a stable error code.
10. Preserve the installation receipt shown by the phone.

## Safety model

GENESIS is fail-closed. Installation remains unavailable unless the dedicated installer environment, pairing token, target identity, image integrity, architecture, and one-time authorization all validate.

The phone cannot choose an arbitrary disk path, image path, shell command, repository URL, firmware action, or executable command. Request fields that attempt to provide those values are rejected.

GENESIS contains no generic `/shell` or `/exec` endpoint and does not automate Chromebook firmware write-protection removal or firmware-security bypass.

The normal Synapse desktop Phone Bootstrap service is separate from GENESIS and does not activate the privileged installer runtime.

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

## Image integrity and provenance

Each final installer ISO carries `/synapse-genesis/manifest.json`. The manifest identifies the exact installer payload with its version, architecture, byte size, SHA-256, build commit, Synapse Source License identifier, and Zenodo DOI `10.5281/zenodo.17574447`.

GENESIS v1 reports this as SHA-256 integrity verification. It does not claim a detached cryptographic release signature until a real signing-key pipeline exists.

## Chromebook preparation boundary

GENESIS does not make a factory-locked Chromebook accept an alternate operating system. Any required Developer Mode, supported alternate boot/UEFI preparation, or other physical ownership step remains a deliberate manual hardware-preparation step.

## Current certification state

The installer code is tested with synthetic devices and non-destructive simulation in CI. The bootable image is required to pass source validation, manifest verification, filesystem inspection, checksum verification, and the existing QEMU boot gate.

The ASUS Chromebook CX1700CKA / GALLOP remains `physical-target`, not `physically-certified`, until a real-device installation and reboot have been completed and evidence recorded.
