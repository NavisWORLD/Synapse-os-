#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo '=== SYNAPSE APPLE INTEL DIAGNOSTICS ==='
"$HERE/detect_apple_model.sh" || true
echo
echo '[PCI / graphics / network / audio]'
if command -v lspci >/dev/null 2>&1; then lspci -nn | grep -Ei 'VGA|Display|3D|Network|Wireless|Audio|Broadcom|Intel' || true; else echo 'lspci unavailable'; fi
echo
echo '[Input]'
grep -Ei 'Name=|Handlers=' /proc/bus/input/devices 2>/dev/null || true
echo
echo '[Network]'
ip -brief link 2>/dev/null || true
echo
echo '[Audio]'
cat /proc/asound/cards 2>/dev/null || true
echo
echo '[Apple SMC / hwmon]'
find /sys/class/hwmon -maxdepth 2 -name name -print -exec cat {} \; 2>/dev/null || true
echo
echo '[Power]'
for p in /sys/class/power_supply/*; do [[ -e "$p" ]] || continue; echo "-- $p"; grep -H . "$p"/{type,online,capacity,status} 2>/dev/null || true; done
echo
echo '[Suspend states]'
cat /sys/power/state 2>/dev/null || true
echo
echo 'No write or firmware operation was performed.'
