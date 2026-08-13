#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
required=(
  README.md VERSION LICENSE
  build/build.sh build/config/package-lists/synapse.list.chroot
  rootfs/etc/os-release rootfs/etc/systemd/system/synapse-agent.service
  src/synapse/cli.py src/synapse/core.py src/synapse/dsl.py
  language/README.md sdk/cpp/include/synapse.hpp sdk/rust/Cargo.toml
)
for path in "${required[@]}"; do
  [[ -e "$ROOT/$path" ]] || { echo "missing: $path" >&2; exit 1; }
done
echo "tree validation: ok"
