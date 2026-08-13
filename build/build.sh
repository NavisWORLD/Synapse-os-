#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"
ARCH="${SYNAPSE_ARCH:-amd64}"
SUITE="${SYNAPSE_SUITE:-trixie}"
WORK="$REPO_ROOT/.work/live-build"
OUT="$REPO_ROOT/out"
ISO="$OUT/SynapseOS-${VERSION}-${ARCH}.iso"

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
expected = (root / ".work" / "live-build").resolve()
if work != expected:
    raise SystemExit(f"refusing unsafe cleanup path: {work}")
shutil.rmtree(work, ignore_errors=True)
PYSAFE
mkdir -p "$WORK" "$OUT"
cd "$WORK"

lb config \
  --mode debian \
  --distribution "$SUITE" \
  --architectures "$ARCH" \
  --binary-images iso-hybrid \
  --archive-areas "main contrib non-free-firmware" \
  --debian-installer none \
  --apt-recommends true \
  --memtest none \
  --bootappend-live "boot=live components hostname=synapse-os username=cory locales=en_US.UTF-8 keyboard-layouts=us quiet splash"

rsync -a "$REPO_ROOT/build/config/" config/

# Plasma 6 in Debian 13 folds the Wayland session into plasma-workspace.
# Older Debian releases used a separate plasma-workspace-wayland package.
# Keep the source manifest readable across generations, but remove that legacy
# package name from the generated trixie build configuration before live-build
# resolves packages.
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
mkdir -p config/includes.chroot/usr/lib/synapse/python
rsync -a "$REPO_ROOT/src/synapse" config/includes.chroot/usr/lib/synapse/python/
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
