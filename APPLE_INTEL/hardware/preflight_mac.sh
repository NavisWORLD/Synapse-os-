#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RUNDIR="${SYNAPSE_APPLE_RUN_DIR:-/run/synapse}"
mkdir -p "$RUNDIR"
IDENTITY="$RUNDIR/apple-identity.json"
LSBLK="$RUNDIR/apple-lsblk.json"
CAPS="$RUNDIR/apple-capabilities.json"
POWER="$RUNDIR/apple-power.json"
OUT="$RUNDIR/apple-preflight.json"
"$HERE/detect_apple_model.sh" > "$IDENTITY"
lsblk -J -b -o NAME,PATH,TYPE,SIZE,RM,TRAN,MOUNTPOINTS,MODEL,SERIAL > "$LSBLK"
SOURCE_PART="$(findmnt -n -o SOURCE /run/live/medium 2>/dev/null || true)"
SOURCE_DISK=""
if [[ -n "$SOURCE_PART" && "$SOURCE_PART" == /dev/* ]]; then
  PK="$(lsblk -n -o PKNAME "$SOURCE_PART" 2>/dev/null | head -n1 || true)"
  if [[ -n "$PK" ]]; then SOURCE_DISK="/dev/$PK"; else SOURCE_DISK="$SOURCE_PART"; fi
fi
GPU=false; KEYBOARD=false; POINTER=false; NETWORK=false; AUDIO=false; APPLESMC=false; SUSPEND=false
if command -v lspci >/dev/null 2>&1 && lspci | grep -Eqi 'VGA|Display|3D controller'; then GPU=true; fi
if grep -Eqi 'keyboard' /proc/bus/input/devices 2>/dev/null; then KEYBOARD=true; fi
if grep -Eqi 'touchpad|trackpad|mouse' /proc/bus/input/devices 2>/dev/null; then POINTER=true; fi
if [[ -d /sys/class/net ]] && find /sys/class/net -mindepth 1 -maxdepth 1 ! -name lo -print -quit | grep -q .; then NETWORK=true; fi
if [[ -r /proc/asound/cards ]] && grep -Eq '^[[:space:]]*[0-9]+ ' /proc/asound/cards; then AUDIO=true; elif command -v aplay >/dev/null 2>&1 && aplay -l >/dev/null 2>&1; then AUDIO=true; fi
if [[ -d /sys/devices/platform/applesmc.768 || -d /sys/bus/platform/drivers/applesmc ]]; then APPLESMC=true; fi
if [[ -r /sys/power/state ]] && grep -qw mem /sys/power/state; then SUSPEND=true; fi
python3 - "$CAPS" "$GPU" "$KEYBOARD" "$POINTER" "$NETWORK" "$AUDIO" "$APPLESMC" "$SUSPEND" <<'PY'
import json, sys
path=sys.argv[1]
vals=[v=="true" for v in sys.argv[2:]]
keys=["gpu","keyboard","pointer","network","audio","applesmc","suspend"]
open(path,"w",encoding="utf-8").write(json.dumps(dict(zip(keys,vals))))
PY
AC=null; BAT=null
for supply in /sys/class/power_supply/*; do
  [[ -e "$supply" ]] || continue
  type="$(cat "$supply/type" 2>/dev/null || true)"
  if [[ "$type" == "Mains" || "$type" == "USB" || "$type" == "USB_C" ]]; then
    online="$(cat "$supply/online" 2>/dev/null || true)"
    [[ "$online" == "1" ]] && AC=true
    [[ "$online" == "0" && "$AC" == null ]] && AC=false
  elif [[ "$type" == "Battery" ]]; then
    BAT="$(cat "$supply/capacity" 2>/dev/null || true)"
  fi
done
python3 - "$POWER" "$AC" "$BAT" <<'PY'
import json, sys
ac = None if sys.argv[2]=="null" else sys.argv[2]=="true"
try: bat=int(sys.argv[3]) if sys.argv[3] else None
except ValueError: bat=None
open(sys.argv[1],"w",encoding="utf-8").write(json.dumps({"ac_online":ac,"battery_percent":bat}))
PY
set +e
python3 "$ROOT/lib/apple_preflight.py" --identity "$IDENTITY" --lsblk "$LSBLK" --source-disk "$SOURCE_DISK" --capabilities "$CAPS" --power "$POWER" --output "$OUT"
RC=$?
set -e
echo
echo "Synapse Apple preflight JSON: $OUT"
exit "$RC"
