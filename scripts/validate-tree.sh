#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
required=(
  README.md VERSION LICENSE
  build/build.sh build/architectures.json build/config/package-lists/synapse.list.chroot
  build/hooks/030-native-sdk.hook.chroot
  rootfs/etc/os-release rootfs/etc/systemd/system/synapse-agent.service
  src/synapse/cli.py src/synapse/core.py src/synapse/dsl.py src/synapse/hardware.py
  language/README.md
  sdk/c/include/synapse/synapse.h sdk/c/src/synapse.c sdk/c/CMakeLists.txt
  sdk/cpp/include/synapse.hpp sdk/rust/Cargo.toml sdk/python/synapse_sdk.py
  scripts/arch_matrix.py scripts/qemu-smoke.sh hardware/profiles.json
)
for path in "${required[@]}"; do
  [[ -e "$ROOT/$path" ]] || { echo "missing: $path" >&2; exit 1; }
done
python3 "$ROOT/scripts/arch_matrix.py" validate >/dev/null
echo "tree validation: ok"
