# Phone HTML USB Flasher Design

Date: 2026-08-19
Repository: NavisWORLD/Synapse-os-
Branch: feature/phone-html-usb-flasher

## Goal

Add a phone-first `FLASH_USB.html` application that can prepare Synapse OS boot media from a mobile browser while preserving the same fail-closed safety model used by GENESIS.

The user experience should be:

1. Open `FLASH_USB.html` on the phone.
2. Connect an external USB device through the phone/adapter path.
3. Load or obtain the approved Synapse OS installer image.
4. Detect whether the browser exposes a direct block-capable transport.
5. If direct access is available, use it.
6. If direct raw USB access is unavailable, expose a local-helper mode rather than pretending the write occurred.
7. Require explicit destructive confirmation.
8. Write only an eligible removable target.
9. Fully read back and verify the flashed image before reporting success.

## Non-goals

- No arbitrary shell or command execution endpoint.
- No ability to target the laptop's internal SSD/eMMC/NVMe.
- No firmware write-protection or enrollment bypass.
- No silent/background destructive writes.
- No fake success when a browser or OS blocks raw mass-storage access.
- No hidden reverse tunnel from GitHub into a local machine.

## Architecture

The flasher has one UI and two transport adapters behind the same state machine.

### 1. Direct browser adapter

`FLASH_USB.html` first probes available browser capabilities such as USB/device APIs and file-system/storage APIs.

The page records:

- whether the relevant API exists;
- whether the user can select an attached device;
- device/product/vendor metadata exposed by the browser;
- whether a writable block-style endpoint or equivalent direct transport is actually available;
- the exact browser exception when access is rejected.

Direct mode is enabled only if the browser exposes enough capability to perform a real bounded write and full read-back verification. Capability detection alone is not treated as proof of write access.

The direct adapter must not infer that a user-selected device is safe merely because it was selected. It must have sufficient transport/device information to bind the destructive confirmation to the exact external target. If that information is unavailable, direct flashing is disabled and the page remains a capability probe or uses helper mode.

### 2. Local helper adapter

When direct browser access is unavailable, the same HTML can connect to a small authenticated local service on port `8788`.

The helper is fixed-purpose and exposes only USB-flashing operations. It enumerates removable USB media server-side, downloads or accepts the approved Synapse image, verifies hashes, writes the selected removable device, syncs, performs full read-back verification, and reports progress.

The local helper does not expose generic command execution.

### HTML hosting and local-network transport

The canonical source file lives in GitHub, but helper mode should not depend on an HTTPS GitHub page being allowed to call an insecure local HTTP endpoint. Browsers can apply mixed-content, CORS, or private-network restrictions to that pattern.

Therefore:

- direct-browser mode may run from the GitHub-hosted/downloaded HTML when the browser itself owns the device transport;
- helper mode serves the exact same `FLASH_USB.html` from `http://<helper-ip>:8788/FLASH_USB.html` so UI and API are same-origin;
- the helper must expose a content hash/version for the served HTML so the phone can confirm it matches the repository build;
- no CORS wildcard is required for the normal helper flow.

## UI states

The single-file HTML should have explicit states:

- `CAPABILITY CHECK`
- `DEVICE SELECTION`
- `IMAGE READY`
- `PREFLIGHT`
- `ARMED`
- `FLASHING`
- `VERIFYING`
- `BOOTABLE USB VERIFIED`
- `FAILED`

The page must never jump from image selection directly to flashing.

## Image source

The flasher supports the Synapse OS amd64 installer image produced by the existing release workflow.

The image must be bound to:

- expected filename;
- version;
- byte size;
- SHA-256;
- architecture;
- Synapse provenance metadata when available.

A mismatched or incomplete image fails closed.

For GitHub releases larger than a single release-asset limit, the flasher may stage/reassemble the existing ordered ISO parts before writing. Helper mode may fetch only the fixed approved Synapse release metadata/assets; the public API must not accept an arbitrary executable command or arbitrary repository URL.

Direct mode may accept a user-selected local ISO/part set, but must verify it against the approved release manifest/checksum before flashing.

## Removable-target policy

A target is eligible only when it is positively identified as external/removable USB media.

Fail closed when:

- the target is internal;
- the target identity is ambiguous;
- multiple indistinguishable targets exist;
- the target is the source/storage device holding the image and cannot safely be overwritten;
- the target disappears or changes identity after arming;
- capacity is smaller than the image;
- power or transport state becomes unsafe.

The UI must show the exact target identity and capacity before destructive confirmation.

## Authentication and destructive confirmation

Helper mode generates a fresh one-boot pairing token and requires it for all non-health API calls.

The user must hold `HOLD TO FLASH USB` for 2.5 seconds.

The authorization is bound to:

- target fingerprint;
- image SHA-256;
- image byte size;
- a short-lived challenge identifier.

Any target/image change invalidates the challenge. Challenges are one-time and replay-resistant.

## Write and verification

A successful flash requires all of the following:

1. verified image before writing;
2. exact target recheck immediately before writing;
3. sequential write with progress reporting;
4. explicit flush/sync completion;
5. full read-back SHA-256 verification over exactly the image byte length;
6. final target fingerprint recheck;
7. only then show `BOOTABLE USB VERIFIED`.

A transport error, short write, disconnect, checksum mismatch, target change, or verification mismatch is a hard failure.

## Local helper API

Proposed fixed-purpose endpoints on `:8788`:

Public:

- `GET /v1/health`
- `GET /FLASH_USB.html`

Authenticated reads:

- `GET /v1/capabilities`
- `GET /v1/devices`
- `GET /v1/image`
- `GET /v1/flash/status`

Authenticated actions:

- `POST /v1/hello`
- `POST /v1/image/prepare`
- `POST /v1/flash/arm`
- `POST /v1/flash/start`

No `/shell`, `/exec`, arbitrary command, arbitrary block-device path, or arbitrary repository URL route is permitted.

## Repository changes

Expected implementation files:

- `phone-bootstrap/FLASH_USB.html`
- `src/synapse/usb_flash.py`
- `src/synapse/usb_flash_server.py`
- fixed launcher/service files for port `8788` where appropriate
- tests for browser-source contracts, removable-target policy, arming, image verification, same-origin helper serving, and helper API
- documentation under `USB_INSTALL.md` and/or a dedicated `FLASH_USB.md`

The direct-browser adapter remains inside the single HTML file so it can be opened directly from GitHub or saved locally on the phone.

## Testing strategy

Use TDD.

Required tests:

- source test proving `FLASH_USB.html` exposes capability detection and no fake-success fallback;
- target-policy tests rejecting internal, ambiguous, source, and undersized disks;
- arm replay/expiry/fingerprint mismatch tests;
- image SHA-256 mismatch test;
- API tests rejecting request-controlled arbitrary disk paths/commands/repository URLs;
- same-origin helper test proving `/FLASH_USB.html` serves the canonical UI;
- simulation-mode write test with a file-backed disposable target;
- real CI destructive test only against a disposable virtual/block-backed fixture;
- verification-failure test proving `BOOTABLE USB VERIFIED` cannot be emitted before full read-back success.

Physical iPhone + adapter testing remains a separate hardware acceptance step and must not be represented as complete from VM/CI evidence alone.

## Success criteria

The feature is considered software-complete when:

- `FLASH_USB.html` runs as a single-file phone UI;
- it accurately reports direct browser capability on the current device;
- it never claims direct flashing when the platform blocks it;
- the local-helper path can create a verified bootable Synapse USB on an eligible disposable/removable target;
- internal disks cannot be selected through the public API;
- full read-back SHA-256 verification gates success;
- the full repository test suite and new USB-flasher CI gates pass.

Physical success is reached only after an actual phone + USB adapter + USB drive run produces a verified bootable Synapse USB and that USB successfully reaches the Synapse/GENESIS boot menu on the target machine.
