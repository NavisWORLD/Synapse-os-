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
  BEASTOS_WEB_MACHINE/manifests/beast-v0.7.0.json BEASTOS_WEB_MACHINE/scripts/fetch-beast-kit.py
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
python3 - "$ROOT/BEASTOS_WEB_MACHINE/manifests/beast-v0.7.0.json" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1], encoding='utf-8'))
assert manifest['tag'] == 'v0.7.0'
assert manifest['commit'] == '97f153225ea2f8910f1c91194a65b97f94246c2b'
assert manifest['sha256'] == '9e436d7af016c4d25b0b1ba6902357e01986a48a34f3315b0003c116d6c68bbb'
assert manifest['prerelease'] is True
PY
echo "tree validation: ok"
