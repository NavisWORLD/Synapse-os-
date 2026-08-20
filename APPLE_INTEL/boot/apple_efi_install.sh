#!/usr/bin/env bash
set -Eeuo pipefail
ESP=""; ROOT=""; DRY=0
usage(){ echo "usage: $0 --esp /dev/<esp-partition> --root /dev/<synapse-root-partition> [--dry-run]" >&2; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --esp) ESP="${2:-}"; shift 2;;
    --root) ROOT="${2:-}"; shift 2;;
    --dry-run) DRY=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "error: unknown argument $1" >&2; usage; exit 2;;
  esac
done
[[ "$ESP" == /dev/* && "$ROOT" == /dev/* ]] || { echo "error: --esp and --root must be explicit /dev paths" >&2; usage; exit 2; }
[[ "$ESP" != "$ROOT" ]] || { echo "error: ESP and root must be different partitions" >&2; exit 2; }
for dev in "$ESP" "$ROOT"; do [[ -b "$dev" ]] || { if [[ "$DRY" != 1 ]]; then echo "error: not a block device: $dev" >&2; exit 2; fi; }; done

if [[ "$DRY" == 1 ]]; then
  echo "DRY RUN: grub-install --target=x86_64-efi --removable --no-nvram --efi-directory=<esp> --boot-directory=<esp>/boot"
  echo "DRY RUN: root=$ROOT esp=$ESP"
  exit 0
fi
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "error: run as root for EFI repair" >&2; exit 2; }
for cmd in mount umount grub-install blkid; do command -v "$cmd" >/dev/null 2>&1 || { echo "error: missing $cmd" >&2; exit 2; }; done
MOUNT_BASE="$(mktemp -d /tmp/synapse-apple-efi.XXXXXX)"
ROOT_MOUNT="$MOUNT_BASE/root"
ESP_MOUNT="$MOUNT_BASE/esp"
mkdir -p "$ROOT_MOUNT" "$ESP_MOUNT"
cleanup(){ set +e; mountpoint -q "$ESP_MOUNT" && umount "$ESP_MOUNT"; mountpoint -q "$ROOT_MOUNT" && umount "$ROOT_MOUNT"; rm -rf "$MOUNT_BASE"; }
trap cleanup EXIT
mount "$ROOT" "$ROOT_MOUNT"
mount "$ESP" "$ESP_MOUNT"
ROOT_UUID="$(blkid -s UUID -o value "$ROOT")"
[[ -n "$ROOT_UUID" ]] || { echo "error: root UUID unavailable" >&2; exit 3; }
KERNEL="$(find "$ROOT_MOUNT/boot" -maxdepth 1 -type f -name 'vmlinuz-*' -printf '%f\n' | sort | tail -n1)"
INITRD="$(find "$ROOT_MOUNT/boot" -maxdepth 1 -type f -name 'initrd.img-*' -printf '%f\n' | sort | tail -n1)"
[[ -n "$KERNEL" && -n "$INITRD" ]] || { echo "error: Synapse kernel/initramfs not found under root /boot" >&2; exit 3; }
mkdir -p "$ESP_MOUNT/boot"
grub-install --target=x86_64-efi --efi-directory="$ESP_MOUNT" --boot-directory="$ESP_MOUNT/boot" --removable --no-nvram
mkdir -p "$ESP_MOUNT/boot/grub"
cat > "$ESP_MOUNT/boot/grub/grub.cfg" <<EOF
set timeout=5
set default=0
menuentry 'Synapse OS // Apple Intel' {
  search --no-floppy --fs-uuid --set=root $ROOT_UUID
  linux /boot/$KERNEL root=UUID=$ROOT_UUID rw quiet splash
  initrd /boot/$INITRD
}
EOF
sync
echo "Synapse fallback EFI boot path repaired without modifying Apple NVRAM."
