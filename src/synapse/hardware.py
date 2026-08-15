from __future__ import annotations

import json
import platform
from pathlib import Path
import shutil
import subprocess
from typing import Any

DEFAULT_PROFILE_PATHS = (
    Path("/usr/share/synapse/hardware/profiles.json"),
    Path(__file__).resolve().parents[2] / "hardware" / "profiles.json",
)

_ARCH_ALIASES = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "riscv64": "riscv64",
}


def normalize_arch(value: str) -> str:
    key = value.strip().lower()
    return _ARCH_ALIASES.get(key, key or "unknown")


def _read_text(path: str | Path) -> str | None:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
        return text or None
    except OSError:
        return None


def _crossystem_hwid() -> str | None:
    binary = shutil.which("crossystem")
    if not binary:
        return None
    try:
        proc = subprocess.run([binary, "hwid"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def load_profiles(path: Path | None = None) -> dict[str, Any]:
    candidates = (path,) if path else DEFAULT_PROFILE_PATHS
    for candidate in candidates:
        if candidate and candidate.is_file():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if data.get("schema_version") != 1 or not isinstance(data.get("profiles"), list):
                raise ValueError("invalid hardware profile registry")
            return data
    return {"schema_version": 1, "profiles": []}


def match_profile(probe: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    arch = normalize_arch(str(probe.get("arch") or ""))
    hwid = str(probe.get("hwid") or "").upper()
    product = str(probe.get("product_name") or "").upper()
    for profile in registry.get("profiles", []):
        if normalize_arch(str(profile.get("arch") or "")) != arch:
            continue
        hwid_tokens = [str(x).upper() for x in profile.get("hwid_contains", [])]
        product_tokens = [str(x).upper() for x in profile.get("product_contains", [])]
        if hwid_tokens and not all(token in hwid for token in hwid_tokens):
            continue
        if product_tokens and product and not any(token in product for token in product_tokens):
            continue
        return {
            "profile_id": profile.get("id"),
            "certification_state": profile.get("certification_state", "unverified"),
            "profile": profile,
        }
    return {"profile_id": None, "certification_state": "unverified", "profile": None}


def probe_hardware(profile_path: Path | None = None) -> dict[str, Any]:
    hwid = _read_text("/sys/firmware/vpd/ro/hwid") or _crossystem_hwid()
    probe = {
        "arch": normalize_arch(platform.machine()),
        "hwid": hwid,
        "sys_vendor": _read_text("/sys/class/dmi/id/sys_vendor"),
        "product_name": _read_text("/sys/class/dmi/id/product_name"),
        "product_version": _read_text("/sys/class/dmi/id/product_version"),
        "board_name": _read_text("/sys/class/dmi/id/board_name"),
    }
    probe.update(match_profile(probe, load_profiles(profile_path)))
    return probe
