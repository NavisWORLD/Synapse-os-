#!/usr/bin/env bash
set -Eeuo pipefail

NAME="SynapseOS-Nebula-amd64.iso"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PARTS=( "${NAME}.part-"* )
if (( ${#PARTS[@]} == 0 )) || [[ ! -f "${PARTS[0]}" ]]; then
  echo "error: no ${NAME}.part-* files found beside this script" >&2
  exit 2
fi

for required in "${NAME}.sha256" "${NAME}.parts.sha256"; do
  [[ -f "$required" ]] || { echo "error: missing $required" >&2; exit 2; }
done

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "error: need sha256sum or shasum" >&2
    return 127
  fi
}

for part in "${PARTS[@]}"; do
  expected="$(awk -v file="$part" '$2 == file || $2 == "*" file {print $1; exit}' "${NAME}.parts.sha256")"
  [[ -n "$expected" ]] || { echo "error: no checksum entry for $part" >&2; exit 2; }
  actual="$(hash_file "$part")"
  [[ "$actual" == "$expected" ]] || { echo "error: checksum mismatch for $part" >&2; exit 1; }
  echo "$part: OK"
done

rm -f "$NAME"
cat "${PARTS[@]}" > "$NAME"
expected_iso="$(awk 'NR == 1 {print $1}' "${NAME}.sha256")"
[[ -n "$expected_iso" ]] || { echo "error: invalid ${NAME}.sha256" >&2; rm -f "$NAME"; exit 2; }
actual_iso="$(hash_file "$NAME")"
if [[ "$actual_iso" != "$expected_iso" ]]; then
  rm -f "$NAME"
  echo "error: reconstructed ISO checksum mismatch; output removed" >&2
  exit 1
fi

echo "$NAME: OK"
echo "Reassembled and verified: $HERE/$NAME"
