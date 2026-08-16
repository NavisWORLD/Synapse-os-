#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <SynapseOS-amd64.iso>" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO="$(realpath "$1")"
[[ -f "$ISO" ]] || { echo "error: ISO not found: $ISO" >&2; exit 2; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "error: GENESIS installed-disk smoke must run as root" >&2
  exit 2
fi

for cmd in qemu-nbd qemu-system-x86_64 truncate modprobe xorriso python3 mount umount sed grep cp sync udevadm; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: missing $cmd" >&2; exit 2; }
done

TMP="$(mktemp -d -t synapse-genesis-installed.XXXXXX)"
DISK="$TMP/synapse-installed.raw"
ROOTFS="$TMP/filesystem.squashfs"
MANIFEST="$TMP/manifest.json"
MOUNT_ROOT="$TMP/installed-root"
MOUNT_ESP="$TMP/installed-esp"
SERIAL_LOG="$TMP/installed-serial.log"
OUT_LOG="${SYNAPSE_GENESIS_INSTALLED_LOG:-/tmp/synapse-vm/synapse-genesis-installed-vm.log}"
NBD=""
NBD_CONNECTED=0
ROOT_MOUNTED=0
ESP_MOUNTED=0
VM_PID=""

copy_log() {
  if [[ -f "$SERIAL_LOG" ]]; then
    mkdir -p "$(dirname "$OUT_LOG")"
    cp "$SERIAL_LOG" "$OUT_LOG" || true
  fi
}

cleanup() {
  if [[ -n "$VM_PID" ]]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
  if [[ "$ESP_MOUNTED" == "1" ]]; then
    umount "$MOUNT_ESP" 2>/dev/null || true
  fi
  if [[ "$ROOT_MOUNTED" == "1" ]]; then
    umount "$MOUNT_ROOT" 2>/dev/null || true
  fi
  if [[ "$NBD_CONNECTED" == "1" && -n "$NBD" ]]; then
    qemu-nbd --disconnect "$NBD" >/dev/null 2>&1 || true
  fi
  copy_log
  rm -rf "$TMP"
}
trap cleanup EXIT

# The virtual target is intentionally large enough for the current rootfs
# multiplier while remaining sparse on the CI host. No physical disk path is
# accepted or constructed by this script.
truncate -s 16G "$DISK"
modprobe nbd max_part=16
udevadm settle

for sysdev in /sys/class/block/nbd*; do
  [[ -e "$sysdev" ]] || continue
  candidate="/dev/$(basename "$sysdev")"
  [[ -b "$candidate" ]] || continue
  if [[ ! -e "$sysdev/pid" ]]; then
    NBD="$candidate"
    break
  fi
done
[[ -n "$NBD" ]] || { echo "error: no unused NBD device is available" >&2; exit 3; }

case "$NBD" in
  /dev/nbd[0-9]*) ;;
  *) echo "error: refusing non-NBD target: $NBD" >&2; exit 3 ;;
esac

echo "GENESIS installed-disk smoke target: $NBD -> temporary sparse image"
qemu-nbd --connect="$NBD" --format=raw "$DISK"
NBD_CONNECTED=1
udevadm settle

xorriso -osirrox on -indev "$ISO" -extract /live/filesystem.squashfs "$ROOTFS" >/dev/null 2>&1
xorriso -osirrox on -indev "$ISO" -extract /synapse-genesis/manifest.json "$MANIFEST" >/dev/null 2>&1

export PYTHONPATH="$REPO_ROOT/src"
export SYNAPSE_GENESIS_TEST_NBD="$NBD"
export SYNAPSE_GENESIS_TEST_ROOTFS="$ROOTFS"
export SYNAPSE_GENESIS_TEST_MANIFEST="$MANIFEST"
export SYNAPSE_GENESIS_TEST_TMP="$TMP"

python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path
import time

from synapse.genesis import (
    EXPECTED_LICENSE,
    EXPECTED_ZENODO_DOI,
    PLAN_SCHEMA,
    RECEIPT_SCHEMA,
    inventory_block_devices,
)
from synapse.genesis_writer import run_install

nbd = os.environ["SYNAPSE_GENESIS_TEST_NBD"]
rootfs = Path(os.environ["SYNAPSE_GENESIS_TEST_ROOTFS"])
manifest_path = Path(os.environ["SYNAPSE_GENESIS_TEST_MANIFEST"])
tmp = Path(os.environ["SYNAPSE_GENESIS_TEST_TMP"])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

inventory = inventory_block_devices()
target = next((item for item in inventory if item.kind == "disk" and item.path == nbd), None)
if target is None:
    raise SystemExit(f"GENESIS CI target disappeared from lsblk: {nbd}")
if not nbd.startswith("/dev/nbd"):
    raise SystemExit(f"GENESIS CI refuses non-NBD target: {nbd}")

plan = {
    "schema": PLAN_SCHEMA,
    "created_at": time.time(),
    "device_fingerprint": "sha256:ci-disposable-nbd-only",
    "target": target.public(),
    "image_path": str(rootfs),
    "manifest_path": str(manifest_path),
    "image_sha256": manifest["image_sha256"],
    "architecture": "amd64",
    "license": EXPECTED_LICENSE,
    "zenodo_doi": EXPECTED_ZENODO_DOI,
}
receipt = {
    "schema": RECEIPT_SCHEMA,
    "created_at": time.time(),
    "final_state": "installing",
    "simulation": False,
    "license": EXPECTED_LICENSE,
    "zenodo_doi": EXPECTED_ZENODO_DOI,
    "target": target.public(),
    "image_sha256": manifest["image_sha256"],
    "phases": [],
}
plan_path = tmp / "ci-install-plan.json"
receipt_path = tmp / "ci-receipt.json"
plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

result = run_install(
    plan_path,
    receipt_path,
    execute=True,
    inventory_probe=lambda: [target],
    source_disk_probe=lambda: None,
    euid=0,
    cmdline="boot=ci synapse.genesis=1",
)
if result.get("final_state") != "complete":
    raise SystemExit(f"GENESIS writer did not complete: {result}")
print("GENESIS disposable-disk writer: PASS")
PY

ESP_PART="${NBD}p1"
ROOT_PART="${NBD}p2"
for _ in $(seq 1 30); do
  [[ -b "$ESP_PART" && -b "$ROOT_PART" ]] && break
  sleep 1
  udevadm settle || true
done
[[ -b "$ESP_PART" ]] || { echo "error: installed EFI partition did not appear: $ESP_PART" >&2; exit 4; }
[[ -b "$ROOT_PART" ]] || { echo "error: installed root partition did not appear: $ROOT_PART" >&2; exit 4; }

mkdir -p "$MOUNT_ROOT" "$MOUNT_ESP"
mount "$ROOT_PART" "$MOUNT_ROOT"
ROOT_MOUNTED=1
mount "$ESP_PART" "$MOUNT_ESP"
ESP_MOUNTED=1
GRUB_CFG="$MOUNT_ESP/boot/grub/grub.cfg"
[[ -s "$GRUB_CFG" ]] || { echo "error: installed ESP GRUB config missing" >&2; exit 4; }

# Add serial output and the existing VM smoke marker only to this disposable CI
# disk. This does not alter the production installer's generated command line.
sed -i '/^[[:space:]]*linux[[:space:]]\/boot\// s@$@ console=ttyS0,115200n8 systemd.unit=multi-user.target systemd.show_status=1 systemd.log_target=console synapse.vmtest=1@' "$GRUB_CFG"
grep -q 'synapse.vmtest=1' "$GRUB_CFG"
test -s "$MOUNT_ROOT/var/lib/synapse/genesis/receipt.json"
grep -q '10.5281/zenodo.17574447' "$MOUNT_ROOT/var/lib/synapse/genesis/receipt.json"
sync
umount "$MOUNT_ESP"
ESP_MOUNTED=0
umount "$MOUNT_ROOT"
ROOT_MOUNTED=0
qemu-nbd --disconnect "$NBD" >/dev/null
NBD_CONNECTED=0
udevadm settle

OVMF_CODE=""
OVMF_VARS=""
for pair in \
  "/usr/share/OVMF/OVMF_CODE_4M.fd:/usr/share/OVMF/OVMF_VARS_4M.fd" \
  "/usr/share/OVMF/OVMF_CODE.fd:/usr/share/OVMF/OVMF_VARS.fd"; do
  code="${pair%%:*}"
  vars="${pair#*:}"
  if [[ -f "$code" && -f "$vars" ]]; then
    OVMF_CODE="$code"
    OVMF_VARS="$vars"
    break
  fi
done
[[ -n "$OVMF_CODE" ]] || { echo "error: OVMF firmware not found" >&2; exit 5; }
cp "$OVMF_VARS" "$TMP/OVMF_VARS.fd"
: > "$SERIAL_LOG"

qemu-system-x86_64 \
  -machine q35,accel=tcg \
  -cpu max \
  -smp 2 \
  -m 4096 \
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
  -drive "if=pflash,format=raw,file=$TMP/OVMF_VARS.fd" \
  -drive "file=$DISK,format=raw,if=virtio" \
  -nic user,model=virtio-net-pci \
  -display none \
  -serial "file:$SERIAL_LOG" \
  -no-reboot &
VM_PID=$!

result=timeout
for _ in $(seq 1 "${SYNAPSE_GENESIS_VM_TIMEOUT:-300}"); do
  if grep -q 'SYNAPSE_VM_READY' "$SERIAL_LOG" 2>/dev/null; then
    result=pass
    break
  fi
  if grep -q 'SYNAPSE_VM_FAIL:' "$SERIAL_LOG" 2>/dev/null; then
    result=guest-fail
    break
  fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then
    result=stopped
    break
  fi
  sleep 1
done

cat "$SERIAL_LOG" || true
copy_log
echo "GENESIS installed amd64 disk result: $result"
[[ "$result" == "pass" ]]