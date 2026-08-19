#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
ISO='SynapseOS-Nebula-amd64.iso'
SIDE="$ISO.sha256"
[[ -f "$ISO" && -f "$SIDE" ]] || { echo "Missing $ISO or $SIDE" >&2; exit 2; }
expected="$(awk 'NR==1{print $1}' "$SIDE")"
if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$ISO" | awk '{print $1}')"; else actual="$(shasum -a 256 "$ISO" | awk '{print $1}')"; fi
[[ "$actual" == "$expected" ]] || { echo "SHA-256 mismatch" >&2; exit 1; }
echo "$ISO: VERIFIED"
echo "$actual"
