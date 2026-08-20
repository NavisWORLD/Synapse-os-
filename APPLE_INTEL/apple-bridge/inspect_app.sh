#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $# -eq 1 ]] || { echo "usage: $0 /path/App.app" >&2; exit 2; }
exec python3 "$HERE/compatibility_report.py" "$1"
