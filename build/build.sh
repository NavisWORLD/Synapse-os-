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
for cmd in lb rsync sha256sum python3 xorriso; do
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

LIVE_BOOT="boot=live components hostname=synapse-os username=cory locales=en_US.UTF-8 keyboard-layouts=us quiet splash"
GENESIS_BOOT="boot=live components hostname=synapse-os username=cory locales=en_US.UTF-8 keyboard-layouts=us synapse.genesis=1"

lb config \
  --mode debian \
  --distribution "$SUITE" \
  --architectures "$ARCH" \
  --binary-images "$SYNAPSE_BINARY_IMAGE" \
  --archive-areas "main contrib non-free-firmware" \
  --debian-installer none \
  --apt-recommends true \
  --memtest none \
  --bootappend-live "$LIVE_BOOT" \
  --bootappend-live-failsafe "$GENESIS_BOOT" \
  "${LB_FOREIGN[@]}"

rsync -a "$REPO_ROOT/build/config/" config/
printf '%s\n' "$SYNAPSE_KERNEL_PACKAGE" >> config/package-lists/synapse.list.chroot

# GENESIS v1 performs destructive installation only on the first certified
# amd64 path. Beast Machine also starts with amd64 only: the browser cockpit
# exists on every architecture, but no VM engine is claimed unless installed.
if [[ "$ARCH" == "amd64" ]]; then
  cat >> config/package-lists/synapse.list.chroot <<'GENESIS_PACKAGES'
parted
dosfstools
e2fsprogs
grub-efi-amd64-bin
grub2-common
efibootmgr
squashfs-tools
util-linux
ipheth-utils
qemu-system-x86
qemu-utils
GENESIS_PACKAGES
fi

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
chmod 0755 config/includes.chroot/usr/local/bin/synapse-usb-flash-server
chmod 0755 config/includes.chroot/usr/local/bin/synapse-beastos-web
mkdir -p config/includes.chroot/usr/lib/synapse/python
rsync -a "$REPO_ROOT/src/synapse" config/includes.chroot/usr/lib/synapse/python/
mkdir -p config/includes.chroot/usr/src/synapse-sdk-c
rsync -a "$REPO_ROOT/sdk/c/" config/includes.chroot/usr/src/synapse-sdk-c/
mkdir -p config/includes.chroot/usr/share/synapse/hardware
cp "$REPO_ROOT/hardware/profiles.json" config/includes.chroot/usr/share/synapse/hardware/profiles.json

# Apple Intel support is additive and currently limited to the amd64 live image.
# It reuses the existing GENESIS writer rather than introducing a second disk writer.
if [[ "$ARCH" == "amd64" ]]; then
  mkdir -p config/includes.chroot/usr/share/synapse/apple-intel
  rsync -a "$REPO_ROOT/APPLE_INTEL/" config/includes.chroot/usr/share/synapse/apple-intel/
fi

# Keep the installed phone USB flasher byte-identical to the source control
# surface used for phone testing. The privileged helper is not auto-enabled;
# this only ships the UI and explicit owner-started launcher.
mkdir -p config/includes.chroot/usr/share/synapse
install -m 0644 "$REPO_ROOT/phone-bootstrap/FLASH_USB.html" \
  config/includes.chroot/usr/share/synapse/FLASH_USB.html

# BeastOS Web is source-bound to the exact Beast Box v0.6.0 release asset.
# Online builds fetch the pinned GitHub asset. Offline/reproducible builders may
# provide SYNAPSE_BEAST_KIT_SOURCE, but that file must pass the same exact size
# and SHA-256 verification before anything enters the image.
BEAST_STAGE="$WORK/.beast-kit"
BEAST_ARCHIVE="$BEAST_STAGE/beast-box-combined-0.6.0.zip"
BEAST_EXTRACT="$BEAST_STAGE/extracted"
BEAST_RECEIPT="$BEAST_STAGE/BEAST_KIT_RECEIPT.json"
rm -rf "$BEAST_STAGE"
mkdir -p "$BEAST_STAGE" "$BEAST_EXTRACT"
BEAST_FETCH_ARGS=(
  --destination "$BEAST_ARCHIVE"
  --extract-to "$BEAST_EXTRACT"
)
if [[ -n "${SYNAPSE_BEAST_KIT_SOURCE:-}" ]]; then
  BEAST_FETCH_ARGS+=(--source-file "$SYNAPSE_BEAST_KIT_SOURCE")
fi
python3 "$REPO_ROOT/BEASTOS_WEB_MACHINE/scripts/fetch-beast-kit.py" \
  "${BEAST_FETCH_ARGS[@]}" > "$BEAST_RECEIPT"

BEAST_IMAGE_DIR="config/includes.chroot/usr/share/synapse/beast-kit"
mkdir -p "$BEAST_IMAGE_DIR" config/includes.chroot/usr/share/synapse
install -m 0644 "$REPO_ROOT/BEASTOS_WEB_MACHINE/manifests/beast-v0.6.0.json" \
  "$BEAST_IMAGE_DIR/beast-v0.6.0.json"
install -m 0644 "$BEAST_RECEIPT" "$BEAST_IMAGE_DIR/BEAST_KIT_RECEIPT.json"
for beast_file in \
  cosmos_beast_box-0.6.0-py3-none-any.whl \
  LICENSE \
  RELEASE_PROVENANCE.json \
  SHA256SUMS; do
  test -f "$BEAST_EXTRACT/$beast_file" || { echo "error: verified Beast kit missing $beast_file" >&2; exit 2; }
  install -m 0644 "$BEAST_EXTRACT/$beast_file" "$BEAST_IMAGE_DIR/$beast_file"
done
rsync -a \
  --exclude '__pycache__/' \
  --exclude 'tests/' \
  "$REPO_ROOT/BEASTOS_WEB_MACHINE/" \
  config/includes.chroot/usr/share/synapse/BEASTOS_WEB_MACHINE/

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
  PROVENANCE.md \
  CITATION.cff \
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

# The live rootfs is the immutable GENESIS installation payload. Generate its
# manifest after live-build finishes, then add that manifest to the ISO outside
# filesystem.squashfs so the installer can verify the exact payload before arm.
GENESIS_STAGE="$WORK/.genesis-manifest"
GENESIS_ROOTFS="$GENESIS_STAGE/filesystem.squashfs"
GENESIS_MANIFEST="$GENESIS_STAGE/manifest.json"
GENESIS_VERIFY_DIR="$GENESIS_STAGE/verify"
GENESIS_VERIFY_ROOTFS="$GENESIS_VERIFY_DIR/filesystem.squashfs"
GENESIS_VERIFY_MANIFEST="$GENESIS_VERIFY_DIR/manifest.json"
REMUSTERED_ISO="$WORK/live-image-genesis.iso"
rm -rf "$GENESIS_STAGE" "$REMUSTERED_ISO"
mkdir -p "$GENESIS_STAGE" "$GENESIS_VERIFY_DIR"

xorriso -osirrox on -indev "$built" -extract /live/filesystem.squashfs "$GENESIS_ROOTFS"
BUILD_COMMIT="${SYNAPSE_BUILD_COMMIT:-$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)}"
python3 "$REPO_ROOT/scripts/genesis_manifest.py" generate \
  --image "$GENESIS_ROOTFS" \
  --version "$VERSION" \
  --arch "$ARCH" \
  --commit "$BUILD_COMMIT" \
  --output "$GENESIS_MANIFEST"

xorriso \
  -indev "$built" \
  -outdev "$REMUSTERED_ISO" \
  -boot_image any replay \
  -map "$GENESIS_MANIFEST" /synapse-genesis/manifest.json \
  -commit

cp "$REMUSTERED_ISO" "$ISO"

# Verify the manifest and rootfs from the final remastered ISO, not the staging
# copies, so a broken remaster cannot produce a successful build artifact. The
# verification copy intentionally preserves the original payload basename,
# because image_filename is part of the manifest identity contract.
xorriso -osirrox on -indev "$ISO" -extract /synapse-genesis/manifest.json "$GENESIS_VERIFY_MANIFEST"
xorriso -osirrox on -indev "$ISO" -extract /live/filesystem.squashfs "$GENESIS_VERIFY_ROOTFS"
python3 "$REPO_ROOT/scripts/genesis_manifest.py" verify \
  --manifest "$GENESIS_VERIFY_MANIFEST" \
  --image "$GENESIS_VERIFY_ROOTFS"

sha256sum "$ISO" > "$ISO.sha256"
echo "Synapse OS image: $ISO"
echo "GENESIS boot mode: live failsafe entry (synapse.genesis=1)"
echo "GENESIS manifest: /synapse-genesis/manifest.json"
echo "Checksum: $ISO.sha256"
