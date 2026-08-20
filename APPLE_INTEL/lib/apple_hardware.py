from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ARCH = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}


def normalize_arch(value: str) -> str:
    key = str(value or "").strip().lower()
    return _ARCH.get(key, key or "unknown")


def load_profiles(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("profiles"), list):
        raise ValueError("invalid Apple Intel profile registry")
    return data


def _is_apple_vendor(value: str) -> bool:
    normalized = " ".join(str(value or "").upper().replace(",", " ").split())
    return normalized in {"APPLE INC.", "APPLE INC", "APPLE COMPUTER INC.", "APPLE COMPUTER INC"}


def match_profile(probe: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_apple_vendor(str(probe.get("sys_vendor") or probe.get("vendor") or "")):
        return None
    arch = normalize_arch(str(probe.get("arch") or probe.get("architecture") or ""))
    product = str(probe.get("product_name") or "").strip()
    for profile in registry.get("profiles", []):
        if normalize_arch(profile.get("arch", "")) != arch:
            continue
        if product in profile.get("model_identifiers", []):
            return profile
    return None


def normalize_probe(probe: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    vendor = str(probe.get("sys_vendor") or probe.get("vendor") or "") or None
    product = str(probe.get("product_name") or "") or None
    board = str(probe.get("board_name") or "") or None
    bios = str(probe.get("bios_vendor") or "") or None
    arch = normalize_arch(str(probe.get("arch") or probe.get("architecture") or ""))
    efi_present = bool(probe.get("efi_present"))
    profile = match_profile(probe, registry)

    if profile:
        support_state = str(profile.get("support_state") or "experimental")
        profile_id = profile.get("id")
        touch_bar = bool(profile.get("touch_bar", False))
    elif _is_apple_vendor(vendor or "") and arch == "amd64":
        support_state = "experimental"
        profile_id = None
        touch_bar = None
    elif _is_apple_vendor(vendor or ""):
        support_state = "unsupported"
        profile_id = None
        touch_bar = None
    else:
        support_state = "unknown"
        profile_id = None
        touch_bar = None

    return {
        "vendor": vendor,
        "product_name": product,
        "board_name": board,
        "bios_vendor": bios,
        "architecture": arch,
        "efi_present": efi_present,
        "profile_id": profile_id,
        "support_state": support_state,
        "touch_bar": touch_bar,
    }
