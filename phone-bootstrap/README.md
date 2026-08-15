# Synapse Phone Bootstrap

Phone Bootstrap turns a Synapse OS laptop into an authenticated local bootstrap target that a tiny HTML page can control over a routed USB/local link.

## What it does

- serves `phone-bootstrap.html` from the laptop itself
- exposes `GET /v1/health`
- exposes authenticated `GET /v1/device` with hostname, OS/kernel, normalized architecture, CPU/core count, RAM, root disk, battery, local IPv4 addresses, COSMOS port probes, hardware identity and certification profile
- accepts authenticated `POST /v1/hello` so the phone can send `hey, I'm here`
- accepts authenticated `POST /v1/install/start`
- reports progress through `GET /v1/install/status`
- installs or fast-forwards the configured COSMOS Git checkout
- preserves an existing COSMOS checkout when it contains local modifications
- can activate COSMOS through Docker Compose when present, or through the repository Dockerfile as a fallback

API v1.1 adds the `hardware` object to the device response. A known `GALLOP` amd64 machine is reported as profile `asus-cx1700cka-gallop` with state `physical-target` until the real hardware acceptance checklist passes.

The browser never receives a shell endpoint and cannot submit arbitrary commands. There is no wipe, raw-disk, firmware, or reimage route in this API.

## Start it manually

```bash
PYTHONPATH=src python3 -m synapse.phone_bootstrap \
  --listen 0.0.0.0 \
  --port 8787 \
  --allow-install \
  --activate \
  --install-root "$HOME/COSMOS" \
  --token-file /tmp/synapse-phone-token
```

Then open the laptop address from the phone:

```text
http://<laptop-ip>:8787/
```

Paste the token from `/tmp/synapse-phone-token`, press **CONNECT**, then **HEY, I'M HERE** or **INSTALL COSMOS**.

## Synapse OS image integration

The OS image installs a **per-user** `synapse-phone-bootstrap.service`, binds it on port `8787`, and generates a fresh pairing token on service start at:

```text
$XDG_RUNTIME_DIR/synapse-phone-bootstrap-token
```

Read it locally with:

```bash
cat "$XDG_RUNTIME_DIR/synapse-phone-bootstrap-token"
```

The service runs as the signed-in desktop user, not as root. Its install target is `$HOME/COSMOS`, so it does not depend on a hard-coded username.

## USB transport note

The API is transport-independent. A USB cable only works when the phone and laptop establish a routed local connection over that cable, such as USB tethering or another trusted USB networking bridge. The HTML does not depend on WebUSB, so iPhone Safari can use it once the laptop API is reachable.

## GitHub / VM relationship

The required `amd64` GitHub workflow builds the image, verifies the generated filesystem and native ABI, and boots the image through the shared `SYNAPSE_VM_READY` QEMU gate. ARM64 and RISC-V use a separate promotion workflow and remain labeled experimental until that workflow passes for each architecture.

Phone Bootstrap does not flash an image onto the laptop. It identifies a running Synapse OS machine and installs/activates the COSMOS service checkout. Firmware and raw-disk operations remain outside this API.
