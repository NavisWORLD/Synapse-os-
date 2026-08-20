#!/usr/bin/env bash
set -Eeuo pipefail
ALLOW_EXPERIMENTAL=0
if [[ "${1:-}" == "--allow-experimental" ]]; then ALLOW_EXPERIMENTAL=1; shift; fi
[[ $# -eq 1 ]] || { echo "usage: $0 [--allow-experimental] /path/App.app" >&2; exit 2; }
APP="$1"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT="$(mktemp /tmp/synapse-apple-bridge.XXXXXX.json)"
trap 'rm -f "$REPORT"' EXIT
set +e
python3 "$HERE/compatibility_report.py" "$APP" --output "$REPORT" >/dev/null
REPORT_RC=$?
set -e
CLASS="$(python3 - "$REPORT" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['classification'])
PY
)"
EXE="$(python3 - "$REPORT" <<'PY'
import json,sys
print(json.load(open(sys.argv[1])).get('executable_path') or '')
PY
)"
cat "$REPORT"
[[ -n "$EXE" ]] || { echo "error: no executable resolved" >&2; exit 3; }
case "$CLASS" in
  native-tool) ;;
  experimental)
    [[ "$ALLOW_EXPERIMENTAL" == 1 ]] || { echo "refusing experimental launch without --allow-experimental" >&2; exit 4; }
    ;;
  *) echo "refusing unsupported bundle" >&2; exit 4;;
esac
chmod +x "$EXE" 2>/dev/null || true
set +e
"$EXE"
RC=$?
set -e
echo "Synapse Apple Bridge process exit status: $RC"
exit "$RC"
