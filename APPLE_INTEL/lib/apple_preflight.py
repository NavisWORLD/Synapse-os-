from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _internal_candidates(disks: list[dict[str, Any]], source_disk: str | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for disk in disks:
        if str(disk.get("type") or disk.get("kind") or "") != "disk":
            continue
        path = str(disk.get("path") or "")
        if not path or path == source_disk:
            continue
        rm = _bool(disk.get("rm") if "rm" in disk else disk.get("removable"))
        tran = str(disk.get("tran") or disk.get("transport") or "").lower()
        if rm or tran == "usb":
            continue
        if path.startswith(("/dev/loop", "/dev/zram", "/dev/sr", "/dev/dm-")):
            continue
        result.append(disk)
    return result


def evaluate_preflight(
    identity: dict[str, Any],
    disks: list[dict[str, Any]],
    source_disk: str | None,
    capabilities: dict[str, Any],
    power: dict[str, Any],
) -> dict[str, Any]:
    fatal: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, code: str, *, fatal_on_fail: bool) -> None:
        checks.append({"name": name, "ok": bool(ok), "code": code})
        if ok:
            return
        (fatal if fatal_on_fail else warnings).append(code)

    arch_ok = str(identity.get("architecture") or "").lower() == "amd64"
    check("amd64 architecture", arch_ok, "ARCH_UNSUPPORTED", fatal_on_fail=True)
    check("EFI boot", _bool(identity.get("efi_present")), "EFI_REQUIRED", fatal_on_fail=True)

    support = str(identity.get("support_state") or "unknown")
    if support == "physical-target":
        checks.append({"name": "Apple hardware profile", "ok": True, "code": "HARDWARE_MATCHED"})
    elif support == "experimental" and str(identity.get("vendor") or "").lower().startswith("apple"):
        checks.append({"name": "Apple hardware profile", "ok": True, "code": "HARDWARE_EXPERIMENTAL"})
        warnings.append("HARDWARE_EXPERIMENTAL")
    else:
        checks.append({"name": "Apple hardware profile", "ok": False, "code": "HARDWARE_UNSUPPORTED"})
        fatal.append("HARDWARE_UNSUPPORTED")

    candidates = _internal_candidates(disks, source_disk)
    target = candidates[0] if len(candidates) == 1 else None
    if not candidates:
        fatal.append("TARGET_MISSING")
        checks.append({"name": "single internal target", "ok": False, "code": "TARGET_MISSING"})
    elif len(candidates) > 1:
        fatal.append("TARGET_AMBIGUOUS")
        checks.append({"name": "single internal target", "ok": False, "code": "TARGET_AMBIGUOUS"})
    else:
        checks.append({"name": "single internal target", "ok": True, "code": "TARGET_OK"})

    ac = power.get("ac_online")
    battery = power.get("battery_percent")
    if ac is False and battery is not None and float(battery) < 30:
        fatal.append("POWER_UNSAFE")
        checks.append({"name": "installation power", "ok": False, "code": "POWER_UNSAFE"})
    elif ac is None and battery is None:
        warnings.append("POWER_UNVERIFIED")
        checks.append({"name": "installation power", "ok": True, "code": "POWER_UNVERIFIED"})
    else:
        checks.append({"name": "installation power", "ok": True, "code": "POWER_OK"})

    required_caps = (("gpu", "GPU_NOT_DETECTED"),)
    optional_caps = (
        ("keyboard", "KEYBOARD_NOT_DETECTED"),
        ("pointer", "POINTER_NOT_DETECTED"),
        ("network", "NETWORK_NOT_DETECTED"),
        ("audio", "AUDIO_NOT_DETECTED"),
        ("applesmc", "APPLESMC_UNVERIFIED"),
        ("suspend", "SUSPEND_UNVERIFIED"),
    )
    for key, code in required_caps:
        check(key, _bool(capabilities.get(key)), code, fatal_on_fail=True)
    for key, code in optional_caps:
        check(key, _bool(capabilities.get(key)), code, fatal_on_fail=False)

    return {
        "ok": not fatal,
        "fatal": fatal,
        "warnings": warnings,
        "target": target,
        "source_disk": source_disk,
        "checks": checks,
        "identity": identity,
    }


def _flatten_lsblk(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in payload.get("blockdevices", []) if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True)
    parser.add_argument("--lsblk", required=True)
    parser.add_argument("--source-disk", default="")
    parser.add_argument("--capabilities", required=True)
    parser.add_argument("--power", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    identity = json.loads(Path(args.identity).read_text(encoding="utf-8"))
    disks = _flatten_lsblk(json.loads(Path(args.lsblk).read_text(encoding="utf-8")))
    capabilities = json.loads(Path(args.capabilities).read_text(encoding="utf-8"))
    power = json.loads(Path(args.power).read_text(encoding="utf-8"))
    result = evaluate_preflight(identity, disks, args.source_disk or None, capabilities, power)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
