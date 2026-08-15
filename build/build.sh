#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"
SUITE="${SYNAPSE_SUITE:-trixie}"
REQUESTED_ARCH="${SYNAPSE_ARCH:-$(dpkg --print-architecture 2>/dev/null || uname -m)}"

eval "$(python3 "$REPO_ROOT/scripts/arch_matrix.py" shell "$REQUESTED_ARCH")"
ARCH="$SYNAPSE_ARCH_NORMALIZED"
WORK="$REPO_ROOT/.work/live-build-$ARCH"
OUT="$REPO_ROOT/out"
ISO="$OUT/SynapseOS-${VERSION}-${ARCH}.iso"

HOST_RAW="$(dpkg --print-architecture 2>/dev/null || uname -m)"
HOST_ARCH="$(python3 "$REPO_ROOT/scripts/arch_matrix.py" normalize "$HOST_RAW")"
LB_FOREIGN=()
FOREIGN=0
if [[ "$HOST_ARCH" != "$ARCH" ]]; then
  FOREIGN=1
  LB_FOREIGN+=(--bootstrap-qemu-arch "$SYNAPSE_BOOTSTRAP_QEMU_ARCH" --bootstrap-qemu-static "$SYNAPSE_QEMU_STATIC")
fi

if [[ "${SYNAPSE_DRY_RUN:-0}" == "1" ]]; then
  printf 'arch=%s\nhost_arch=%s\nforeign=%s\nkernel=%s\nbinary_image=%s\nsupport_state=%s\nqemu_static=%s\n' \
    "$ARCH" "$HOST_ARCH" "$FOREIGN" "$SYNAPSE_KERNEL_PACKAGE" "$SYNAPSE_BINARY_IMAGE" "$SYNAPSE_SUPPORT_STATE" "$SYNAPSE_QEMU_STATIC"
  exit 0
fi

if [[ "$FOREIGN" == "1" && ( -z "$SYNAPSE_QEMU_STATIC" || ! -x "$SYNAPSE_QEMU_STATIC" ) ]]; then
  echo "error: foreign $ARCH build on $HOST_ARCH requires $SYNAPSE_QEMU_STATIC" >&2
  exit 2
fi
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "error: live-build needs root for chroot/mount operations; run: sudo ./build/build.sh" >&2
  exit 2
fi
for cmd in lb rsync sha256sum python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: missing $cmd" >&2; exit 2; }
done
python3 - "$WORK" "$REPO_ROOT" <<'PYSAFE'
from pathlib import Path
import shutil, sys
work = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]).resolve()
expected_parent = (root / ".work").resolve()
if work.parent != expected_parent or not work.name.startswith("live-build-"):
    raise SystemExit(f"refusing unsafe cleanup path: {work}")
shutil.rmtree(work, ignore_errors=True)
PYSAFE
mkdir -p "$WORK" "$OUT"
cd "$WORK"

lb config \
  --mode debian \
  --distribution "$SUITE" \
  --architectures "$ARCH" \
  --binary-images "$SYNAPSE_BINARY_IMAGE" \
  --archive-areas "main contrib non-free-firmware" \
  --debian-installer none \
  --apt-recommends true \
  --memtest none \
  --bootappend-live "boot=live components hostname=synapse-os username=cory locales=en_US.UTF-8 keyboard-layouts=us quiet splash" \
  "${LB_FOREIGN[@]}"

rsync -a "$REPO_ROOT/build/config/" config/
printf '%s\n' "$SYNAPSE_KERNEL_PACKAGE" >> config/package-lists/synapse.list.chroot

if [[ "$SUITE" == "trixie" ]]; then
  python3 - "config/package-lists/nebula-ui.list.chroot" <<'PYCOMPAT'
from pathlib import Path
import sys
path = Path(sys.argv[1])
if path.exists():
    lines = path.read_text(encoding="utf-8").splitlines()
    lines = [line for line in lines if line.strip() != "plasma-workspace-wayland"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PYCOMPAT
fi

mkdir -p config/includes.chroot config/hooks/live
rsync -a "$REPO_ROOT/rootfs/" config/includes.chroot/
chmod 0755 config/includes.chroot/usr/local/bin/synflow
mkdir -p config/includes.chroot/usr/lib/synapse/python
rsync -a "$REPO_ROOT/src/synapse" config/includes.chroot/usr/lib/synapse/python/
mkdir -p config/includes.chroot/usr/src/synapse-sdk-c
rsync -a "$REPO_ROOT/sdk/c/" config/includes.chroot/usr/src/synapse-sdk-c/
mkdir -p config/includes.chroot/usr/share/synapse/hardware
cp "$REPO_ROOT/hardware/profiles.json" config/includes.chroot/usr/share/synapse/hardware/profiles.json

# Ship the controlling first-party license and provenance notices inside every
# generated Synapse OS image. Third-party package licenses remain available
# through their own package metadata and are not replaced by these files.
LEGAL_DIR="config/includes.chroot/usr/share/doc/synapse-os"
mkdir -p "$LEGAL_DIR"
for legal_file in \
  LICENSE \
  NOTICE \
  COMMERCIAL-LICENSING.md \
  LICENSE-HISTORY.md \
  TRADEMARKS.md \
  THIRD_PARTY_NOTICES.md; do
  install -m 0644 "$REPO_ROOT/$legal_file" "$LEGAL_DIR/$legal_file"
done

rsync -a "$REPO_ROOT/build/hooks/" config/hooks/live/
chmod +x config/hooks/live/*.hook.chroot

lb build
built="$(find . -maxdepth 1 -type f \( -name 'live-image-*.hybrid.iso' -o -name 'live-image-*.iso' \) | head -n1)"
if [[ -z "$built" ]]; then
  echo "error: live-build completed without an ISO" >&2
  exit 3
fi
cp "$built" "$ISO"
sha256sum "$ISO" > "$ISO.sha256"
echo "Synapse OS image: $ISO"
echo "Checksum: $ISO.sha256"
