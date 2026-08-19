#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3 is required for the automatic release downloader." >&2
  echo "You can still download the release assets manually; see START_HERE.md." >&2
  exit 2
fi
"$PY" "$HERE/tools/download_release.py"
echo
echo "Release files downloaded. Next run ./reassemble-usb-installer.sh"
