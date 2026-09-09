# BeastOS Web Machine

**Status:** experimental Synapse OS subsystem. Browser/PWA and authority behavior are implemented and under CI; physical device and disposable-guest validation must be reported separately from software tests.

BeastOS Web Machine is the browser cockpit connecting Synapse OS to the existing Beast Box persistent runtime. It does not fork Beast memory, state, R12 routing, providers, provenance, checkpoints, or model handoff logic.

> SYNAPSE OS = THE HOME  
> BEAST BOX = THE CONTINUITY  
> BEASTOS WEB = THE COCKPIT  
> MODEL = THE BRAIN CLOCKING IN  
> BEAST MACHINE = THE DISPOSABLE BODY

The security invariant is simple: **the story transfers; the keys do not.**

## Architecture

```text
Browser / installed PWA
        |
        | same-origin authenticated /v1 API
        v
BeastOS localhost bridge (127.0.0.1 only)
        |
        +-- Synapse authority ledger ----> device / file / VM grants
        |
        +-- Beast runtime exchange ------> Beast Box v0.6.0 durable runtime
        |
        +-- QEMU controller -------------> optional disposable Linux guest
        |
        +-- hash-chained Synapse Trace
```

The browser is not the persistent AI runtime. Beast Box owns durable continuity. Synapse owns host authority. The model does not automatically own either.

## Pinned Beast integration

Synapse consumes the published Beast Box **v0.6.0 portable runtime preview/prerelease** as a versioned external input.

| Field | Value |
| --- | --- |
| Tag | `v0.6.0` |
| Commit | `331f03c5d6a4aab0b2e32314293e36c7a94be393` |
| Asset | `beast-box-combined-0.6.0.zip` |
| Size | `676405` bytes |
| SHA-256 | `c2a5bf5e3cb972ec3e5f1aa45f06d7e77e9b6de115e049f06e830a1f4c312ad2` |
| Runtime API | `beastbox runtime exchange` |

The canonical pin is `manifests/beast-v0.6.0.json`. `scripts/fetch-beast-kit.py` accepts no caller-controlled download URL. It fetches the pinned GitHub release asset, verifies exact size and SHA-256, rejects unsafe ZIP entries, and requires the published wheel. Offline builders may supply `SYNAPSE_BEAST_KIT_SOURCE`; the supplied file must pass the same manifest verification.

The Synapse image installs only the verified `cosmos_beast_box-0.6.0-py3-none-any.whl` into `/opt/synapse/beast-runtime`. No Beast source tree is copied into or reimplemented by Synapse.

## Beast exchange

The bridge calls the fixed Beast protocol through a subprocess argument vector with `shell=False`:

```text
beastbox runtime exchange --data-dir <owner data directory> ...
```

Requests are bounded `beastbox-request-v1` documents. Only `chat`, `inspect`, and `init` are supported by this adapter. A runtime/provider failure is returned as unavailable; there is no silent provider fallback.

The default installed demonstration provider is Beast Box's deterministic `reference` provider. It is **not a language model**. Local Ollama or a compatible provider can be selected explicitly. Non-loopback compatible providers require HTTPS and explicit remote authorization.

## Authority model

Model, memory, state, provenance, authority, and whole-system identity are separate concerns.

A brain clock-in revokes all brain-scoped grants from the previous brain. If a disposable VM is running, model swap destroys the old body before the new brain becomes active.

Grantable bridge capabilities are deliberately enumerated:

- camera
- microphone
- filesystem read/write
- repository write
- VM control/network
- network status/control
- USB
- serial
- Bluetooth

There is no arbitrary `shell`, `exec`, command, path, repository URL, device path, image path, secret, or credential endpoint.

The master privacy action revokes bridge grants and destroys an active Beast Machine where technically possible. Browser camera/microphone tracks are also stopped by the PWA. Operations already submitted outside the local process cannot be falsely represented as canceled.

## Browser capability layer

Capability state is detected rather than assumed. The UI uses:

- `navigator.mediaDevices.getUserMedia` for camera and microphone
- File System Access API detection with normal file-picker fallback
- OPFS detection through `navigator.storage.getDirectory`
- IndexedDB availability as browser fallback capability
- `navigator.storage.estimate` for quota information
- `navigator.gpu` for WebGPU probing
- WebAssembly plus SIMD/thread eligibility checks
- WebUSB, WebSerial, and WebBluetooth feature detection
- browser online/offline state

States are shown as supported, permission required, authorized, denied, or unavailable. A feature-detection result is not represented as a connected physical device.

### Browser limitations

HTML does **not** bypass the browser sandbox.

HTML does **not** directly boot the physical computer.

A normal browser can use the device's existing network connection but that is not unrestricted control of the Wi-Fi adapter. Native network inspection or mutation belongs behind explicit Synapse authority.

WebUSB, WebSerial, WebBluetooth, WebGPU, File System Access, OPFS, camera, and microphone support vary by browser, operating system, security context, and policy. Unsupported APIs remain unavailable.

## Files and storage scopes

The product distinguishes:

1. `TEMPORARY_ATTACHMENT`
2. `CONVERSATION_CONTEXT`
3. `WORKSPACE_KNOWLEDGE`
4. `PERSISTENT_BEAST_MEMORY`
5. `VM_EPHEMERAL_STORAGE`

A browser upload begins as `TEMPORARY_ATTACHMENT`. Transfer between scopes requires an explicit authorized path. Uploading a file does not silently make it persistent Beast memory.

The cockpit does not store provider secrets in `localStorage`. Secrets must stay in existing Beast/Synapse host configuration mechanisms and environment-variable indirection. Secret-like values are redacted before Synapse provenance hashing.

## Network model

**Network information is not network authority.**

Browser mode may use `fetch`, WebSocket/WebTransport where implemented, localhost Beast services, or explicitly configured LAN/HTTPS services. Wi-Fi scanning/joining and NetworkManager mutation are not implemented by the browser layer in this revision.

No stored Wi-Fi password is exposed to a model, prompt, continuity bundle, or trace.

## Beast Machine

The first implementation is a **browser-controlled Synapse VM** backed by native QEMU on supported Synapse amd64 images.

The QEMU controller:

- requires a configured guest image and expected SHA-256
- verifies the image before launch
- uses snapshot mode
- defaults networking to `none`
- requires separate `vm.network` authority for user-mode networking
- exposes no arbitrary shell/exec interface
- revokes `vm.control` when the guest is destroyed

The repository does not ship an unverified remote guest image. Until a concrete guest image is pinned and physically boot-tested through this controller, VM guest validation is `IMPLEMENTED_NOT_PHYSICALLY_VALIDATED`, not verified.

Browser-hosted WASM virtualization is not implemented in this revision.

## Synapse OS integration

The Synapse image includes:

- `/usr/local/bin/synapse-beastos-web`
- `BeastOS Web` desktop entry and icon
- an `Open BeastOS Web` action in Synapse Control
- the PWA/runtime bridge under `/usr/share/synapse/BEASTOS_WEB_MACHINE`
- the pinned Beast manifest and build receipt under `/usr/share/synapse/beast-kit`
- an isolated Beast runtime at `/opt/synapse/beast-runtime`
- QEMU packages on the initial amd64 path

The privileged cockpit is **not auto-enabled at boot**. The owner launches it explicitly; it binds to loopback.

## Testing

`make check` runs the Python authority/security/unit contracts, browser JavaScript contracts, syntax checks, licensing audit, native ABI/SDK tests, and architecture dry-runs.

The existing `Build and VM smoke test` workflow additionally:

1. materializes the exact pinned Beast release kit
2. installs its wheel into an isolated CI venv
3. initializes the real Beast `runtime exchange` reference provider
4. starts the authenticated BeastOS loopback bridge
5. runs Playwright Chromium E2E
6. records screenshots, trace, video, MP4 conversion, transcript, receipt, environment metadata, and SHA-256 sums
7. builds the Synapse amd64 ISO
8. verifies BeastOS/Beast/QEMU files inside the final SquashFS
9. boots the live ISO in QEMU
10. performs the existing installed-Synapse VM smoke path

Browser E2E with a reference provider is not physical hardware validation and is labeled accordingly in its receipt.

## Demo reproduction

On Synapse OS, use the desktop **BeastOS Web** launcher or:

```sh
synapse-beastos-web
```

For a source checkout with an installed Beast executable:

```sh
PYTHONPATH=. python3 -m BEASTOS_WEB_MACHINE.bridge.server \
  --listen 127.0.0.1 \
  --port 8790 \
  --beast-executable beastbox \
  --beast-data-dir ~/.local/share/beastbox/beastos-web
```

Then open `http://127.0.0.1:8790/`.

A minimal authority/continuity demonstration is:

1. clock in Brain A
2. send a Beast turn
3. grant Brain A one capability
4. clock in Brain B
5. verify grants are empty
6. send another Beast turn through the same Beast data directory
7. inspect Beast continuity and Synapse Trace separately
8. grant `vm.control` only if a verified guest has been configured
9. create/destroy the disposable machine
10. verify the Beast runtime remains outside that VM lifecycle

## Current feature classification

| Feature | Status |
| --- | --- |
| Beast v0.6.0 exchange adapter | IMPLEMENTED_AND_TESTED at unit-contract level; CI E2E pending per commit |
| Persistent continuity through Beast | IMPLEMENTED; end-to-end browser CI must pass before verified wording |
| Model switching / authority reset | IMPLEMENTED_AND_TESTED |
| PWA shell | IMPLEMENTED; browser CI required for verified wording |
| Offline shell | IMPLEMENTED; does not fake API responses |
| Camera / microphone | IMPLEMENTED_NOT_PHYSICALLY_VALIDATED |
| File upload/scope UI | IMPLEMENTED_AND_TESTED at browser-contract level |
| WebGPU | IMPLEMENTED_NOT_PHYSICALLY_VALIDATED |
| Browser-local model | PROTOTYPE / NOT_ESTABLISHED for production use |
| Host-local model | IMPLEMENTED through Beast providers; provider availability is environment-dependent |
| Remote model | IMPLEMENTED through Beast compatible provider rules; explicit opt-in required |
| USB / Serial / Bluetooth | EXPERIMENTAL feature-detection and authority surfaces; physical device validation not established |
| Network status | IMPLEMENTED |
| Native network control | NOT_ESTABLISHED in BeastOS Web |
| QEMU controller | IMPLEMENTED_NOT_PHYSICALLY_VALIDATED with a dedicated guest |
| Synapse image integration | IMPLEMENTED; final status depends on image CI |

Status language is intentionally conservative. A polished UI does not convert a prototype into verified hardware evidence.

## Troubleshooting

- **BEAST RUNTIME UNAVAILABLE:** confirm `/opt/synapse/beast-runtime/bin/beastbox` exists on Synapse, or pass `--beast-executable` in a source run.
- **Camera/mic denied:** browser/OS permission was denied or no device is exposed. BeastOS does not bypass it.
- **VM unavailable:** a guest image + matching SHA-256 were not configured, or QEMU is unavailable on this architecture.
- **Bridge unavailable:** launch `synapse-beastos-web`; the bridge intentionally does not run as an always-on privileged service.
- **Remote provider refused:** use Beast's compatible provider, HTTPS, and explicit remote authorization. There is no silent fallback.
- **Offline:** the PWA shell can load from cache; Beast/host/provider operations remain unavailable until their real endpoint is reachable.

## Non-claims

BeastOS Web does not establish consciousness, sentience, biological life, identity transfer, quantum advantage, extra physical dimensions, or new physics. Browser/VM simulation remains simulation evidence. Physical-world claims require physical-world measurement.
