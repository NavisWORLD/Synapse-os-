#!/usr/bin/env python3
"""Synapse OS removable-USB raw image writer.

Safety model:
- source ISO must match its SHA-256 sidecar;
- only whole-disk USB/removable candidates are eligible;
- system/boot/internal disks are rejected;
- confirmation text is bound to the selected device identity;
- the written prefix is read back and SHA-256 verified before success.

This tool never accepts an arbitrary target path from the command line. It discovers
candidate USB disks itself and lets the operator select one of those candidates.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time
from typing import Callable, Iterable

CHUNK = 4 * 1024 * 1024
ISO_NAME = "SynapseOS-Nebula-amd64.iso"


def run(cmd: list[str], *, text: bool = True, check: bool = True, capture: bool = True):
    return subprocess.run(
        cmd,
        check=check,
        text=text,
        capture_output=capture,
    )


def human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


def parse_sha256_sidecar(path: Path, expected_name: str) -> str:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        fields = line.split(maxsplit=1)
        digest = fields[0].lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"Invalid SHA-256 in {path}")
        if len(fields) == 2:
            name = fields[1].strip().lstrip("*")
            if Path(name).name != Path(expected_name).name:
                continue
        return digest
    raise ValueError(f"No checksum for {expected_name} found in {path}")


def sha256_path(path: Path, limit: int | None = None) -> str:
    h = hashlib.sha256()
    remaining = limit
    with open(path, "rb", buffering=0) as f:
        while True:
            if remaining is not None and remaining <= 0:
                break
            want = CHUNK if remaining is None else min(CHUNK, remaining)
            block = f.read(want)
            if not block:
                break
            h.update(block)
            if remaining is not None:
                remaining -= len(block)
    if limit is not None and remaining != 0:
        raise IOError(f"Short read while hashing {path}: {remaining} bytes missing")
    return h.hexdigest()


def sha256_prefix(path: Path | str, length: int) -> str:
    return sha256_path(Path(path), limit=length)


def safe_candidate(candidate: dict, image_size: int) -> tuple[bool, str]:
    if str(candidate.get("type", "")).lower() != "disk":
        return False, "not a whole disk"
    if str(candidate.get("bus", "")).lower() != "usb":
        return False, "not USB transport"
    if not bool(candidate.get("removable")):
        return False, "not marked removable/external"
    if bool(candidate.get("system")):
        return False, "system disk"
    if bool(candidate.get("boot")):
        return False, "boot disk"
    try:
        size = int(candidate.get("size", 0))
    except (TypeError, ValueError):
        return False, "unknown capacity"
    if size < image_size:
        return False, "too small for installer image"
    if not candidate.get("path") or not candidate.get("id"):
        return False, "missing device identity"
    return True, "eligible USB disk"


def confirmation_phrase(candidate: dict) -> str:
    return f"ERASE USB {candidate['id']}"


def _progress_printer(done: int, total: int) -> None:
    pct = 100.0 if total == 0 else (done * 100.0 / total)
    print(f"\rWriting: {pct:6.2f}%  {human_size(done)} / {human_size(total)}", end="", flush=True)
    if done >= total:
        print()


def write_image(
    source: Path,
    target: Path | str,
    total_bytes: int,
    progress: Callable[[int, int], None] | None = _progress_printer,
) -> None:
    done = 0
    with open(source, "rb", buffering=0) as src, open(target, "r+b", buffering=0) as dst:
        while done < total_bytes:
            block = src.read(min(CHUNK, total_bytes - done))
            if not block:
                raise IOError("Source image ended early")
            view = memoryview(block)
            written = 0
            while written < len(block):
                n = dst.write(view[written:])
                if n is None:
                    n = 0
                if n <= 0:
                    raise IOError("Target write returned zero bytes")
                written += n
            done += len(block)
            if progress:
                progress(done, total_bytes)
        dst.flush()
        try:
            os.fsync(dst.fileno())
        except OSError:
            pass


def _windows_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _windows_discover() -> list[dict]:
    script = r"""
$ErrorActionPreference='Stop'
Get-Disk | Select-Object Number,FriendlyName,SerialNumber,BusType,Size,IsBoot,IsSystem,IsReadOnly,OperationalStatus | ConvertTo-Json -Depth 3 -Compress
"""
    cp = run(["powershell.exe", "-NoProfile", "-Command", script])
    raw = cp.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    result = []
    for d in data:
        bus = str(d.get("BusType", "")).lower()
        number = int(d["Number"])
        result.append(
            {
                "id": f"disk{number}",
                "disk_number": number,
                "path": rf"\\.\PhysicalDrive{number}",
                "name": d.get("FriendlyName") or f"PhysicalDrive{number}",
                "serial": d.get("SerialNumber") or "",
                "size": int(d.get("Size") or 0),
                "bus": bus,
                "removable": bus == "usb",
                "system": bool(d.get("IsSystem")),
                "boot": bool(d.get("IsBoot")),
                "readonly": bool(d.get("IsReadOnly")),
                "type": "disk",
            }
        )
    return result


def _linux_discover() -> list[dict]:
    cp = run([
        "lsblk", "-J", "-b", "-d", "-o",
        "NAME,PATH,SIZE,RM,TYPE,TRAN,MODEL,SERIAL"
    ])
    data = json.loads(cp.stdout)
    result = []
    for d in data.get("blockdevices", []):
        path = d.get("path") or f"/dev/{d.get('name')}"
        result.append(
            {
                "id": d.get("name") or Path(path).name,
                "path": path,
                "name": (d.get("model") or d.get("name") or "USB disk").strip(),
                "serial": (d.get("serial") or "").strip(),
                "size": int(d.get("size") or 0),
                "bus": str(d.get("tran") or "").lower(),
                "removable": str(d.get("rm")) in {"1", "true", "True"} or d.get("rm") == 1,
                "system": path == _linux_root_parent(),
                "boot": path == _linux_root_parent(),
                "readonly": False,
                "type": str(d.get("type") or ""),
            }
        )
    return result


def _linux_root_parent() -> str:
    try:
        source = run(["findmnt", "-n", "-o", "SOURCE", "/"]).stdout.strip()
        pk = run(["lsblk", "-no", "PKNAME", source]).stdout.strip()
        return f"/dev/{pk}" if pk else source
    except Exception:
        return ""


def _mac_discover() -> list[dict]:
    cp = run(["diskutil", "list", "-plist", "external", "physical"], text=False)
    payload = plistlib.loads(cp.stdout)
    result = []
    for disk in payload.get("AllDisksAndPartitions", []):
        ident = disk.get("DeviceIdentifier")
        if not ident:
            continue
        info_cp = run(["diskutil", "info", "-plist", f"/dev/{ident}"], text=False)
        info = plistlib.loads(info_cp.stdout)
        proto = str(info.get("BusProtocol") or info.get("BusName") or "").lower()
        internal = bool(info.get("Internal", True))
        removable = bool(info.get("RemovableMedia", False)) or not internal
        result.append(
            {
                "id": ident,
                "path": f"/dev/r{ident}",
                "control_path": f"/dev/{ident}",
                "name": info.get("MediaName") or ident,
                "serial": info.get("DiskUUID") or "",
                "size": int(info.get("TotalSize") or 0),
                "bus": proto,
                "removable": removable,
                "system": internal,
                "boot": internal,
                "readonly": bool(info.get("ReadOnlyMedia", False)),
                "type": "disk",
            }
        )
    return result


def discover_candidates() -> list[dict]:
    if sys.platform.startswith("win"):
        return _windows_discover()
    if sys.platform.startswith("linux"):
        return _linux_discover()
    if sys.platform == "darwin":
        return _mac_discover()
    raise RuntimeError(f"Unsupported platform: {sys.platform}")


def _windows_prepare(candidate: dict) -> None:
    n = int(candidate["disk_number"])
    script = rf"""
$ErrorActionPreference='Stop'
$disk = Get-Disk -Number {n}
if ($disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem) {{ throw 'Target no longer passes USB safety checks.' }}
if ($disk.IsReadOnly) {{ Set-Disk -Number {n} -IsReadOnly $false }}
Get-Partition -DiskNumber {n} -ErrorAction SilentlyContinue | ForEach-Object {{
  if ($_.DriveLetter) {{ cmd /c "mountvol $($_.DriveLetter): /p" | Out-Null }}
}}
Set-Disk -Number {n} -IsOffline $true
"""
    run(["powershell.exe", "-NoProfile", "-Command", script])
    time.sleep(1)


def _windows_finish(candidate: dict) -> None:
    n = int(candidate["disk_number"])
    script = rf"""
$ErrorActionPreference='SilentlyContinue'
Set-Disk -Number {n} -IsOffline $false
Update-Disk -Number {n}
"""
    run(["powershell.exe", "-NoProfile", "-Command", script], check=False)


def _linux_prepare(candidate: dict) -> None:
    dev = str(candidate["path"])
    cp = run(["lsblk", "-ln", "-o", "PATH", dev])
    paths = [x.strip() for x in cp.stdout.splitlines() if x.strip()]
    for p in reversed(paths[1:]):
        run(["umount", p], check=False)


def _linux_finish(candidate: dict) -> None:
    run(["sync"], check=False, capture=False)


def _mac_prepare(candidate: dict) -> None:
    run(["diskutil", "unmountDisk", str(candidate["control_path"])], capture=False)


def _mac_finish(candidate: dict) -> None:
    run(["diskutil", "eject", str(candidate["control_path"])], check=False, capture=False)


def prepare_target(candidate: dict) -> None:
    if sys.platform.startswith("win"):
        _windows_prepare(candidate)
    elif sys.platform.startswith("linux"):
        _linux_prepare(candidate)
    elif sys.platform == "darwin":
        _mac_prepare(candidate)


def finish_target(candidate: dict) -> None:
    if sys.platform.startswith("win"):
        _windows_finish(candidate)
    elif sys.platform.startswith("linux"):
        _linux_finish(candidate)
    elif sys.platform == "darwin":
        _mac_finish(candidate)


def require_privileges() -> None:
    if sys.platform.startswith("win"):
        if not _windows_admin():
            raise PermissionError("Run FLASH_USB_WINDOWS.cmd as Administrator.")
    else:
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            raise PermissionError("Run this flasher with sudo/root privileges.")


def locate_iso(base: Path) -> tuple[Path, Path]:
    iso = base / ISO_NAME
    sha = base / f"{ISO_NAME}.sha256"
    if not iso.is_file():
        raise FileNotFoundError(f"Missing {iso.name}. Reassemble the installer first.")
    if not sha.is_file():
        raise FileNotFoundError(f"Missing {sha.name}. Source verification is mandatory.")
    return iso, sha


def choose_candidate(candidates: Iterable[dict], image_size: int) -> dict:
    eligible = []
    for c in candidates:
        ok, reason = safe_candidate(c, image_size)
        if ok and not c.get("readonly"):
            eligible.append(c)
    if not eligible:
        raise RuntimeError("No eligible removable USB disk found. Insert one USB drive and retry.")

    print("\nEligible USB targets:\n")
    for i, c in enumerate(eligible, 1):
        serial = f" serial={c['serial']}" if c.get("serial") else ""
        print(f"  [{i}] {c['id']}  {c['name']}  {human_size(int(c['size']))}{serial}")
    raw = input("\nChoose USB number: ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(eligible)):
        raise RuntimeError("Invalid USB selection.")
    return eligible[int(raw) - 1]


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    print("Synapse OS USB Flasher")
    print("======================")
    print("This operation ERASES the selected USB drive. Internal/system disks are rejected.\n")

    try:
        require_privileges()
        iso, sha_sidecar = locate_iso(base)
        image_size = iso.stat().st_size
        expected = parse_sha256_sidecar(sha_sidecar, iso.name)
        print(f"Installer: {iso}")
        print(f"Size:      {human_size(image_size)}")
        print("Verifying source SHA-256...")
        actual = sha256_path(iso)
        if actual != expected:
            raise RuntimeError(f"SOURCE CHECKSUM MISMATCH\nexpected {expected}\nactual   {actual}")
        print(f"Source verified: {actual}\n")

        selected = choose_candidate(discover_candidates(), image_size)
        reprobe = {c["id"]: c for c in discover_candidates()}
        current = reprobe.get(selected["id"])
        if current is None:
            raise RuntimeError("Selected USB disappeared before write.")
        ok, reason = safe_candidate(current, image_size)
        if not ok:
            raise RuntimeError(f"Selected target failed re-probe: {reason}")
        if current.get("serial") and selected.get("serial") and current["serial"] != selected["serial"]:
            raise RuntimeError("Selected USB identity changed before write.")
        selected = current

        phrase = confirmation_phrase(selected)
        print("\nFINAL DESTRUCTIVE CONFIRMATION")
        print(f"Target: {selected['id']}  {selected['name']}  {human_size(int(selected['size']))}")
        print(f"Type exactly: {phrase}")
        if input("> ").strip() != phrase:
            raise RuntimeError("Confirmation did not match. Nothing was written.")

        prepared = False
        try:
            prepare_target(selected)
            prepared = True
            print("\nWriting installer image...")
            write_image(iso, selected["path"], image_size)
            print("Verifying full written image by SHA-256 read-back...")
            readback = sha256_prefix(selected["path"], image_size)
            if readback != expected:
                raise RuntimeError(
                    f"READ-BACK CHECKSUM MISMATCH\nexpected {expected}\nactual   {readback}\n"
                    "Do not boot this USB. Reflash or replace it."
                )
            print(f"\nBOOTABLE USB VERIFIED\nSHA-256: {readback}")
        finally:
            if prepared:
                finish_target(selected)
        return 0
    except KeyboardInterrupt:
        print("\nCancelled. No success state was recorded.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
