#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
required=(
  README.md VERSION LICENSE
  build/build.sh build/architectures.json build/config/package-lists/synapse.list.chroot
  build/hooks/015-beastos-web.hook.chroot build/hooks/030-native-sdk.hook.chroot
  rootfs/etc/os-release rootfs/etc/systemd/system/synapse-agent.service
  rootfs/usr/local/bin/synapse-beastos-web rootfs/usr/share/applications/beastos-web.desktop
  src/synapse/cli.py src/synapse/core.py src/synapse/dsl.py src/synapse/hardware.py
  BEASTOS_WEB_MACHINE/README.md
  BEASTOS_WEB_MACHINE/bridge/server.py BEASTOS_WEB_MACHINE/bridge/adapter.py BEASTOS_WEB_MACHINE/bridge/kit.py
  BEASTOS_WEB_MACHINE/manifests/beast-v0.6.0.json BEASTOS_WEB_MACHINE/scripts/fetch-beast-kit.py
  BEASTOS_WEB_MACHINE/public/index.html BEASTOS_WEB_MACHINE/public/app.webmanifest BEASTOS_WEB_MACHINE/public/sw.js
  BEASTOS_WEB_MACHINE/src/app/app.js BEASTOS_WEB_MACHINE/src/beast/conversation.js
  language/README.md
  sdk/c/include/synapse/synapse.h sdk/c/src/synapse.c sdk/c/CMakeLists.txt
  sdk/cpp/include/synapse.hpp sdk/rust/Cargo.toml sdk/python/synapse_sdk.py
  scripts/arch_matrix.py scripts/qemu-smoke.sh hardware/profiles.json
)
for path in "${required[@]}"; do
  [[ -e "$ROOT/$path" ]] || { echo "missing: $path" >&2; exit 1; }
done
python3 "$ROOT/scripts/arch_matrix.py" validate >/dev/null
python3 - "$ROOT/BEASTOS_WEB_MACHINE/manifests/beast-v0.6.0.json" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1], encoding='utf-8'))
assert manifest['tag'] == 'v0.6.0'
assert manifest['commit'] == '331f03c5d6a4aab0b2e32314293e36c7a94be393'
assert manifest['sha256'] == 'c2a5bf5e3cb972ec3e5f1aa45f06d7e77e9b6de115e049f06e830a1f4c312ad2'
assert manifest['prerelease'] is True
PY
echo "tree validation: ok"
