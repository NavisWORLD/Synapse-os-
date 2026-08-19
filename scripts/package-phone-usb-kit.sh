#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# != 1 )); then
  echo "usage: $0 <release-dir>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RELEASE_DIR="$(realpath -m "$1")"
KIT_SRC="$ROOT/PHONE_USB_KIT"
OUT="$RELEASE_DIR/SynapseOS-Phone-USB-Kit.zip"
OUT_SHA="$OUT.sha256"

[[ -d "$RELEASE_DIR" ]] || { echo "error: release dir not found: $RELEASE_DIR" >&2; exit 2; }
[[ -d "$KIT_SRC" ]] || { echo "error: phone kit source missing: $KIT_SRC" >&2; exit 2; }
[[ -f "$ROOT/USB_INSTALL.md" ]] || { echo "error: USB_INSTALL.md missing" >&2; exit 2; }

required=(
  "SynapseOS-Nebula-amd64.iso.parts.sha256"
  "SynapseOS-Nebula-amd64.iso.sha256"
  "reassemble-usb-installer.ps1"
  "reassemble-usb-installer.sh"
)

for name in "${required[@]}"; do
  [[ -f "$RELEASE_DIR/$name" ]] || { echo "error: missing release file: $name" >&2; exit 2; }
done

STAGE="$(mktemp -d)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

cp -a "$KIT_SRC/." "$STAGE/"
cp "$ROOT/USB_INSTALL.md" "$STAGE/USB_INSTALL.md"
for name in "${required[@]}"; do
  cp "$RELEASE_DIR/$name" "$STAGE/$name"
done

rm -f "$OUT" "$OUT_SHA"
STAGE="$STAGE" OUT="$OUT" python3 - <<'PY'
import os
import zipfile
from pathlib import Path

stage = Path(os.environ["STAGE"])
out = Path(os.environ["OUT"])
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(p for p in stage.rglob("*") if p.is_file()):
        archive.write(path, path.relative_to(stage).as_posix())
PY

sha256sum "$OUT" > "$OUT_SHA"
[[ -s "$OUT" ]] || { echo "error: phone kit bundle is empty" >&2; exit 1; }
[[ -s "$OUT_SHA" ]] || { echo "error: phone kit checksum missing" >&2; exit 1; }

printf 'phone_kit=%s\nchecksum=%s\n' "$OUT" "$OUT_SHA"
