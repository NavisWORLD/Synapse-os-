#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/.work/live-build"
if [[ -d "$WORK" ]] && command -v lb >/dev/null 2>&1; then
  cd "$WORK"
  lb clean --purge || true
fi
python3 - "$ROOT" <<'PYSAFE'
from pathlib import Path
import shutil, sys
root = Path(sys.argv[1]).resolve()
target = (root / ".work").resolve()
if target.parent != root or target.name != ".work":
    raise SystemExit(f"refusing unsafe cleanup path: {target}")
shutil.rmtree(target, ignore_errors=True)
PYSAFE
echo "Synapse OS build workspace cleaned."
