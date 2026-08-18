#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# < 2 || $# > 3 )); then
  echo "usage: $0 <source-iso> <release-dir> [stable-name]" >&2
  exit 2
fi

SOURCE_ISO="$(realpath "$1")"
RELEASE_DIR="$(realpath -m "$2")"
NAME="${3:-SynapseOS-Nebula-amd64.iso}"
PART_SIZE="${SYNAPSE_RELEASE_PART_SIZE:-1900M}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SOURCE_ISO" ]] || { echo "error: source ISO not found: $SOURCE_ISO" >&2; exit 2; }
[[ -n "$RELEASE_DIR" && "$RELEASE_DIR" != "/" ]] || { echo "error: unsafe release directory" >&2; exit 2; }
[[ "$NAME" != */* && "$NAME" == *.iso ]] || { echo "error: stable name must be a plain .iso filename" >&2; exit 2; }

for cmd in sha256sum split stat awk cat; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: missing required command: $cmd" >&2; exit 2; }
done

mkdir -p "$RELEASE_DIR"
rm -f \
  "$RELEASE_DIR/$NAME" \
  "$RELEASE_DIR/$NAME.sha256" \
  "$RELEASE_DIR/$NAME.parts.sha256" \
  "$RELEASE_DIR/$NAME.part-"* \
  "$RELEASE_DIR/reassemble-usb-installer.sh" \
  "$RELEASE_DIR/reassemble-usb-installer.ps1"

ISO_SHA="$(sha256sum "$SOURCE_ISO" | awk '{print $1}')"
printf '%s  %s\n' "$ISO_SHA" "$NAME" > "$RELEASE_DIR/$NAME.sha256"

split -b "$PART_SIZE" -d -a 3 "$SOURCE_ISO" "$RELEASE_DIR/$NAME.part-"
cp "$SCRIPT_DIR/reassemble-usb-installer.sh" "$RELEASE_DIR/reassemble-usb-installer.sh"
cp "$SCRIPT_DIR/reassemble-usb-installer.ps1" "$RELEASE_DIR/reassemble-usb-installer.ps1"
chmod 0755 "$RELEASE_DIR/reassemble-usb-installer.sh"

(
  cd "$RELEASE_DIR"
  sha256sum "$NAME.part-"* > "$NAME.parts.sha256"
  sha256sum -c "$NAME.parts.sha256"
)

for part in "$RELEASE_DIR/$NAME.part-"*; do
  bytes="$(stat -c '%s' "$part")"
  if (( bytes >= 2147483648 )); then
    echo "error: release part exceeds GitHub's 2 GiB asset limit: $part ($bytes bytes)" >&2
    exit 1
  fi
done

bash -n "$RELEASE_DIR/reassemble-usb-installer.sh"
if command -v pwsh >/dev/null 2>&1; then
  SYNAPSE_PS_SCRIPT="$RELEASE_DIR/reassemble-usb-installer.ps1" \
    pwsh -NoProfile -Command \
      '$null = [scriptblock]::Create((Get-Content -Raw -LiteralPath $env:SYNAPSE_PS_SCRIPT))'
fi

STREAM_SHA="$(cat "$RELEASE_DIR/$NAME.part-"* | sha256sum | awk '{print $1}')"
if [[ "$STREAM_SHA" != "$ISO_SHA" ]]; then
  echo "error: split parts do not reconstruct the verified ISO" >&2
  exit 1
fi

printf 'packaged=%s\nsha256=%s\npart_size=%s\n' "$NAME" "$ISO_SHA" "$PART_SIZE"
