#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "SYNAPSE APPLE INTEL // EFI RECOVERY"
echo "This repairs only the explicitly supplied Synapse ESP/root pair."
exec "$HERE/apple_efi_install.sh" "$@"
