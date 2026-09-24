# Synapse OS — AMD64 virtual-machine installation

Synapse OS Nebula is a Debian 13 / KDE Plasma 6 **alpha**. The AMD64 build and
GENESIS disposable-disk installation have automated QEMU coverage. A headless
guest-ready marker verifies the installed OS reaches its system smoke test; it
does **not** certify graphical login, acceleration, audio, camera, suspend or
every VM platform. Follow the manual acceptance checklist before declaring a
particular VM configuration usable.

**Never point a VM installer or media writer at your host's physical disk.**
Use a new, disposable virtual disk and keep host backups.

## Obtain the image and verify it

Download the matching AMD64 ISO and `.iso.sha256` from a completed
[Build and VM smoke test](https://github.com/NavisWORLD/Synapse-os-/actions/workflows/build-vm-smoke.yml)
run. Its workflow artifacts are temporary; the
[Releases](https://github.com/NavisWORLD/Synapse-os-/releases) page contains
separately built, versioned installers. Do not assume a previous release has
the same code or image checksum as the current main branch.

Release ISO parts must be reassembled and checked as described in
[USB_INSTALL.md](../USB_INSTALL.md). On Linux, with the ISO and its checksum in
the same directory:

```bash
sha256sum -c SynapseOS-Nebula-amd64.iso.sha256
```

Stop if the checksum does not match. The checksum file must refer to the actual
ISO filename. Keep the `VERSION`, commit SHA, run URL and checksum with your
test notes.

## Suggested VM allocation

| Setting | Starting point |
| --- | --- |
| Guest architecture | x86_64 / AMD64 |
| RAM | 8 GiB for graphical desktop testing; automated headless gate uses 4 GiB |
| CPU | 4 virtual CPUs, if available; automated gate uses 2 |
| Virtual disk | New, disposable 32 GiB virtual disk (sparse / dynamically allocated is fine) |
| Firmware | UEFI (OVMF on QEMU); avoid assuming Secure Boot support |
| Network | NAT, with user consent; offline live boot is also valid |
| Display | VM's ordinary graphical console, not the headless CI serial port |

These are testing starting points, not measured minimum requirements. AMD64
on an ARM host needs full-system emulation; a native ARM64 VM cannot directly
boot an AMD64 image.

## VirtualBox and VMware / similar desktop hypervisors

1. Create a **new Linux, 64-bit** VM with a new virtual disk. Enable EFI if
   supported. Do not attach a raw physical disk.
2. Attach the checksum-verified ISO as the virtual optical drive. Boot it.
3. Test the live desktop before installing. Open **Synapse Control** and
   **BeastOS Web** from the launcher. An offline or missing model provider
   must show unavailable, not a fabricated connected status.
4. If the graphical **Install Synapse OS** launcher is available, follow its
   Calamares flow and select **only the disposable VM disk**. GENESIS is a
   separately gated install path, primarily tested on disposable QEMU storage.
5. Shut down, detach the ISO, boot the virtual disk and complete the manual
   checks below. If the installed system does not boot, preserve the VM console
   output and do not erase your original host system.

VirtualBox and VMware are **manual validation targets**, not automatically
certified by the existing QEMU CI.

## QEMU / KVM on an AMD64 Linux host

Install QEMU and OVMF with your distribution package manager, then check the
available firmware paths; they vary by distribution. The example below assumes
the Debian/Ubuntu 4 MiB OVMF pair:

```bash
test -r /usr/share/OVMF/OVMF_CODE_4M.fd
test -r /usr/share/OVMF/OVMF_VARS_4M.fd
cp /usr/share/OVMF/OVMF_VARS_4M.fd ./synapse-OVMF_VARS.fd
qemu-img create -f qcow2 synapse-test.qcow2 32G

qemu-system-x86_64 \
  -machine q35,accel=kvm \
  -cpu host -smp 4 -m 8192 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=./synapse-OVMF_VARS.fd \
  -drive file=./synapse-test.qcow2,format=qcow2,if=virtio \
  -drive file=./SynapseOS-Nebula-amd64.iso,media=cdrom,readonly=on \
  -nic user,model=virtio-net-pci \
  -boot order=d
```

Run the graphical installer within the guest, shut it down and **remove the
ISO drive line** for the installed cold boot. Change `-boot order=d` to
`-boot order=c`. For an AMD64 host without KVM access, replace
`-machine q35,accel=kvm -cpu host` with
`-machine q35,accel=tcg -cpu max`; emulation will be slower.

The repository's independent automated installation gate is
`scripts/genesis-installed-vm-smoke.sh`. It builds a temporary sparse image,
connects only an unused NBD device, exercises the real GENESIS writer,
disconnects NBD, then cold-boots the virtual drive using OVMF. **Do not copy
the CI script's privileged NBD commands into a physical installer workflow.**

## Manual graphical and daily-use acceptance

Record PASS / FAIL / NOT TESTED and a screenshot or guest log for each:

- Live boot and installed cold boot reach a graphical login and Plasma session.
- Login, application launcher, panel, file manager, settings and terminal work.
- Synapse Control launches, reports the real guest CPU/RAM/disk and runs
  `synapse doctor`.
- Network, DNS, package updates, PipeWire audio and display resizing work
  (or explicitly record missing virtual devices and offline mode).
- BeastOS opens through its loopback-only bridge; a missing local AI model
  fails gracefully. No host authority or secrets transfer on model swap.
- Calamares displays the **virtual** target and completes a fresh install.
  Preserve the installation receipt and confirm the second cold boot.
- Restart, shutdown, package updates, disk persistence and recovery entry
  function in the same VM.

Only mark a VM configuration verified when these checks have actual evidence.
The AMD64 headless CI passing does not certify physical laptops, ARM64/RISC-V,
or the integrated RAWRPHØS model.

## Physical disk installation

Read [USB_INSTALL.md](../USB_INSTALL.md) and
[docs/INSTALL.md](INSTALL.md) before preparing a separate USB image. Back up
the real machine and verify the checksum. The automated installer is tested
against disposable virtual disks, not your particular physical hardware.
