#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3 is required for the Synapse raw USB flasher." >&2
  echo "Use balenaEtcher instead if Python 3 is unavailable." >&2
  exit 2
fi
if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  exec "$PY" "$HERE/tools/synapse_usb_flasher.py"
else
  exec sudo "$PY" "$HERE/tools/synapse_usb_flasher.py"
fi
