#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/INSTALL_SYNAPSE_MAC.sh" "$@"
