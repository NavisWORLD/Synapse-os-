#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="${PYTHON:-python3}"
read_one(){ [[ -r "$1" ]] && tr -d '\000\r\n' < "$1" || true; }
VENDOR="$(read_one /sys/class/dmi/id/sys_vendor)"
PRODUCT="$(read_one /sys/class/dmi/id/product_name)"
BOARD="$(read_one /sys/class/dmi/id/board_name)"
BIOS="$(read_one /sys/class/dmi/id/bios_vendor)"
ARCH="$(uname -m)"
EFI=false
[[ -d /sys/firmware/efi ]] && EFI=true
export SYNAPSE_APPLE_VENDOR="$VENDOR" SYNAPSE_APPLE_PRODUCT="$PRODUCT" SYNAPSE_APPLE_BOARD="$BOARD" SYNAPSE_APPLE_BIOS="$BIOS" SYNAPSE_APPLE_ARCH="$ARCH" SYNAPSE_APPLE_EFI="$EFI"
"$PYTHON" - "$ROOT" <<'PY'
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from lib.apple_hardware import load_profiles, normalize_probe
probe = {
    "sys_vendor": os.environ.get("SYNAPSE_APPLE_VENDOR", ""),
    "product_name": os.environ.get("SYNAPSE_APPLE_PRODUCT", ""),
    "board_name": os.environ.get("SYNAPSE_APPLE_BOARD", ""),
    "bios_vendor": os.environ.get("SYNAPSE_APPLE_BIOS", ""),
    "arch": os.environ.get("SYNAPSE_APPLE_ARCH", ""),
    "efi_present": os.environ.get("SYNAPSE_APPLE_EFI") == "true",
}
registry = load_profiles(root / "hardware" / "apple_intel_profiles.json")
print(json.dumps(normalize_probe(probe, registry), sort_keys=True))
PY
