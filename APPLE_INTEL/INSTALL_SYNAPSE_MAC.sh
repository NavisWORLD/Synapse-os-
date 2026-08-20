#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFLIGHT="$HERE/hardware/preflight_mac.sh"

if ! grep -qw 'synapse.genesis=1' /proc/cmdline 2>/dev/null; then
  echo "error: boot the Synapse USB GENESIS/failsafe entry first (requires synapse.genesis=1)." >&2
  exit 2
fi

echo "SYNAPSE APPLE INTEL // INSTALL GATE"
echo "Running read-only Mac preflight before GENESIS can be armed..."
"$PREFLIGHT"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "error: systemd/systemctl is required in the Synapse live environment." >&2
  exit 2
fi

SERVICE='synapse-genesis-installer-api.service'
if ! systemctl cat "$SERVICE" >/dev/null 2>&1; then
  echo "error: $SERVICE is not installed in this live image." >&2
  exit 2
fi

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  systemctl start "$SERVICE"
else
  sudo systemctl start "$SERVICE"
fi

TOKEN_FILE=/run/synapse-genesis/token
for _ in $(seq 1 20); do [[ -s "$TOKEN_FILE" ]] && break; sleep .25; done
if [[ ! -s "$TOKEN_FILE" ]]; then
  echo "error: GENESIS service started but no pairing token appeared." >&2
  systemctl --no-pager --full status "$SERVICE" || true
  exit 3
fi
TOKEN="$(cat "$TOKEN_FILE")"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "$IP" ]] || IP=127.0.0.1

echo
echo "APPLE PREFLIGHT: PASS"
echo "GENESIS API: RUNNING"
echo "Pairing token: $TOKEN"
echo "Open: http://$IP:8787/GENESIS.html"
echo
echo "GENESIS still requires its own verified image/target checks and hold-to-install authorization."
echo "This wrapper does not bypass disk selection, arm challenges, or write verification."
