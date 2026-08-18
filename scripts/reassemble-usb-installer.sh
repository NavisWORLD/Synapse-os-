#!/usr/bin/env bash
set -Eeuo pipefail

NAME="SynapseOS-Nebula-amd64.iso"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

mapfile -t PARTS < <(printf '%s\n' "${NAME}.part-"* | sort)
if (( ${#PARTS[@]} == 0 )) || [[ ! -f "${PARTS[0]}" ]]; then
  echo "error: no ${NAME}.part-* files found beside this script" >&2
  exit 2
fi

for required in "${NAME}.sha256" "${NAME}.parts.sha256"; do
  [[ -f "$required" ]] || { echo "error: missing $required" >&2; exit 2; }
done

sha256sum -c "${NAME}.parts.sha256"
rm -f "$NAME"
cat "${PARTS[@]}" > "$NAME"
sha256sum -c "${NAME}.sha256"

echo "Reassembled and verified: $HERE/$NAME"
