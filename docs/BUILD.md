# Build Manual

## Supported first target

- Build host: Debian/Ubuntu-family Linux, amd64
- Target: amd64 UEFI/BIOS hybrid ISO
- Base suite: Debian 13 `trixie`

## Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y live-build debootstrap rsync xorriso squashfs-tools
```

Then:

```bash
make check
sudo ./build/build.sh
```

The build script creates an isolated `.work/live-build` tree, copies the tracked package list/rootfs/hooks, runs `lb build`, and exports the ISO + SHA-256 into `out/`.

## Clean

```bash
sudo ./build/clean.sh
```

## Reproducibility notes

The suite is pinned to `trixie`; package patch versions follow the Debian repositories at build time. For bit-for-bit long-term reproduction, add a dated snapshot mirror and record `SOURCE_DATE_EPOCH` in a future release profile.
