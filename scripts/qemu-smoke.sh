#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <amd64|arm64|riscv64> <iso>" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH="$1"
ISO="$2"
eval "$(python3 "$REPO_ROOT/scripts/arch_matrix.py" shell "$ARCH")"

if [[ "${SYNAPSE_QEMU_DRY_RUN:-0}" == "1" ]]; then
  printf 'arch=%s\nqemu=%s\nmachine=%s\ncpu=%s\nconsole=%s\n' \
    "$SYNAPSE_ARCH_NORMALIZED" "$SYNAPSE_QEMU_SYSTEM" "$SYNAPSE_QEMU_MACHINE" "$SYNAPSE_QEMU_CPU" "$SYNAPSE_SERIAL_CONSOLE"
  exit 0
fi

for cmd in "$SYNAPSE_QEMU_SYSTEM" xorriso grep; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: missing $cmd" >&2; exit 2; }
done
[[ -f "$ISO" ]] || { echo "error: ISO not found: $ISO" >&2; exit 2; }

TMP="$(mktemp -d -t synapse-qemu-${SYNAPSE_ARCH_NORMALIZED}.XXXXXX)"
cleanup() {
  if [[ -n "${VM_PID:-}" ]]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

xorriso -osirrox on -indev "$ISO" -extract /live/vmlinuz "$TMP/vmlinuz" >/dev/null 2>&1
xorriso -osirrox on -indev "$ISO" -extract /live/initrd.img "$TMP/initrd.img" >/dev/null 2>&1
: > "$TMP/serial.log"

common=(
  -machine "$SYNAPSE_QEMU_MACHINE"
  -cpu "$SYNAPSE_QEMU_CPU"
  -smp 2
  -m 4096
  -kernel "$TMP/vmlinuz"
  -initrd "$TMP/initrd.img"
  -append "boot=live components live-media=/dev/vda console=$SYNAPSE_SERIAL_CONSOLE systemd.unit=multi-user.target systemd.show_status=1 systemd.log_target=console synapse.vmtest=1"
  -display none
  -serial "file:$TMP/serial.log"
  -no-reboot
)

if [[ "$SYNAPSE_ARCH_NORMALIZED" == "amd64" ]]; then
  media=(-drive "file=$ISO,format=raw,if=virtio,readonly=on")
  network=(-nic user,model=virtio-net-pci)
else
  media=(-drive "if=none,id=live,file=$ISO,format=raw,readonly=on" -device "virtio-blk-device,drive=live")
  network=(-netdev "user,id=net0" -device "virtio-net-device,netdev=net0")
fi

"$SYNAPSE_QEMU_SYSTEM" "${common[@]}" "${media[@]}" "${network[@]}" &
VM_PID=$!
result=timeout
for _ in $(seq 1 "${SYNAPSE_QEMU_TIMEOUT:-240}"); do
  if grep -q 'SYNAPSE_VM_READY' "$TMP/serial.log" 2>/dev/null; then
    result=pass
    break
  fi
  if grep -q 'SYNAPSE_VM_FAIL:' "$TMP/serial.log" 2>/dev/null; then
    result=guest-fail
    break
  fi
  if ! kill -0 "$VM_PID" 2>/dev/null; then
    result=stopped
    break
  fi
  sleep 1
done

cat "$TMP/serial.log" || true
if [[ -n "${SYNAPSE_QEMU_LOG:-}" ]]; then
  mkdir -p "$(dirname "$SYNAPSE_QEMU_LOG")"
  cp "$TMP/serial.log" "$SYNAPSE_QEMU_LOG"
fi
echo "QEMU $SYNAPSE_ARCH_NORMALIZED result: $result"
[[ "$result" == "pass" ]]
