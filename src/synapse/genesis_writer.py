from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Callable

from .genesis import (
    EXPECTED_LICENSE,
    EXPECTED_ZENODO_DOI,
    PLAN_SCHEMA,
    BlockDevice,
    GenesisError,
    inventory_block_devices,
    source_disk_path,
)
from .hardware import normalize_arch


CommandRunner = Callable[..., str]
InventoryProbe = Callable[[], list[BlockDevice]]
SourceDiskProbe = Callable[[], str | None]


def _run(argv: list[str], *, timeout: int = 900) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "command failed").strip()
        raise GenesisError("WRITE_FAILED", f"{Path(argv[0]).name}: {detail}")
    return proc.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise GenesisError("IMAGE_MISSING", f"cannot read image: {path}") from exc
    return digest.hexdigest()


def _read_json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenesisError(code, f"invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise GenesisError(code, f"JSON must be an object: {path}")
    return payload


def _current_cmdline() -> str:
    try:
        return Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def partition_paths(target: str) -> tuple[str, str]:
    name = Path(target).name
    suffix = "p" if name and name[-1].isdigit() else ""
    return f"{target}{suffix}1", f"{target}{suffix}2"


def _same_device(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return os.path.realpath(a) == os.path.realpath(b)


def validate_install_plan(
    plan: dict[str, Any],
    *,
    inventory: list[BlockDevice],
    source_disk_path: str | None,
) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise GenesisError("PLAN_INVALID", "unsupported GENESIS install-plan schema")
    if plan.get("license") != EXPECTED_LICENSE or plan.get("zenodo_doi") != EXPECTED_ZENODO_DOI:
        raise GenesisError("PROVENANCE_MISMATCH", "install plan license/provenance does not match Synapse policy")

    architecture = normalize_arch(str(plan.get("architecture") or ""))
    if architecture != "amd64":
        raise GenesisError("ARCH_MISMATCH", "GENESIS v1 destructive writer supports amd64 only")

    target_data = plan.get("target")
    if not isinstance(target_data, dict):
        raise GenesisError("PLAN_INVALID", "install plan target is missing")
    target_path = str(target_data.get("path") or "")
    target_fingerprint = str(target_data.get("fingerprint") or "")
    if not target_path.startswith("/dev/") or not target_fingerprint.startswith("sha256:"):
        raise GenesisError("PLAN_INVALID", "install plan target identity is incomplete")

    current = next((item for item in inventory if item.kind == "disk" and item.path == target_path), None)
    if current is None or not secrets_compare(current.fingerprint, target_fingerprint):
        raise GenesisError("ARM_MISMATCH", "target disk identity changed after arming")
    if _same_device(target_path, source_disk_path):
        raise GenesisError("ARM_MISMATCH", "target disk is the current installer/source-media disk")
    if current.removable or (current.transport or "").lower() == "usb":
        raise GenesisError("TARGET_REMOVABLE", "GENESIS refuses removable or USB target disks")
    if current.path.startswith(("/dev/loop", "/dev/zram", "/dev/sr", "/dev/dm-")):
        raise GenesisError("TARGET_REMOVABLE", "GENESIS refuses virtual or non-installable target devices")

    image_path_text = str(plan.get("image_path") or "")
    expected_sha = str(plan.get("image_sha256") or "").lower()
    if not image_path_text or not expected_sha:
        raise GenesisError("PLAN_INVALID", "install plan image identity is incomplete")
    image_path = Path(image_path_text)
    actual_sha = _sha256(image_path)
    if not secrets_compare(actual_sha, expected_sha):
        raise GenesisError("IMAGE_HASH_MISMATCH", "staged Synapse image changed after arming")

    validated = dict(plan)
    validated["target"] = current.public()
    validated["image_path"] = str(image_path)
    validated["image_sha256"] = actual_sha
    validated["architecture"] = architecture
    return validated


def secrets_compare(left: str, right: str) -> bool:
    # Local helper keeps comparison semantics explicit without exposing mutable state.
    import secrets

    return secrets.compare_digest(left, right)


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record(receipt: dict[str, Any], phase: str, message: str) -> None:
    receipt.setdefault("phases", []).append({"phase": phase, "at": time.time(), "message": message})


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise GenesisError("WRITE_FAILED", f"required installer tool is missing: {name}")
    return path


def _mounted_target_children(target: str, runner: CommandRunner) -> list[str]:
    lsblk = _require_tool("lsblk")
    text = runner([lsblk, "-nrpo", "PATH,MOUNTPOINT", target], timeout=15)
    mounts: list[str] = []
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[1].strip():
            mounts.append(parts[1].strip())
    return sorted(set(mounts), key=len, reverse=True)


def _partition_and_install(
    plan: dict[str, Any],
    receipt: dict[str, Any],
    runner: CommandRunner,
    mount_root: Path,
) -> dict[str, Any]:
    target = str(plan["target"]["path"])
    image = Path(str(plan["image_path"]))
    esp, root_partition = partition_paths(target)
    mount_root = Path(mount_root)
    esp_mount = mount_root / "boot" / "efi"

    wipefs = _require_tool("wipefs")
    parted = _require_tool("parted")
    partprobe = _require_tool("partprobe")
    udevadm = _require_tool("udevadm")
    mkfs_vfat = _require_tool("mkfs.vfat")
    mkfs_ext4 = _require_tool("mkfs.ext4")
    mount = _require_tool("mount")
    umount = _require_tool("umount")
    unsquashfs = _require_tool("unsquashfs")
    blkid = _require_tool("blkid")
    grub_install = _require_tool("grub-install")
    sync = _require_tool("sync")

    mounted_root = False
    mounted_esp = False
    try:
        _record(receipt, "unmount", "unmounting existing target filesystems")
        for mounted in _mounted_target_children(target, runner):
            runner([umount, mounted], timeout=60)

        _record(receipt, "partition", "creating Synapse GPT, EFI, and root partitions")
        runner([wipefs, "-a", target], timeout=60)
        runner([parted, "-s", target, "mklabel", "gpt"], timeout=60)
        runner([parted, "-s", target, "mkpart", "ESP", "fat32", "1MiB", "513MiB"], timeout=60)
        runner([parted, "-s", target, "set", "1", "esp", "on"], timeout=60)
        runner([parted, "-s", target, "mkpart", "root", "ext4", "513MiB", "100%"], timeout=60)
        runner([partprobe, target], timeout=60)
        runner([udevadm, "settle"], timeout=60)

        _record(receipt, "format", "formatting Synapse EFI and root filesystems")
        runner([mkfs_vfat, "-F", "32", "-n", "SYNAPSE_EFI", esp], timeout=180)
        runner([mkfs_ext4, "-F", "-L", "SYNAPSE_ROOT", root_partition], timeout=300)

        mount_root.mkdir(parents=True, exist_ok=True)
        runner([mount, root_partition, str(mount_root)], timeout=60)
        mounted_root = True
        esp_mount.mkdir(parents=True, exist_ok=True)
        runner([mount, esp, str(esp_mount)], timeout=60)
        mounted_esp = True

        _record(receipt, "extract", "extracting verified Synapse root filesystem")
        runner([unsquashfs, "-f", "-d", str(mount_root), str(image)], timeout=1800)

        root_uuid = runner([blkid, "-s", "UUID", "-o", "value", root_partition], timeout=30).strip()
        esp_uuid = runner([blkid, "-s", "UUID", "-o", "value", esp], timeout=30).strip()
        if not root_uuid or not esp_uuid:
            raise GenesisError("VERIFY_FAILED", "could not read installed filesystem UUIDs")
        etc = mount_root / "etc"
        etc.mkdir(parents=True, exist_ok=True)
        (etc / "fstab").write_text(
            f"UUID={root_uuid} / ext4 defaults,noatime 0 1\n"
            f"UUID={esp_uuid} /boot/efi vfat umask=0077 0 2\n",
            encoding="utf-8",
        )

        _record(receipt, "bootloader", "installing removable UEFI GRUB bootloader")
        runner(
            [
                grub_install,
                "--target=x86_64-efi",
                f"--efi-directory={esp_mount}",
                f"--boot-directory={mount_root / 'boot'}",
                "--removable",
                "--no-nvram",
            ],
            timeout=300,
        )

        kernels = sorted((mount_root / "boot").glob("vmlinuz-*"))
        initrds = sorted((mount_root / "boot").glob("initrd.img-*"))
        if not kernels or not initrds:
            raise GenesisError("VERIFY_FAILED", "installed rootfs does not contain a kernel/initramfs pair")
        kernel = kernels[-1].name
        initrd = initrds[-1].name
        grub_dir = mount_root / "boot" / "grub"
        grub_dir.mkdir(parents=True, exist_ok=True)
        (grub_dir / "grub.cfg").write_text(
            "set timeout=3\n"
            "set default=0\n"
            "menuentry 'Synapse OS' {\n"
            f"  search --no-floppy --fs-uuid --set=root {root_uuid}\n"
            f"  linux /boot/{kernel} root=UUID={root_uuid} rw quiet splash\n"
            f"  initrd /boot/{initrd}\n"
            "}\n",
            encoding="utf-8",
        )

        _record(receipt, "receipt", "embedding GENESIS installation receipt")
        embedded = mount_root / "var" / "lib" / "synapse" / "genesis" / "receipt.json"
        _write_receipt(embedded, receipt)
        runner([sync], timeout=120)

        _record(receipt, "verify", "verifying installed Synapse identity and provenance")
        os_release = mount_root / "etc" / "os-release"
        try:
            os_text = os_release.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise GenesisError("VERIFY_FAILED", "installed /etc/os-release is missing") from exc
        required = (
            mount_root / "usr" / "share" / "doc" / "synapse-os" / "LICENSE",
            mount_root / "usr" / "share" / "doc" / "synapse-os" / "PROVENANCE.md",
            mount_root / "usr" / "share" / "synapse" / "phone-bootstrap.html",
        )
        if "ID=synapseos" not in os_text or any(not path.is_file() for path in required):
            raise GenesisError("VERIFY_FAILED", "installed Synapse identity/provenance markers are incomplete")

        receipt["final_state"] = "complete"
        receipt["finished_at"] = time.time()
        _record(receipt, "complete", "Synapse OS installation verified")
        return receipt
    finally:
        if mounted_esp:
            try:
                runner([umount, str(esp_mount)], timeout=60)
            except Exception:
                pass
        if mounted_root:
            try:
                runner([umount, str(mount_root)], timeout=60)
            except Exception:
                pass


def run_install(
    plan_path: Path | str,
    receipt_path: Path | str,
    *,
    execute: bool = False,
    inventory_probe: InventoryProbe = inventory_block_devices,
    source_disk_probe: SourceDiskProbe = source_disk_path,
    command_runner: CommandRunner = _run,
    euid: int | None = None,
    cmdline: str | None = None,
    installer: Callable[[dict[str, Any], dict[str, Any], CommandRunner, Path], dict[str, Any]] = _partition_and_install,
    mount_root: Path | str = Path("/mnt/synapse-genesis-target"),
) -> dict[str, Any]:
    plan_file = Path(plan_path)
    receipt_file = Path(receipt_path)
    plan = _read_json_object(plan_file, code="PLAN_INVALID")
    receipt = _read_json_object(receipt_file, code="RECEIPT_INVALID")
    validated = validate_install_plan(
        plan,
        inventory=inventory_probe(),
        source_disk_path=source_disk_probe(),
    )

    if not execute:
        result = dict(receipt)
        result["final_state"] = "simulated"
        result["simulation"] = True
        _record(result, "validated", "GENESIS writer simulation validated target and image; no disk commands executed")
        return result

    effective_euid = os.geteuid() if euid is None else int(euid)
    effective_cmdline = _current_cmdline() if cmdline is None else str(cmdline)
    if effective_euid != 0:
        raise GenesisError("INSTALLER_DISABLED", "destructive GENESIS writer requires root")
    if "synapse.genesis=1" not in effective_cmdline.split():
        raise GenesisError("INSTALLER_DISABLED", "destructive GENESIS writer requires kernel marker synapse.genesis=1")
    if validated["architecture"] != "amd64":
        raise GenesisError("ARCH_MISMATCH", "GENESIS v1 destructive writer supports amd64 only")

    result = installer(validated, receipt, command_runner, Path(mount_root))
    if not isinstance(result, dict):
        raise GenesisError("WRITE_FAILED", "GENESIS installer returned an invalid result")
    _write_receipt(receipt_file, result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synapse OS GENESIS fixed-purpose installer writer")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--execute", action="store_true", help="perform the destructive install; requires root and synapse.genesis=1")
    parser.add_argument("--mount-root", default="/mnt/synapse-genesis-target")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_install(
            args.plan,
            args.receipt,
            execute=args.execute,
            mount_root=Path(args.mount_root),
        )
    except GenesisError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message}}))
        return 2
    print(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
