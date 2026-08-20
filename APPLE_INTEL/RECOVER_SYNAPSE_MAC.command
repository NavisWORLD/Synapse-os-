#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/RECOVER_SYNAPSE_MAC.sh" "$@"
