# FLASH USB // phone-first Synapse media writer

`phone-bootstrap/FLASH_USB.html` is the Synapse OS phone-facing USB-media tool.

It has two deliberately separate transports behind one UI:

1. **Direct browser experiment** — probe the phone/browser for WebUSB, select an explicitly granted USB device, and continue only if the browser actually allows the USB Mass Storage Bulk-Only interface to be claimed.
2. **Local helper** — when direct browser mass-storage access is unavailable, serve the same HTML from the fixed-purpose authenticated helper on port `8788`. The helper performs the privileged raw write locally and accepts no arbitrary command, disk path, image path, repository URL, or shell request from the phone.

A successful result is never inferred from a completed write call. Both paths require full SHA-256 verification of the source image before writing and a full SHA-256 read-back over the written image bytes before the UI may display `BOOTABLE USB VERIFIED`.

## First iPhone capability test — safe checkpoint

This first test is non-destructive. Do **not** hold the flash button yet.

1. Open/download `phone-bootstrap/FLASH_USB.html` on the phone.
2. Press **RUN CAPABILITY CHECK**.
3. Read the `WebUSB` and `Secure context` fields.
4. If WebUSB is exposed, connect the sacrificial USB drive through the phone's USB adapter and press **CHOOSE USB DEVICE**.
5. Stop after the page reports either `MSC BOT CLAIMED` or the exact browser/platform error such as `SecurityError` / `navigator.usb is not exposed`.

No disk write occurs during capability check or USB selection. The destructive button remains locked until an image is hash-verified and a target-capacity preflight succeeds.

## Direct browser path

Direct mode is intentionally narrow. It accepts only a browser-granted interface matching:

- USB interface class `0x08` — Mass Storage;
- subclass `0x06` — SCSI transparent command set;
- protocol `0x50` — Bulk-Only Transport;
- one bulk-IN and one bulk-OUT endpoint.

When that interface can actually be claimed, the page uses USB Mass Storage CBW/CSW framing and the bounded SCSI commands needed for the operation:

- `READ CAPACITY(10)`;
- `WRITE(10)`;
- `SYNCHRONIZE CACHE(10)`;
- `READ(10)`.

The page does not offer generic USB control transfers or arbitrary SCSI commands.

### Direct flash sequence

1. Choose the reconstructed `SynapseOS-...-amd64.iso`.
2. Choose the matching `.sha256` sidecar or paste its 64-character digest.
3. Press **VERIFY IMAGE** and wait for the streaming source SHA-256 to match.
4. Press **CHOOSE USB DEVICE** and grant only the USB drive you intend to erase.
5. Press **DIRECT PREFLIGHT** and verify target identity and capacity.
6. Hold **HOLD TO FLASH USB** continuously for 2.5 seconds.
7. Keep the phone powered and the adapter/USB physically stable through both `FLASHING` and `VERIFYING`.
8. Treat the media as good only if the final state is exactly `BOOTABLE USB VERIFIED`.

If the browser refuses the Mass Storage interface, that is a direct-transport failure. It is not converted into a fake direct success.

## Local helper path on Linux/Synapse

The helper is an explicit owner-started privileged tool. It is **not** enabled at normal boot.

With the verified ISO and checksum file on the helper host:

```bash
sudo synapse-usb-flash-server \
  --listen 0.0.0.0 \
  --port 8788 \
  --token-file /run/synapse-usb-flash/token \
  --image /path/to/SynapseOS-Nebula-amd64.iso \
  --sha256-file /path/to/SynapseOS-Nebula-amd64.iso.sha256
```

Read the one-boot token:

```bash
sudo cat /run/synapse-usb-flash/token
```

Find the helper host IP:

```bash
hostname -I
```

Then open on the phone:

```text
http://<helper-ip>:8788/FLASH_USB.html
```

Enter the token and press **CONNECT HELPER**.

The helper's real writer refuses to continue unless exactly one eligible target exists with all of these properties:

- `TYPE=disk`;
- removable flag set;
- transport exactly `usb`;
- not the source disk containing the ISO;
- capacity at least the ISO byte size.

If two eligible USB disks are attached, the helper fails with `TARGET_AMBIGUOUS` rather than guessing. Internal SSD/eMMC/NVMe media do not qualify.

Immediately before opening a real block device, the helper re-probes target identity. The one-time authorization is bound to target fingerprint, source image SHA-256, and source image size. Any identity change requires a new arm.

## Verification and receipt

The helper writes sequentially, flushes the block device, then reads back exactly the source image byte length and calculates SHA-256 again. Only a byte-for-byte digest match creates a `synapse-usb-flash-receipt/v1` receipt with `verified: true`.

A disconnect, short write, short read, target change, source-image change, or read-back mismatch ends in `FAILED`.

## Relationship to GENESIS

`FLASH_USB.html` prepares the removable boot media. `GENESIS.html` is the next stage after booting that media on the target ASUS/GALLOP machine.

```text
phone → FLASH_USB.html → verified bootable USB
                           ↓
                     boot ASUS from USB
                           ↓
phone → GENESIS.html → install Synapse OS to verified internal target
```

These are separate destructive boundaries. The USB flasher cannot select the Chromebook's internal target, and GENESIS cannot turn an ordinary copied folder into bootable USB media.

## Current evidence boundary

Repository/CI tests can prove policy, image hashing, one-time arming, disposable file-backed writes, read-back verification, API request restrictions, HTML source contracts, and generated-image packaging.

They do **not** prove that a particular iPhone/iOS build exposes WebUSB Mass Storage. Physical direct-browser support is established only by the real phone + adapter capability test. A blocked direct path is an expected platform result and leaves the local-helper path available.
