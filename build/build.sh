#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '\n' < "$REPO_ROOT/VERSION")"
SUITE="${SYNAPSE_SUITE:-trixie}"
REQUESTED_ARCH="${SYNAPSE_ARCH:-$(dpkg --print-architecture 2>/dev/null || uname -m)}"

# Resident Full Zeref is pinned by immutable source/model identities. These are
# intentionally not branch names or "latest" aliases.
ZEREF_BEASTBOX_COMMIT="${ZEREF_BEASTBOX_COMMIT:-e81399d1d040ad23d13bcc49b038a0b6c16ec74d}"
ZEREF_BEASTBOX_REPO="https://github.com/NavisWORLD/The-beast-box-.git"
QC67_REPO="phera-ra/QC67_cosmo"
QC67_ARCH_SHA256="955805d45f7b407ef5cc9b6efe178d9a5f63df5b32eaf539d9aedcbb2967f1dc"
QC67_SERVER_SHA256="02a509f9c2a20f63c38dca186c082bfdc2603aa8b6f1f903ec19a0e709218d87"
QC67_CHECKPOINT_SHA256="aa0cb13c1e67d459db280a53b6407dfc2b5b5f3fd6f640bc43686b70d799acd1"

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
for cmd in lb rsync sha256sum python3 xorriso git curl; do
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
# amd64 path. Other architectures keep their non-destructive compatibility
# framework without silently claiming an installer implementation.
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
mkdir -p config/includes.chroot/usr/lib/synapse/python
rsync -a "$REPO_ROOT/src/synapse" config/includes.chroot/usr/lib/synapse/python/
mkdir -p config/includes.chroot/usr/src/synapse-sdk-c
rsync -a "$REPO_ROOT/sdk/c/" config/includes.chroot/usr/src/synapse-sdk-c/
mkdir -p config/includes.chroot/usr/share/synapse/hardware
cp "$REPO_ROOT/hardware/profiles.json" config/includes.chroot/usr/share/synapse/hardware/profiles.json

# Stage an immutable Beast Box snapshot. The .git directory is excluded from
# the image and no credentials are used or copied by this build step.
ZEREF_SOURCE_STAGE="$WORK/.zeref-beastbox"
rm -rf "$ZEREF_SOURCE_STAGE"
git clone --no-checkout "$ZEREF_BEASTBOX_REPO" "$ZEREF_SOURCE_STAGE"
git -C "$ZEREF_SOURCE_STAGE" checkout --detach "$ZEREF_BEASTBOX_COMMIT"
test "$(git -C "$ZEREF_SOURCE_STAGE" rev-parse HEAD)" = "$ZEREF_BEASTBOX_COMMIT"
mkdir -p config/includes.chroot/usr/src/cosmos-beast-box
rsync -a --exclude='.git' "$ZEREF_SOURCE_STAGE/" config/includes.chroot/usr/src/cosmos-beast-box/

# Bundle the exact QC67 native implementation and checkpoint already used by
# the measured Trinity experiment. Every downloaded byte is SHA-256 pinned.
QC67_ROOT="config/includes.chroot/usr/share/synapse/zeref/qc67"
mkdir -p "$QC67_ROOT/architecture" "$QC67_ROOT/serving" "$QC67_ROOT/weights"
fetch_qc67() {
  local rel="$1"
  local digest="$2"
  local dest="$QC67_ROOT/$rel"
  curl -fsSL "https://huggingface.co/${QC67_REPO}/resolve/main/${rel}?download=true" -o "$dest"
  printf '%s  %s\n' "$digest" "$dest" | sha256sum -c -
}
fetch_qc67 architecture/cosmos_spark_cst.py "$QC67_ARCH_SHA256"
fetch_qc67 serving/cosmos_serve.py "$QC67_SERVER_SHA256"
fetch_qc67 weights/spark_cst.pt "$QC67_CHECKPOINT_SHA256"
cat > config/includes.chroot/usr/share/synapse/zeref/provenance.json <<EOF
{
  "schema": "synapse.zeref.bundle.v1",
  "beastbox_commit": "$ZEREF_BEASTBOX_COMMIT",
  "beastbox_repo": "NavisWORLD/The-beast-box-",
  "qc67_repo": "$QC67_REPO",
  "architecture_sha256": "$QC67_ARCH_SHA256",
  "native_server_sha256": "$QC67_SERVER_SHA256",
  "checkpoint_sha256": "$QC67_CHECKPOINT_SHA256",
  "ibm_credential_embedded": false
}
EOF

# Keep the installed phone USB flasher byte-identical to the source control
# surface used for phone testing. The privileged helper is not auto-enabled;
# this only ships the UI and explicit owner-started launcher.
mkdir -p config/includes.chroot/usr/share/synapse
install -m 0644 "$REPO_ROOT/phone-bootstrap/FLASH_USB.html" \
  config/includes.chroot/usr/share/synapse/FLASH_USB.html

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
echo "Resident Zeref Beast Box commit: $ZEREF_BEASTBOX_COMMIT"
echo "Checksum: $ISO.sha256"
