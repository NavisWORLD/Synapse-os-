# COSMOS // GENESIS v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated phone-controlled Synapse OS installer that can safely identify one internal GALLOP target, verify the live Synapse rootfs payload, require a one-time destructive arm challenge, and install from a dedicated live/installer environment without exposing generic shell or disk-write APIs.

**Architecture:** Keep the existing v1 COSMOS bootstrap intact. Add a focused `synapse.genesis` policy/state module, a separate privileged `synapse.genesis_writer` installer implementation, thin `/v2` routing in `phone_bootstrap.py`, and a single-file `GENESIS.html` client. The bootable ISO carries a manifest outside `filesystem.squashfs`; when booted with `synapse.genesis=1`, a root-only system service enables the destructive installer path while the normal per-user bootstrap is disabled.

**Tech Stack:** Python 3.10+, stdlib HTTP server/subprocess/hashlib/json/secrets, Linux `lsblk`, `findmnt`, `parted`, `mkfs.vfat`, `mkfs.ext4`, `unsquashfs`, `grub-install`, `blkid`, `sync`, systemd, Debian live-build, xorriso, HTML/CSS/vanilla JavaScript, unittest, GitHub Actions/QEMU.

## Global Constraints

- First destructive physical target: ASUS Chromebook CX1700CKA / `GALLOP`, `amd64`.
- Existing v1 Phone Bootstrap API remains compatible.
- No `/shell`, `/exec`, request-controlled command, generic disk writer, firmware-unlock, credential, persistence, or monitoring-disable API.
- Destructive install is disabled unless the daemon runs with explicit installer-mode configuration in a dedicated live environment.
- Installer mode additionally requires Linux kernel command line marker `synapse.genesis=1`.
- Target selection is fail-closed: exactly one eligible whole internal non-removable non-USB disk, excluding the source/live-media disk when identifiable.
- Phone requests never choose the disk path or image path.
- Image source is fixed by daemon configuration and verified against a fixed manifest.
- Manifest must include Synapse version, architecture, image filename/type/size/SHA-256, build commit, `Cory Davis / NavisWORLD Synapse Source License 1.0`, and Zenodo DOI `10.5281/zenodo.17574447`.
- Arm challenge is random, short-lived, in-memory, one-time, and bound to device fingerprint, target fingerprint, and image SHA-256.
- Writer revalidates target fingerprint and image SHA-256 immediately before destructive work.
- CI never writes a real block device; destructive commands are tested through simulation/fakes.
- GALLOP remains `physical-target` until a real-device install/certification run passes.

---

### Task 1: GENESIS policy, device inventory, manifest verification, and arm challenge

**Files:**
- Create: `src/synapse/genesis.py`
- Create: `tests/test_genesis.py`

**Interfaces:**
- Produces: `GenesisError(code, message)`, `BlockDevice`, `ImageManifest`, `GenesisPreflight`, `inventory_block_devices()`, `select_install_target()`, `verify_manifest()`, `GenesisManager`.
- `GenesisManager.preflight() -> dict[str, Any]`
- `GenesisManager.image_status() -> dict[str, Any]`
- `GenesisManager.arm() -> dict[str, Any]`
- `GenesisManager.start(challenge_id: str, acknowledgement: str) -> dict[str, Any]`
- `GenesisManager.status() -> dict[str, Any]`
- `GenesisManager.receipt() -> dict[str, Any] | None`

- [ ] Write failing tests using synthetic `lsblk` JSON for one internal eMMC target, removable USB rejection, ambiguous dual-internal rejection, and source-media exclusion.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_genesis -v` and confirm failures because `synapse.genesis` does not exist.
- [ ] Implement immutable block-device parsing and fail-closed target selection. Use `lsblk --json --bytes -o NAME,KNAME,PATH,TYPE,SIZE,RM,ROTA,TRAN,MODEL,SERIAL,PKNAME,MOUNTPOINTS` and `findmnt -n -o SOURCE /run/live/medium` when available. Never hard-code `/dev/sda`.
- [ ] Add tests for manifest architecture/size/hash/license/DOI checks using temporary files and SHA-256.
- [ ] Implement `ImageManifest.from_path()` and `verify_manifest()` for manifest schema `synapse-genesis-manifest/v1`, image type `squashfs-rootfs`, exact size, SHA-256, architecture, license, DOI, and target-capacity check.
- [ ] Add tests for challenge issuance, expiry, replay, acknowledgement mismatch, device mismatch, target mismatch, and image mismatch.
- [ ] Implement `GenesisManager` arm state with `secrets.token_urlsafe(24)`, 120-second default expiry, exact acknowledgement `ERASE:<target_fingerprint>:INSTALL:<image_sha256>`, and one-time consumption.
- [ ] Add receipt tests requiring hardware profile/HWID/architecture, target metadata, image metadata, challenge ID, phase history, license identifier, and Zenodo DOI.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_genesis -v`; require all tests green.
- [ ] Commit Task 1.

### Task 2: Dedicated installer writer and safe simulation

**Files:**
- Create: `src/synapse/genesis_writer.py`
- Create: `tests/test_genesis_writer.py`

**Interfaces:**
- Consumes: immutable install plan emitted by `GenesisManager`.
- Produces: `validate_install_plan(plan, ...)`, `run_install(plan_path, receipt_path, execute=False)`, CLI `python3 -m synapse.genesis_writer`.

- [ ] Write failing tests proving writer refuses execution without installer mode, without `synapse.genesis=1`, with non-root execution, target fingerprint mismatch, image hash mismatch, removable/USB target, or source-media target.
- [ ] Implement plan schema `synapse-genesis-plan/v1` with fixed image path and target path copied from server-side preflight only.
- [ ] Implement simulation mode that validates every destructive prerequisite and emits the full phase sequence without invoking partition/filesystem commands.
- [ ] Add fake-command-runner tests that assert destructive command construction is argv-only, never `shell=True`, and never consumes command text from plan/UI fields.
- [ ] Implement amd64 installer sequence for `squashfs-rootfs`: unmount target children; `wipefs -a`; GPT via `parted`; 512 MiB FAT32 ESP + ext4 root; `mkfs.vfat`; `mkfs.ext4`; mount root/ESP; `unsquashfs -f -d`; generate `/etc/fstab`; install removable UEFI GRUB with `grub-install --target=x86_64-efi --removable --no-nvram`; generate minimal UUID-based GRUB config; copy receipt into `/var/lib/synapse/genesis/receipt.json`; `sync`; verify installed markers; unmount.
- [ ] Refuse destructive writer on non-`amd64` for v1 with stable `ARCH_MISMATCH` error.
- [ ] Ensure cleanup unmounts temporary mountpoints in `finally` without masking the original error.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_genesis_writer -v`; require green.
- [ ] Commit Task 2.

### Task 3: Wire GENESIS v2 into the local HTTP API

**Files:**
- Modify: `src/synapse/phone_bootstrap.py`
- Modify: `tests/test_phone_bootstrap.py`

**Interfaces:**
- Adds public `GET /v2/health`.
- Adds authenticated `GET /v2/device`, `/v2/preflight`, `/v2/image`, `/v2/install/status`, `/v2/install/receipt`.
- Adds authenticated `POST /v2/hello`, `/v2/install/arm`, `/v2/install/start`.
- Adds CLI flags `--genesis-manifest`, `--genesis-image`, `--genesis-staging-dir`, `--genesis-installer-mode`, `--genesis-simulation`, `--genesis-ui-path`.

- [ ] Write failing HTTP tests for v2 health, auth, preflight, arm/start, structured error code JSON, and GENESIS UI route.
- [ ] Refactor server construction to accept a `GenesisManager` without changing v1 behavior.
- [ ] Map `GenesisError.code` to JSON `{ok:false,error:{code,message}}`; preserve existing v1 error shape for v1 endpoints.
- [ ] Implement `GET /GENESIS.html` and `/genesis` route resolution.
- [ ] Require challenge ID + exact acknowledgement body for `/v2/install/start`; ignore/reject any request fields attempting to provide disk/image/command paths.
- [ ] Run `PYTHONPATH=src:. python3 -m unittest tests.test_phone_bootstrap -v`; require v1 and v2 tests green.
- [ ] Commit Task 3.

### Task 4: Build the single-file GENESIS phone UI

**Files:**
- Create: `phone-bootstrap/GENESIS.html`
- Create: `rootfs/usr/share/synapse/GENESIS.html`
- Modify: `tests/test_phone_bootstrap.py`

**Interfaces:**
- Consumes only documented `/v2` JSON endpoints.
- Produces phone controls `CONNECT`, `HEY, I'M HERE`, `REFRESH PREFLIGHT`, and press-and-hold `INSTALL SYNAPSE OS`.

- [ ] Add source-smoke tests requiring endpoint strings, hold-to-confirm logic, acknowledgement construction, destructive warning text, hardware/profile/image/target rendering, status polling, receipt rendering, and no `/shell`/`/exec` strings.
- [ ] Implement responsive single-file HTML/CSS/JS using the existing cosmic visual language.
- [ ] Disable arming unless preflight reports `ready=true`; render every preflight check and stable error code.
- [ ] Implement a 2.5-second pointer/touch hold. On completion call `/v2/install/arm`, display the server-bound target/image identifiers, construct the exact acknowledgement from the arm response, then call `/v2/install/start`.
- [ ] Poll `/v2/install/status` every 1.5 seconds and fetch `/v2/install/receipt` on terminal states.
- [ ] Keep pairing token in localStorage as v1 does; never persist the one-time arm challenge after the page session.
- [ ] Verify repository and rootfs copies are byte-identical.
- [ ] Run phone-bootstrap tests again.
- [ ] Commit Task 4.

### Task 5: Dedicated live-installer system service and toolchain

**Files:**
- Create: `rootfs/usr/lib/systemd/system/synapse-genesis-installer-api.service`
- Create: `rootfs/usr/local/bin/synapse-genesis-writer`
- Modify: `rootfs/usr/lib/systemd/user/synapse-phone-bootstrap.service`
- Modify: `build/hooks/020-phone-bootstrap.hook.chroot`
- Modify: `build/build.sh`
- Modify: `Makefile`

**Interfaces:**
- Dedicated service runs only when kernel command line includes `synapse.genesis=1` and `/run/live/medium/synapse-genesis/manifest.json` exists.
- Normal user bootstrap refuses to start under `synapse.genesis=1` to avoid port collision.

- [ ] Add tests/static checks for systemd conditions and wrapper syntax before creating files.
- [ ] Add root system service on port 8787 with explicit `--genesis-installer-mode`, fixed manifest `/run/live/medium/synapse-genesis/manifest.json`, fixed image `/run/live/medium/live/filesystem.squashfs`, staging `/run/synapse-genesis`, and token `/run/synapse-genesis/token`.
- [ ] Add `ConditionKernelCommandLine=synapse.genesis=1` and `ConditionPathExists=/run/live/medium/synapse-genesis/manifest.json`; do not enable destructive mode in the per-user service.
- [ ] Add user-service negative kernel condition to prevent a port collision in GENESIS mode.
- [ ] Add root wrapper for `python3 -m synapse.genesis_writer`.
- [ ] Extend build hook to enable the installer API system service; systemd conditions keep it dormant in normal boots.
- [ ] For amd64 builds append required installer packages `parted`, `dosfstools`, `e2fsprogs`, `grub-efi-amd64-bin`, `grub2-common`, `efibootmgr`, `squashfs-tools`, `util-linux`.
- [ ] Extend `make lint` shell/unit syntax checks.
- [ ] Commit Task 5.

### Task 6: Generate and embed the immutable GENESIS manifest in the ISO

**Files:**
- Create: `scripts/genesis_manifest.py`
- Create: `tests/test_genesis_manifest.py`
- Modify: `build/build.sh`

**Interfaces:**
- CLI: `python3 scripts/genesis_manifest.py --image <filesystem.squashfs> --version <VERSION> --arch amd64 --commit <sha> --output <manifest.json>`.
- Manifest schema: `synapse-genesis-manifest/v1`.

- [ ] Write failing tests for deterministic manifest JSON, exact size/SHA-256, license identifier, DOI, build commit, and architecture.
- [ ] Implement manifest generator with no network access.
- [ ] After `lb build`, extract `/live/filesystem.squashfs` from the produced ISO, generate manifest, and remaster the ISO with xorriso `-boot_image any replay` so `/synapse-genesis/manifest.json` lives outside the squashfs on the boot medium.
- [ ] Recompute final ISO SHA-256 only after remastering.
- [ ] Add a build-time verification that extracts the final manifest and confirms its recorded squashfs SHA-256/size match the final ISO payload.
- [ ] Run manifest tests and `SYNAPSE_DRY_RUN=1 SYNAPSE_ARCH=amd64 ./build/build.sh`.
- [ ] Commit Task 6.

### Task 7: Documentation and CI evidence

**Files:**
- Create: `GENESIS.md`
- Modify: `PHONE_BOOTSTRAP.md`
- Modify: `phone-bootstrap/README.md`
- Modify: `README.md`
- Modify: `.github/workflows/build-vm-smoke.yml`
- Modify: `tests/test_license_policy.py`

**Interfaces:**
- Documents dedicated live-boot requirement and exact physical readiness boundary.
- CI proves GENESIS assets/manifest are present but does not execute destructive writer.

- [ ] Document booting the prepared Synapse live environment with kernel argument `synapse.genesis=1`, reading the local pairing token, connecting GENESIS.html, preflight/arming, and the fact that firmware preparation remains physical/manual.
- [ ] Document that the destructive writer is code-complete/CI-simulated but physical GALLOP install remains uncertified until a real device test succeeds.
- [ ] Extend CI extraction checks to require `GENESIS.html`, `synapse/genesis.py`, `synapse/genesis_writer.py`, systemd installer unit, wrapper, and `/synapse-genesis/manifest.json`.
- [ ] In CI extract the manifest and filesystem.squashfs and run the manifest verifier against the built artifact.
- [ ] Add a writer simulation invocation against synthetic plan/target fixtures only; never pass a real `/dev/*` target.
- [ ] Preserve license/Zenodo embedding checks.
- [ ] Commit Task 7.

### Task 8: Full verification and integration

**Files:**
- Review all branch changes.

**Interfaces:**
- Produces reviewable PR from `feature/genesis-installer-v1` to `main`.

- [ ] Run/require `make check` on the exact branch head.
- [ ] Review diff for unrelated code, request-controlled command/path injection, shell execution, hard-coded target disk, firmware bypass, or destructive default enablement.
- [ ] Open a draft PR with the physical-certification boundary clearly stated.
- [ ] Require GitHub Actions source-validation success.
- [ ] Require amd64 ISO build and checksum success.
- [ ] Require generated filesystem and external GENESIS manifest inspection success.
- [ ] Require QEMU `SYNAPSE_VM_READY` boot success.
- [ ] Mark PR ready only after all required non-destructive gates pass.
- [ ] Do not call GALLOP physically certified until the real Chromebook install has been performed and evidence recorded.
