from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import threading
import time
from typing import Any, Callable

from .hardware import normalize_arch, probe_hardware

EXPECTED_LICENSE = "Cory Davis / NavisWORLD Synapse Source License 1.0"
EXPECTED_ZENODO_DOI = "10.5281/zenodo.17574447"
MANIFEST_SCHEMA = "synapse-genesis-manifest/v1"
PLAN_SCHEMA = "synapse-genesis-plan/v1"
RECEIPT_SCHEMA = "synapse-genesis-receipt/v1"


class GenesisError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BlockDevice:
    name: str
    path: str
    kind: str
    size: int
    removable: bool
    rotational: bool
    transport: str | None
    model: str | None
    serial: str | None
    parent: str | None
    mountpoints: tuple[str, ...]
    fingerprint: str

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImageManifest:
    schema: str
    synapse_version: str
    architecture: str
    image_type: str
    image_filename: str
    image_size: int
    image_sha256: str
    build_commit: str
    license: str
    zenodo_doi: str
    required_target_bytes: int
    signature: dict[str, Any] | None = None

    @classmethod
    def from_path(cls, path: Path | str) -> "ImageManifest":
        manifest_path = Path(path)
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise GenesisError("IMAGE_MISSING", f"manifest not found: {manifest_path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise GenesisError("IMAGE_MANIFEST_INVALID", f"invalid manifest: {manifest_path}") from exc
        if not isinstance(raw, dict):
            raise GenesisError("IMAGE_MANIFEST_INVALID", "manifest must be a JSON object")
        try:
            image_size = int(raw["image_size"])
            return cls(
                schema=str(raw["schema"]),
                synapse_version=str(raw["synapse_version"]),
                architecture=normalize_arch(str(raw["architecture"])),
                image_type=str(raw["image_type"]),
                image_filename=str(raw["image_filename"]),
                image_size=image_size,
                image_sha256=str(raw["image_sha256"]).lower(),
                build_commit=str(raw["build_commit"]),
                license=str(raw["license"]),
                zenodo_doi=str(raw["zenodo_doi"]),
                required_target_bytes=int(raw.get("required_target_bytes") or max(image_size * 4, 8 * 1024**3)),
                signature=raw.get("signature") if isinstance(raw.get("signature"), dict) else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GenesisError("IMAGE_MANIFEST_INVALID", "manifest is missing required fields") from exc

    def public(self) -> dict[str, Any]:
        return asdict(self)


def _fingerprint(prefix: str, fields: dict[str, Any]) -> str:
    material = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(prefix.encode('utf-8') + b'\0' + material).hexdigest()}"


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _device_from_raw(raw: dict[str, Any]) -> BlockDevice:
    path = str(raw.get("path") or ("/dev/" + str(raw.get("kname") or raw.get("name") or "")))
    mountpoints = tuple(str(x) for x in (raw.get("mountpoints") or []) if x)
    fields = {
        "path": path,
        "size": int(raw.get("size") or 0),
        "transport": raw.get("tran"),
        "model": raw.get("model"),
        "serial": raw.get("serial"),
    }
    return BlockDevice(
        name=str(raw.get("name") or raw.get("kname") or Path(path).name),
        path=path,
        kind=str(raw.get("type") or ""),
        size=fields["size"],
        removable=_boolish(raw.get("rm")),
        rotational=_boolish(raw.get("rota")),
        transport=str(raw.get("tran")) if raw.get("tran") is not None else None,
        model=str(raw.get("model")) if raw.get("model") is not None else None,
        serial=str(raw.get("serial")) if raw.get("serial") is not None else None,
        parent=str(raw.get("pkname")) if raw.get("pkname") is not None else None,
        mountpoints=mountpoints,
        fingerprint=_fingerprint("synapse-block-device-v1", fields),
    )


def parse_lsblk_inventory(payload: dict[str, Any]) -> list[BlockDevice]:
    roots = payload.get("blockdevices") if isinstance(payload, dict) else None
    if not isinstance(roots, list):
        raise GenesisError("TARGET_INVENTORY_FAILED", "lsblk output does not contain blockdevices")
    out: list[BlockDevice] = []

    def visit(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        out.append(_device_from_raw(raw))
        for child in raw.get("children") or []:
            visit(child)

    for raw in roots:
        visit(raw)
    return out


def inventory_block_devices() -> list[BlockDevice]:
    binary = shutil.which("lsblk")
    if not binary:
        raise GenesisError("TARGET_INVENTORY_FAILED", "lsblk is required")
    proc = subprocess.run(
        [
            binary,
            "--json",
            "--bytes",
            "-o",
            "NAME,KNAME,PATH,TYPE,SIZE,RM,ROTA,TRAN,MODEL,SERIAL,PKNAME,MOUNTPOINTS",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        raise GenesisError("TARGET_INVENTORY_FAILED", (proc.stderr or "lsblk failed").strip())
    try:
        return parse_lsblk_inventory(json.loads(proc.stdout))
    except json.JSONDecodeError as exc:
        raise GenesisError("TARGET_INVENTORY_FAILED", "lsblk returned invalid JSON") from exc


def source_disk_path() -> str | None:
    findmnt = shutil.which("findmnt")
    lsblk = shutil.which("lsblk")
    if not findmnt or not lsblk:
        return None
    for mountpoint in ("/run/live/medium", "/"):
        proc = subprocess.run([findmnt, "-n", "-o", "SOURCE", mountpoint], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            continue
        source = proc.stdout.strip()
        if not source.startswith("/dev/"):
            continue
        parent = subprocess.run([lsblk, "-n", "-o", "PKNAME", source], capture_output=True, text=True, timeout=5)
        if parent.returncode == 0 and parent.stdout.strip():
            return "/dev/" + parent.stdout.strip().splitlines()[0]
        return source
    return None


def select_install_target(devices: list[BlockDevice], source_disk_path: str | None) -> BlockDevice:
    source = os.path.realpath(source_disk_path) if source_disk_path else None
    candidates: list[BlockDevice] = []
    for item in devices:
        if item.kind != "disk":
            continue
        if item.removable:
            continue
        if (item.transport or "").lower() == "usb":
            continue
        if item.path.startswith(("/dev/loop", "/dev/zram", "/dev/sr", "/dev/dm-")):
            continue
        if source and os.path.realpath(item.path) == source:
            continue
        candidates.append(item)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise GenesisError("TARGET_AMBIGUOUS", "no unique eligible internal target disk was found")
    raise GenesisError("TARGET_AMBIGUOUS", "multiple eligible internal target disks were found")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise GenesisError("IMAGE_MISSING", f"image not found: {path}") from exc
    except OSError as exc:
        raise GenesisError("IMAGE_MISSING", f"image cannot be read: {path}") from exc
    return digest.hexdigest()


def verify_manifest(
    manifest: ImageManifest,
    *,
    image_path: Path | str,
    expected_arch: str,
    target_size: int,
) -> dict[str, Any]:
    image = Path(image_path)
    if manifest.schema != MANIFEST_SCHEMA or manifest.image_type != "squashfs-rootfs":
        raise GenesisError("IMAGE_MANIFEST_INVALID", "unsupported GENESIS manifest schema or image type")
    if normalize_arch(expected_arch) != manifest.architecture:
        raise GenesisError("ARCH_MISMATCH", f"image is {manifest.architecture}, device is {normalize_arch(expected_arch)}")
    if manifest.license != EXPECTED_LICENSE or manifest.zenodo_doi != EXPECTED_ZENODO_DOI:
        raise GenesisError("PROVENANCE_MISMATCH", "manifest license/provenance markers do not match Synapse policy")
    try:
        actual_size = image.stat().st_size
    except FileNotFoundError as exc:
        raise GenesisError("IMAGE_MISSING", f"image not found: {image}") from exc
    if actual_size != manifest.image_size:
        raise GenesisError("IMAGE_SIZE_MISMATCH", f"image size is {actual_size}, expected {manifest.image_size}")
    actual_sha = _sha256(image)
    if not secrets.compare_digest(actual_sha, manifest.image_sha256):
        raise GenesisError("IMAGE_HASH_MISMATCH", "Synapse image SHA-256 does not match manifest")
    required = max(manifest.required_target_bytes, manifest.image_size)
    if int(target_size) < required:
        raise GenesisError("TARGET_TOO_SMALL", f"target disk is smaller than required {required} bytes")
    return {
        "verified": True,
        "verification": "hash-verified",
        "signature_verified": False,
        "image_sha256": actual_sha,
        "image_size": actual_size,
        "required_target_bytes": required,
        "manifest": manifest.public(),
    }


def _device_fingerprint(hardware: dict[str, Any]) -> str:
    return _fingerprint(
        "synapse-device-v1",
        {
            "arch": normalize_arch(str(hardware.get("arch") or platform.machine())),
            "hwid": hardware.get("hwid"),
            "profile_id": hardware.get("profile_id"),
            "product_name": hardware.get("product_name"),
            "board_name": hardware.get("board_name"),
        },
    )


def power_snapshot() -> dict[str, Any]:
    root = Path("/sys/class/power_supply")
    ac_online: bool | None = None
    battery_percent: float | None = None
    if root.exists():
        for item in sorted(root.iterdir()):
            try:
                kind = (item / "type").read_text(encoding="utf-8").strip().lower()
            except OSError:
                continue
            if kind in {"mains", "usb", "usb_c"}:
                try:
                    ac_online = (item / "online").read_text(encoding="utf-8").strip() == "1"
                except OSError:
                    pass
            elif kind == "battery" and battery_percent is None:
                try:
                    battery_percent = float((item / "capacity").read_text(encoding="utf-8").strip())
                except (OSError, ValueError):
                    pass
    return {"ac_online": ac_online, "battery_percent": battery_percent}


def boot_mode_snapshot() -> dict[str, Any]:
    cmdline = ""
    try:
        cmdline = Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return {
        "mode": "uefi" if Path("/sys/firmware/efi").exists() else "legacy-or-unknown",
        "genesis_kernel_marker": "synapse.genesis=1" in cmdline.split(),
    }


class GenesisManager:
    def __init__(
        self,
        *,
        manifest_path: Path | str | None,
        image_path: Path | str | None,
        staging_dir: Path | str,
        installer_mode: bool,
        simulation: bool,
        arm_ttl: float = 120.0,
        hardware_probe: Callable[[], dict[str, Any]] = probe_hardware,
        inventory_probe: Callable[[], list[BlockDevice]] = inventory_block_devices,
        source_disk_probe: Callable[[], str | None] = source_disk_path,
        power_probe: Callable[[], dict[str, Any]] = power_snapshot,
        boot_mode_probe: Callable[[], dict[str, Any]] = boot_mode_snapshot,
    ) -> None:
        self.manifest_path = Path(manifest_path).resolve() if manifest_path else None
        self.image_path = Path(image_path).resolve() if image_path else None
        self.staging_dir = Path(staging_dir).resolve()
        self.installer_mode = bool(installer_mode)
        self.simulation = bool(simulation)
        self.arm_ttl = float(arm_ttl)
        self.hardware_probe = hardware_probe
        self.inventory_probe = inventory_probe
        self.source_disk_probe = source_disk_probe
        self.power_probe = power_probe
        self.boot_mode_probe = boot_mode_probe
        self._lock = threading.RLock()
        self._challenges: dict[str, dict[str, Any]] = {}
        self._state: dict[str, Any] = {
            "phase": "idle",
            "progress": 0,
            "message": "GENESIS ready",
            "error": None,
        }
        self._receipt: dict[str, Any] | None = None
        self._thread: threading.Thread | None = None

    def _phase(self, phase: str, progress: int, message: str) -> None:
        with self._lock:
            self._state.update({"phase": phase, "progress": progress, "message": message, "error": None})
            if self._receipt is not None:
                self._receipt["phases"].append({"phase": phase, "at": time.time(), "message": message})
                self._persist_receipt_locked()

    def _persist_receipt_locked(self) -> None:
        if self._receipt is None:
            return
        try:
            self.staging_dir.mkdir(parents=True, exist_ok=True)
            (self.staging_dir / "receipt.json").write_text(
                json.dumps(self._receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        except OSError:
            pass

    def preflight(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        hardware = self.hardware_probe()
        arch = normalize_arch(str(hardware.get("arch") or platform.machine()))
        device_fp = _device_fingerprint(hardware)
        target = select_install_target(self.inventory_probe(), self.source_disk_probe())
        checks.append({"name": "target", "ok": True, "message": "unique internal target identified"})

        if not self.manifest_path or not self.image_path:
            raise GenesisError("IMAGE_MISSING", "GENESIS manifest/image are not configured")
        manifest = ImageManifest.from_path(self.manifest_path)
        image = verify_manifest(manifest, image_path=self.image_path, expected_arch=arch, target_size=target.size)
        checks.append({"name": "image", "ok": True, "message": image["verification"]})

        power = self.power_probe()
        ac_online = power.get("ac_online")
        battery = power.get("battery_percent")
        power_ok = ac_online is True or (battery is not None and float(battery) >= 50.0) or (ac_online is None and battery is None)
        if not power_ok:
            raise GenesisError("POWER_INSUFFICIENT", "connect external power or charge the battery above 50%")
        checks.append({"name": "power", "ok": True, "message": "power preflight passed"})

        boot = self.boot_mode_probe()
        if self.installer_mode and not self.simulation and not boot.get("genesis_kernel_marker"):
            raise GenesisError("INSTALLER_DISABLED", "installer mode requires kernel marker synapse.genesis=1")
        checks.append({"name": "boot", "ok": True, "message": str(boot.get("mode") or "unknown")})

        return {
            "ready": True,
            "device_fingerprint": device_fp,
            "hardware": hardware,
            "target": target.public(),
            "image": image,
            "power": power,
            "boot": boot,
            "checks": checks,
            "installer_mode": self.installer_mode,
            "simulation": self.simulation,
        }

    def image_status(self) -> dict[str, Any]:
        preflight = self.preflight()
        return preflight["image"]

    def arm(self) -> dict[str, Any]:
        preflight = self.preflight()
        now = time.time()
        challenge_id = secrets.token_urlsafe(24)
        target_id = preflight["target"]["fingerprint"]
        image_sha = preflight["image"]["image_sha256"]
        ack = f"ERASE:{target_id}:INSTALL:{image_sha}"
        challenge = {
            "challenge_id": challenge_id,
            "device_fingerprint": preflight["device_fingerprint"],
            "target_disk_id": target_id,
            "image_sha256": image_sha,
            "issued_at": now,
            "expires_at": now + self.arm_ttl,
            "acknowledgement": ack,
            "consumed": False,
        }
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "created_at": now,
            "hardware": preflight["hardware"],
            "device_fingerprint": preflight["device_fingerprint"],
            "target": preflight["target"],
            "image": preflight["image"]["manifest"],
            "image_sha256": image_sha,
            "license": EXPECTED_LICENSE,
            "zenodo_doi": EXPECTED_ZENODO_DOI,
            "challenge_id": challenge_id,
            "phases": [{"phase": "armed", "at": now, "message": "destructive install armed"}],
            "final_state": None,
            "error": None,
        }
        with self._lock:
            self._challenges[challenge_id] = challenge
            self._receipt = receipt
            self._state = {"phase": "armed", "progress": 2, "message": "GENESIS armed", "error": None}
            self._persist_receipt_locked()
        return {k: v for k, v in challenge.items() if k != "consumed"}

    def _validate_challenge(self, challenge_id: str, acknowledgement: str) -> tuple[dict[str, Any], dict[str, Any]]:
        with self._lock:
            challenge = self._challenges.get(challenge_id)
            if challenge is None or challenge.get("consumed"):
                raise GenesisError("ARM_REPLAYED", "arm challenge is unknown or already consumed")
            if time.time() > float(challenge["expires_at"]):
                challenge["consumed"] = True
                raise GenesisError("ARM_EXPIRED", "arm challenge expired")
            if not secrets.compare_digest(str(challenge["acknowledgement"]), acknowledgement):
                raise GenesisError("ARM_MISMATCH", "destructive acknowledgement does not match arm challenge")

        preflight = self.preflight()
        if preflight["device_fingerprint"] != challenge["device_fingerprint"]:
            raise GenesisError("ARM_MISMATCH", "device changed after arming")
        if preflight["target"]["fingerprint"] != challenge["target_disk_id"]:
            raise GenesisError("ARM_MISMATCH", "target disk changed after arming")
        if preflight["image"]["image_sha256"] != challenge["image_sha256"]:
            raise GenesisError("ARM_MISMATCH", "image changed after arming")
        return challenge, preflight

    def start(self, challenge_id: str, acknowledgement: str) -> dict[str, Any]:
        challenge, preflight = self._validate_challenge(challenge_id, acknowledgement)
        if not self.simulation and not self.installer_mode:
            raise GenesisError("INSTALLER_DISABLED", "destructive installer mode is disabled")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise GenesisError("INSTALL_ALREADY_RUNNING", "a GENESIS install is already running")
            challenge["consumed"] = True
            self._thread = threading.Thread(
                target=self._worker,
                args=(preflight,),
                name="synapse-genesis-install",
                daemon=True,
            )
            self._thread.start()
            return dict(self._state)

    def _worker(self, preflight: dict[str, Any]) -> None:
        try:
            self._phase("staging", 20, "writing immutable GENESIS install plan")
            self.staging_dir.mkdir(parents=True, exist_ok=True)
            plan = {
                "schema": PLAN_SCHEMA,
                "created_at": time.time(),
                "device_fingerprint": preflight["device_fingerprint"],
                "target": preflight["target"],
                "image_path": str(self.image_path),
                "manifest_path": str(self.manifest_path),
                "image_sha256": preflight["image"]["image_sha256"],
                "architecture": preflight["hardware"].get("arch"),
                "license": EXPECTED_LICENSE,
                "zenodo_doi": EXPECTED_ZENODO_DOI,
            }
            (self.staging_dir / "install-plan.json").write_text(
                json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            if self.simulation:
                self._phase("installing", 55, "simulation: destructive writer not invoked")
                self._phase("verifying", 85, "simulation: install plan and provenance verified")
                self._phase("complete", 100, "GENESIS simulation complete")
                with self._lock:
                    if self._receipt is not None:
                        self._receipt["final_state"] = "complete"
                        self._receipt["finished_at"] = time.time()
                        self._persist_receipt_locked()
                return
            raise GenesisError("INSTALLER_DISABLED", "GENESIS writer is not wired yet")
        except GenesisError as exc:
            with self._lock:
                self._state = {"phase": "failed", "progress": self._state.get("progress", 0), "message": exc.message, "error": {"code": exc.code, "message": exc.message}}
                if self._receipt is not None:
                    self._receipt["phases"].append({"phase": "failed", "at": time.time(), "message": exc.message})
                    self._receipt["final_state"] = "failed"
                    self._receipt["error"] = {"code": exc.code, "message": exc.message}
                    self._receipt["finished_at"] = time.time()
                    self._persist_receipt_locked()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def receipt(self) -> dict[str, Any] | None:
        with self._lock:
            return json.loads(json.dumps(self._receipt)) if self._receipt is not None else None
