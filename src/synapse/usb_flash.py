from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Iterable


class UsbFlashError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class UsbDevice:
    name: str
    path: str
    dev_type: str
    size: int
    removable: bool
    transport: str | None
    model: str | None
    serial: str | None
    parent: str | None
    mountpoints: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        payload = {
            "name": self.name,
            "path": self.path,
            "dev_type": self.dev_type,
            "size": int(self.size),
            "removable": bool(self.removable),
            "transport": (self.transport or "").lower(),
            "model": self.model or "",
            "serial": self.serial or "",
            "parent": self.parent or "",
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.dev_type,
            "size": self.size,
            "removable": self.removable,
            "transport": self.transport,
            "model": self.model,
            "serial": self.serial,
            "parent": self.parent,
            "mountpoints": list(self.mountpoints),
            "fingerprint": self.fingerprint,
        }


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _size_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _collect_mountpoints(node: dict[str, Any]) -> tuple[str, ...]:
    out: list[str] = []
    for value in node.get("mountpoints") or []:
        if value:
            out.append(str(value))
    for child in node.get("children") or []:
        if isinstance(child, dict):
            out.extend(_collect_mountpoints(child))
    return tuple(dict.fromkeys(out))


def parse_usb_inventory(payload: dict[str, Any]) -> list[UsbDevice]:
    if not isinstance(payload, dict):
        raise UsbFlashError("INVENTORY_INVALID", "lsblk inventory must be an object")
    devices: list[UsbDevice] = []
    for raw in payload.get("blockdevices") or []:
        if not isinstance(raw, dict):
            continue
        path = str(raw.get("path") or "")
        name = str(raw.get("name") or raw.get("kname") or "")
        if not path and name:
            path = f"/dev/{name}"
        devices.append(
            UsbDevice(
                name=name,
                path=path,
                dev_type=str(raw.get("type") or ""),
                size=_size_int(raw.get("size")),
                removable=_boolish(raw.get("rm")),
                transport=(str(raw.get("tran")).lower() if raw.get("tran") is not None else None),
                model=(str(raw.get("model")).strip() if raw.get("model") is not None else None),
                serial=(str(raw.get("serial")).strip() if raw.get("serial") is not None else None),
                parent=(str(raw.get("pkname")).strip() if raw.get("pkname") is not None else None),
                mountpoints=_collect_mountpoints(raw),
            )
        )
    return devices


def _eligible_usb(device: UsbDevice, *, image_size: int, source_disk_path: str | None) -> bool:
    if device.dev_type != "disk":
        return False
    if not device.removable:
        return False
    if (device.transport or "").lower() != "usb":
        return False
    if not device.path:
        return False
    if source_disk_path and os.path.realpath(device.path) == os.path.realpath(source_disk_path):
        return False
    if device.size < int(image_size):
        return False
    return True


def select_usb_target(
    devices: Iterable[UsbDevice],
    *,
    image_size: int,
    source_disk_path: str | None,
) -> UsbDevice:
    eligible = [
        d
        for d in devices
        if _eligible_usb(d, image_size=image_size, source_disk_path=source_disk_path)
    ]
    if not eligible:
        raise UsbFlashError("NO_ELIGIBLE_USB", "no unique removable USB disk is eligible for this image")
    if len(eligible) != 1:
        raise UsbFlashError("TARGET_AMBIGUOUS", f"{len(eligible)} removable USB disks are eligible; refusing to guess")
    return eligible[0]


def _run(args: list[str], *, timeout: int = 10) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UsbFlashError("HOST_TOOL_FAILED", f"{args[0]} failed: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "command failed").strip()
        raise UsbFlashError("HOST_TOOL_FAILED", f"{args[0]} failed: {detail}")
    return proc.stdout.strip()


def probe_usb_devices() -> list[UsbDevice]:
    lsblk = shutil.which("lsblk")
    if not lsblk:
        raise UsbFlashError("LSBLK_MISSING", "lsblk is required for local-helper USB inventory")
    raw = _run(
        [
            lsblk,
            "-J",
            "-b",
            "-o",
            "NAME,KNAME,PATH,TYPE,SIZE,RM,ROTA,TRAN,MODEL,SERIAL,PKNAME,MOUNTPOINTS",
        ]
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsbFlashError("INVENTORY_INVALID", "lsblk returned invalid JSON") from exc
    return parse_usb_inventory(payload)


def source_disk_for_path(path: Path) -> str | None:
    findmnt = shutil.which("findmnt")
    lsblk = shutil.which("lsblk")
    if not findmnt or not lsblk:
        return None
    try:
        source = _run([findmnt, "-n", "-o", "SOURCE", "-T", str(path)], timeout=5).strip()
    except UsbFlashError:
        return None
    if not source.startswith("/dev/"):
        return None
    try:
        parent = _run([lsblk, "-n", "-o", "PKNAME", source], timeout=5).strip().splitlines()[0].strip()
    except (UsbFlashError, IndexError):
        parent = ""
    return f"/dev/{parent}" if parent else source


def sha256_file(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FlashState:
    phase: str = "idle"
    message: str = "Ready"
    progress: int = 0
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    bytes_written: int = 0
    total_bytes: int = 0
    target_fingerprint: str | None = None
    image_sha256: str | None = None
    readback_sha256: str | None = None


class UsbFlashManager:
    def __init__(
        self,
        *,
        image_path: Path,
        expected_sha256: str,
        simulation: bool = False,
        arm_ttl: float = 120.0,
        inventory_probe: Callable[[], list[UsbDevice]] | None = None,
        source_disk_probe: Callable[[], str | None] | None = None,
    ) -> None:
        self.image_path = image_path.expanduser().resolve()
        digest = expected_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise UsbFlashError("IMAGE_DIGEST_INVALID", "expected SHA-256 must be exactly 64 hex characters")
        self.expected_sha256 = digest
        self.simulation = bool(simulation)
        self.arm_ttl = float(arm_ttl)
        self._inventory_probe = inventory_probe or probe_usb_devices
        self._source_disk_probe = source_disk_probe or (lambda: source_disk_for_path(self.image_path))
        self._lock = threading.RLock()
        self._state = FlashState()
        self._arm: dict[str, Any] | None = None
        self._used_challenges: set[str] = set()
        self._thread: threading.Thread | None = None
        self._receipt: dict[str, Any] | None = None

    def capabilities(self) -> dict[str, Any]:
        return {
            "helper": True,
            "raw_write": True,
            "target_policy": "unique-removable-usb-only",
            "verification": "full-sha256-readback",
            "simulation": self.simulation,
        }

    def _image_verified(self) -> dict[str, Any]:
        if not self.image_path.is_file():
            raise UsbFlashError("IMAGE_MISSING", f"configured image does not exist: {self.image_path.name}")
        size = self.image_path.stat().st_size
        if size <= 0:
            raise UsbFlashError("IMAGE_EMPTY", "configured image is empty")
        actual = sha256_file(self.image_path)
        if actual != self.expected_sha256:
            raise UsbFlashError(
                "IMAGE_HASH_MISMATCH",
                f"image SHA-256 {actual} does not match expected {self.expected_sha256}",
            )
        return {
            "filename": self.image_path.name,
            "size": size,
            "sha256": actual,
            "verified": True,
            "verification": "sha256",
        }

    def image_status(self) -> dict[str, Any]:
        return self._image_verified()

    def prepare_image(self) -> dict[str, Any]:
        return self._image_verified()

    def _inventory(self) -> list[UsbDevice]:
        devices = self._inventory_probe()
        if not isinstance(devices, list) or not all(isinstance(d, UsbDevice) for d in devices):
            raise UsbFlashError("INVENTORY_INVALID", "inventory probe must return UsbDevice records")
        return devices

    def devices(self) -> list[dict[str, Any]]:
        image_size = self.image_path.stat().st_size if self.image_path.is_file() else 0
        source = self._source_disk_probe()
        rows: list[dict[str, Any]] = []
        for device in self._inventory():
            row = device.to_dict()
            row["eligible"] = _eligible_usb(device, image_size=image_size, source_disk_path=source)
            rows.append(row)
        return rows

    def preflight(self) -> dict[str, Any]:
        image = self._image_verified()
        devices = self._inventory()
        source = self._source_disk_probe()
        target = select_usb_target(devices, image_size=image["size"], source_disk_path=source)
        return {
            "ready": True,
            "source_disk": source,
            "target": target.to_dict(),
            "image": image,
            "checks": [
                {"name": "image_sha256", "ok": True},
                {"name": "unique_removable_usb", "ok": True},
                {"name": "capacity", "ok": target.size >= image["size"]},
                {"name": "source_media_excluded", "ok": source is None or os.path.realpath(target.path) != os.path.realpath(source)},
            ],
        }

    def arm(self) -> dict[str, Any]:
        preflight = self.preflight()
        target = preflight["target"]
        image = preflight["image"]
        challenge_id = secrets.token_urlsafe(24)
        now = time.time()
        acknowledgement = (
            f"FLASH:{target['fingerprint']}:IMAGE:{image['sha256']}:SIZE:{image['size']}"
        )
        arm = {
            "challenge_id": challenge_id,
            "target_fingerprint": target["fingerprint"],
            "image_sha256": image["sha256"],
            "image_size": image["size"],
            "acknowledgement": acknowledgement,
            "created_at": now,
            "expires_at": now + self.arm_ttl,
        }
        with self._lock:
            self._arm = arm
        return dict(arm)

    def start(self, challenge_id: str, acknowledgement: str) -> dict[str, Any]:
        with self._lock:
            if challenge_id in self._used_challenges:
                raise UsbFlashError("ARM_REPLAYED", "this flash authorization has already been consumed")
            arm = dict(self._arm) if self._arm else None
            if arm is None or not challenge_id or challenge_id != arm["challenge_id"]:
                raise UsbFlashError("ARM_MISMATCH", "flash challenge does not match the current authorization")
            if time.time() > float(arm["expires_at"]):
                self._used_challenges.add(challenge_id)
                raise UsbFlashError("ARM_EXPIRED", "flash authorization expired")
            if not secrets.compare_digest(str(acknowledgement), str(arm["acknowledgement"])):
                raise UsbFlashError("ARM_MISMATCH", "flash acknowledgement does not match the bound target/image")
            if self._thread and self._thread.is_alive():
                raise UsbFlashError("FLASH_ALREADY_RUNNING", "a USB flash job is already running")
            self._used_challenges.add(challenge_id)

        try:
            preflight = self.preflight()
        except UsbFlashError as exc:
            if exc.code == "IMAGE_HASH_MISMATCH":
                raise UsbFlashError("IMAGE_CHANGED", exc.message) from exc
            raise

        target_dict = preflight["target"]
        image = preflight["image"]
        if target_dict["fingerprint"] != arm["target_fingerprint"]:
            raise UsbFlashError("TARGET_CHANGED", "removable USB identity changed after arming")
        if image["sha256"] != arm["image_sha256"] or image["size"] != arm["image_size"]:
            raise UsbFlashError("IMAGE_CHANGED", "image identity changed after arming")

        target = next(d for d in self._inventory() if d.fingerprint == target_dict["fingerprint"])
        with self._lock:
            self._receipt = None
            self._state = FlashState(
                phase="queued",
                message="USB flash queued",
                progress=1,
                started_at=time.time(),
                total_bytes=image["size"],
                target_fingerprint=target.fingerprint,
                image_sha256=image["sha256"],
            )
            self._thread = threading.Thread(
                target=self._worker,
                args=(challenge_id, target, image),
                name="synapse-usb-flash",
                daemon=True,
            )
            self._thread.start()
            return asdict(self._state)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._state)

    def receipt(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._receipt) if self._receipt is not None else None

    def _set_state(self, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self._state, key, value)

    def _worker(self, challenge_id: str, target: UsbDevice, image: dict[str, Any]) -> None:
        try:
            self._write_image(target, image["size"])
            self._set_state(phase="verifying", message="Reading USB back and verifying SHA-256", progress=82)
            readback = self._verify_readback(target, image["sha256"], image["size"])
            finished = time.time()
            receipt = {
                "schema": "synapse-usb-flash-receipt/v1",
                "verified": True,
                "challenge_id": challenge_id,
                "target": target.to_dict(),
                "image": image,
                "bytes_written": image["size"],
                "readback_sha256": readback,
                "started_at": self._state.started_at,
                "finished_at": finished,
                "verification": "full-sha256-readback",
            }
            with self._lock:
                self._receipt = receipt
            self._set_state(
                phase="complete",
                message="BOOTABLE USB VERIFIED",
                progress=100,
                finished_at=finished,
                bytes_written=image["size"],
                readback_sha256=readback,
            )
        except Exception as exc:
            if isinstance(exc, UsbFlashError):
                detail = f"{exc.code}: {exc.message}"
            else:
                detail = f"WRITE_FAILED: {exc}"
            self._set_state(
                phase="failed",
                message="USB flash failed",
                error=detail,
                finished_at=time.time(),
            )

    def _unmount_target(self, target: UsbDevice) -> None:
        if self.simulation or not target.mountpoints:
            return
        umount = shutil.which("umount")
        if not umount:
            raise UsbFlashError("TARGET_BUSY", "target has mounted filesystems and umount is unavailable")
        for mountpoint in reversed(target.mountpoints):
            proc = subprocess.run([umount, mountpoint], capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "unmount failed").strip()
                raise UsbFlashError("TARGET_BUSY", f"could not unmount {mountpoint}: {detail}")

    def _require_real_write_safety(self, target: UsbDevice) -> None:
        if self.simulation:
            return
        if os.name != "posix":
            raise UsbFlashError("PLATFORM_UNSUPPORTED", "raw helper writer currently requires a POSIX/Linux host")
        if os.geteuid() != 0:
            raise UsbFlashError("ROOT_REQUIRED", "real raw USB flashing requires root")
        if not target.path.startswith("/dev/"):
            raise UsbFlashError("TARGET_INVALID", "real raw target must be a /dev block device")
        image_size = self.image_path.stat().st_size
        current = select_usb_target(
            self._inventory(),
            image_size=image_size,
            source_disk_path=self._source_disk_probe(),
        )
        if current.fingerprint != target.fingerprint:
            raise UsbFlashError("TARGET_CHANGED", "USB target changed immediately before raw write")

    def _write_image(self, target: UsbDevice, byte_count: int) -> None:
        self._require_real_write_safety(target)
        self._unmount_target(target)
        self._set_state(phase="flashing", message="Writing verified Synapse image to removable USB", progress=5)
        chunk_size = 4 * 1024 * 1024
        written = 0
        try:
            with self.image_path.open("rb") as src, open(target.path, "r+b", buffering=0) as dst:
                dst.seek(0)
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    view = memoryview(chunk)
                    offset = 0
                    while offset < len(view):
                        n = dst.write(view[offset:])
                        if n is None:
                            n = 0
                        if n <= 0:
                            raise UsbFlashError("SHORT_WRITE", "raw USB writer made no forward progress")
                        offset += n
                    written += len(chunk)
                    progress = 5 + int((written / byte_count) * 72)
                    self._set_state(progress=min(progress, 77), bytes_written=written)
                dst.flush()
                os.fsync(dst.fileno())
            if hasattr(os, "sync"):
                os.sync()
        except UsbFlashError:
            raise
        except OSError as exc:
            raise UsbFlashError("WRITE_FAILED", str(exc)) from exc
        if written != byte_count:
            raise UsbFlashError("SHORT_WRITE", f"wrote {written} of {byte_count} bytes")

    def _verify_readback(self, target: UsbDevice, expected_sha256: str, byte_count: int) -> str:
        h = hashlib.sha256()
        remaining = byte_count
        chunk_size = 4 * 1024 * 1024
        try:
            with open(target.path, "rb", buffering=0) as src:
                src.seek(0)
                while remaining:
                    chunk = src.read(min(chunk_size, remaining))
                    if not chunk:
                        raise UsbFlashError("SHORT_READ", f"USB ended with {remaining} bytes left to verify")
                    h.update(chunk)
                    remaining -= len(chunk)
                    done = byte_count - remaining
                    progress = 82 + int((done / byte_count) * 17)
                    self._set_state(progress=min(progress, 99))
        except UsbFlashError:
            raise
        except OSError as exc:
            raise UsbFlashError("VERIFY_READ_FAILED", str(exc)) from exc
        actual = h.hexdigest()
        if actual != expected_sha256:
            raise UsbFlashError(
                "VERIFY_MISMATCH",
                f"read-back SHA-256 {actual} does not match source {expected_sha256}",
            )
        return actual
