from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from typing import BinaryIO

CHUNK_SIZE = 4 * 1024 * 1024
VERIFY_SAMPLE = 1024 * 1024


class UsbWriterError(RuntimeError):
    pass


@dataclass(frozen=True)
class DiskCandidate:
    device: str
    size: int
    label: str
    transport: str
    system: bool = False


def human_size(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    n = float(value)
    for unit in units:
        if n < 1024.0 or unit == units[-1]:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{value} B"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def checksum_from_file(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise UsbWriterError("checksum file is empty")
    digest = text.split()[0].lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise UsbWriterError("checksum file does not begin with a SHA-256 digest")
    return digest


def verify_iso_checksum(iso: Path, checksum: Path) -> str:
    expected = checksum_from_file(checksum)
    actual = sha256_file(iso)
    if actual != expected:
        raise UsbWriterError(f"ISO checksum mismatch: expected {expected}, got {actual}")
    return actual


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise UsbWriterError((proc.stderr or proc.stdout or "command failed").strip())
    return proc.stdout


def _walk_mounts(item: dict) -> list[str]:
    mounts = [x for x in (item.get("mountpoints") or []) if x]
    for child in item.get("children") or []:
        mounts.extend(_walk_mounts(child))
    return mounts


def linux_candidates() -> list[DiskCandidate]:
    if not shutil.which("lsblk"):
        return []
    data = json.loads(_run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,RM,TRAN,MODEL,MOUNTPOINTS"]))
    out: list[DiskCandidate] = []
    for item in data.get("blockdevices", []):
        if item.get("type") != "disk":
            continue
        transport = str(item.get("tran") or "")
        if not bool(item.get("rm")) and transport.lower() != "usb":
            continue
        mounts = _walk_mounts(item)
        system = any(x in mounts for x in ("/", "/boot", "/boot/efi"))
        out.append(DiskCandidate(str(item["path"]), int(item.get("size") or 0), (item.get("model") or item["name"]).strip(), transport or "removable", system))
    return out


def mac_candidates() -> list[DiskCandidate]:
    if not shutil.which("diskutil"):
        return []
    raw = subprocess.run(["diskutil", "list", "-plist", "external", "physical"], capture_output=True)
    if raw.returncode != 0:
        raise UsbWriterError(raw.stderr.decode(errors="replace").strip() or "diskutil failed")
    data = plistlib.loads(raw.stdout)
    out: list[DiskCandidate] = []
    for item in data.get("AllDisksAndPartitions", []):
        ident = item.get("DeviceIdentifier")
        if ident:
            out.append(DiskCandidate(f"/dev/{ident}", int(item.get("Size") or 0), item.get("Content") or ident, "external", False))
    return out


def windows_candidates() -> list[DiskCandidate]:
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return []
    script = "Get-Disk | Where-Object {$_.BusType -eq 'USB'} | Select-Object Number,FriendlyName,Size,BusType,IsBoot,IsSystem | ConvertTo-Json -Compress"
    text = _run([ps, "-NoProfile", "-Command", script]).strip()
    if not text:
        return []
    data = json.loads(text)
    rows = data if isinstance(data, list) else [data]
    out: list[DiskCandidate] = []
    for item in rows:
        num = int(item["Number"])
        out.append(DiskCandidate(fr"\\.\PhysicalDrive{num}", int(item.get("Size") or 0), item.get("FriendlyName") or f"PhysicalDrive{num}", "USB", bool(item.get("IsBoot") or item.get("IsSystem"))))
    return out


def candidates() -> list[DiskCandidate]:
    if sys.platform.startswith("linux"):
        return linux_candidates()
    if sys.platform == "darwin":
        return mac_candidates()
    if os.name == "nt":
        return windows_candidates()
    return []


def canonical_device(value: str) -> str:
    if os.name == "nt":
        return value.lower()
    return str(Path(value).resolve())


def resolve_candidate(device: str) -> DiskCandidate:
    wanted = canonical_device(device)
    for item in candidates():
        if canonical_device(item.device) == wanted:
            if item.system:
                raise UsbWriterError("refusing a disk marked as boot/system")
            return item
    raise UsbWriterError("target is not in the detected removable/external USB device list")


def unmount_candidate(candidate: DiskCandidate) -> None:
    if sys.platform.startswith("linux") and shutil.which("lsblk"):
        paths = [x.strip() for x in _run(["lsblk", "-ln", "-o", "PATH", candidate.device]).splitlines() if x.strip()]
        for path in paths[1:]:
            subprocess.run(["umount", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "darwin":
        _run(["diskutil", "unmountDisk", candidate.device])
    elif os.name == "nt":
        ps = shutil.which("powershell") or shutil.which("pwsh")
        if ps and candidate.device.lower().startswith(r"\\.\physicaldrive"):
            number = int(candidate.device.lower().split("physicaldrive", 1)[1])
            script = f"Get-Partition -DiskNumber {number} -ErrorAction SilentlyContinue | Where-Object {{$_.DriveLetter}} | ForEach-Object {{ Remove-PartitionAccessPath -DiskNumber {number} -PartitionNumber $_.PartitionNumber -AccessPath ($_.DriveLetter + ':\\') -ErrorAction SilentlyContinue }}"
            subprocess.run([ps, "-NoProfile", "-Command", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_stream(source: BinaryIO, target: BinaryIO, total: int, *, progress: bool = True) -> None:
    written = 0
    while True:
        chunk = source.read(CHUNK_SIZE)
        if not chunk:
            break
        target.write(chunk)
        written += len(chunk)
        if progress:
            pct = 100.0 if not total else written * 100.0 / total
            print(f"\rWriting {human_size(written)} / {human_size(total)} ({pct:5.1f}%)", end="", flush=True)
    target.flush()
    try:
        os.fsync(target.fileno())
    except (AttributeError, OSError):
        pass
    if progress:
        print()


def compare_samples(iso: Path, device: str, iso_size: int) -> None:
    sample = min(VERIFY_SAMPLE, iso_size)
    offsets = [0]
    if iso_size > sample:
        offsets.append(iso_size - sample)
    with iso.open("rb", buffering=0) as source, open(device, "rb", buffering=0) as target:
        for offset in offsets:
            source.seek(offset)
            target.seek(offset)
            if target.read(sample) != source.read(sample):
                raise UsbWriterError(f"post-write verification failed at byte offset {offset}")


def write_iso(iso: Path, candidate: DiskCandidate, *, progress: bool = True) -> None:
    iso_size = iso.stat().st_size
    if iso_size <= 0:
        raise UsbWriterError("ISO is empty")
    if candidate.size and iso_size > candidate.size:
        raise UsbWriterError(f"ISO is {human_size(iso_size)} but target is only {human_size(candidate.size)}")
    unmount_candidate(candidate)
    device = candidate.device
    if sys.platform == "darwin" and device.startswith("/dev/disk"):
        raw = "/dev/r" + device.removeprefix("/dev/")
        if Path(raw).exists():
            device = raw
    try:
        with iso.open("rb", buffering=0) as source, open(device, "r+b", buffering=0) as target:
            target.seek(0)
            write_stream(source, target, iso_size, progress=progress)
    except PermissionError as exc:
        raise UsbWriterError("permission denied; run from an Administrator/root terminal") from exc
    except OSError as exc:
        raise UsbWriterError(f"raw USB write failed: {exc}") from exc
    compare_samples(iso, device, iso_size)


def list_devices() -> int:
    items = candidates()
    if not items:
        print("No removable/external USB disks detected.")
        return 1
    for item in items:
        status = "REFUSED(system)" if item.system else "eligible"
        print(f"{item.device:24} {human_size(item.size):>10}  {status:16}  {item.label}")
    return 0


def command_write(args: argparse.Namespace) -> int:
    iso = Path(args.iso).expanduser().resolve()
    if not iso.is_file():
        raise UsbWriterError(f"ISO not found: {iso}")
    candidate = resolve_candidate(args.device)
    expected_confirm = f"ERASE:{candidate.device}"
    if args.confirm != expected_confirm:
        raise UsbWriterError(f"confirmation mismatch; pass exactly --confirm {expected_confirm!r}")
    checksum = Path(args.checksum).expanduser().resolve() if args.checksum else Path(str(iso) + ".sha256")
    if not checksum.is_file():
        raise UsbWriterError("checksum file is required; pass --checksum or place <iso>.sha256 next to the ISO")
    digest = verify_iso_checksum(iso, checksum)
    print(f"ISO:      {iso}")
    print(f"SHA-256:  {digest}")
    print(f"Target:   {candidate.device} ({candidate.label}, {human_size(candidate.size)})")
    if args.dry_run:
        print("Dry run only. No bytes written.")
        return 0
    print("WARNING: the target USB disk will be overwritten.")
    write_iso(iso, candidate)
    print("Synapse USB write complete and sampled verification passed.")
    print("Eject the USB, boot the target computer from UEFI/USB, then launch Install Synapse OS.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="synapse-usb", description="Guarded Synapse OS bootable USB writer")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list removable/external USB disks")
    w = sub.add_parser("write", help="write a verified Synapse OS hybrid ISO to a USB disk")
    w.add_argument("--iso", required=True)
    w.add_argument("--device", required=True)
    w.add_argument("--checksum")
    w.add_argument("--confirm", required=True, help="must equal ERASE:<device>")
    w.add_argument("--dry-run", action="store_true", help="perform all validation without writing")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "list":
            return list_devices()
        return command_write(args)
    except UsbWriterError as exc:
        print(f"synapse-usb: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
