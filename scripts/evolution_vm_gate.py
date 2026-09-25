#!/usr/bin/env python3
"""Compare fixed baseline and staged candidate checks inside TWO disconnected QEMU boots.

No model runs on the CI host. Candidate source is treated as untrusted and
exposed only through a read-only, verified payload ISO. This is a VM smoke
evaluator, not a security proof or approval to deploy any generated patch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

SCHEMA = "synapse.evolution.vm.payload.v1"
RESULT = "SYNAPSE_EVO_RESULT:"
GUEST_SCRIPT = Path("rootfs/usr/local/lib/synapse/evolution-vm-evaluator.py")
RECEIPT_SCHEMA = "synapse.evolution.receipt.v1"
ALLOWED = re.compile(r"src/synapse/[A-Za-z][A-Za-z0-9_]{0,65}\.py\Z")
PROTECTED = {"evolution.py", "evolution_model.py", "cli.py", "agent.py", "__init__.py"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tool(*args: str, timeout: int = 60) -> bytes:
    done = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if done.returncode:
        raise ValueError(f"trusted tool failed: {Path(args[0]).name} exit {done.returncode}")
    return done.stdout


def validate(repo: Path, receipt_dir: Path) -> tuple[dict, list[tuple[Path, bytes]]]:
    repo = repo.resolve(strict=True)
    if not (repo / GUEST_SCRIPT).is_file():
        raise ValueError("trusted guest evaluator is missing from the selected source")
    head = tool("git", "-C", str(repo), "rev-parse", "HEAD").decode().strip()
    dirty = tool("git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise ValueError("tracked repository is not clean")
    receipt_path = receipt_dir / "RECEIPT.json"
    patch_path = receipt_dir / "PATCH_REVIEW.diff"
    if receipt_path.is_symlink() or patch_path.is_symlink():
        raise ValueError("receipt and patch must be regular files")
    data = receipt_path.read_bytes()
    if len(data) > 30_000 or not data:
        raise ValueError("bounded Stage 1 receipt is required")
    receipt = json.loads(data)
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("base_commit") != head:
        raise ValueError("Stage 1 receipt does not match exact source HEAD")
    if receipt.get("production_modified") is not False or receipt.get("promotion") != "OWNER_REVIEW_REQUIRED":
        raise ValueError("Stage 1 authority boundary not verified")
    if receipt.get("execution") != "STATIC_SYNTAX_ONLY" or receipt.get("tests") != "NOT_RUN":
        raise ValueError("Stage 1 receipt claims incompatible execution")
    diff = patch_path.read_bytes()
    if not diff or len(diff) > 250_000 or sha(diff) != receipt.get("patch_sha256"):
        raise ValueError("review patch SHA-256 mismatch")
    work = Path(receipt.get("workspace", ""))
    if not work.is_absolute() or not work.is_dir() or work.resolve() != work:
        raise ValueError("stage workspace is not an absolute existing directory")
    changes = receipt.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 3:
        raise ValueError("only 1-3 reviewed changes are allowed")
    verified = []
    seen = set()
    for item in changes:
        if not isinstance(item, dict) or set(item) != {
            "path", "before_sha256", "after_sha256"
        }:
            raise ValueError("invalid change receipt fields")
        path = item["path"]
        if not isinstance(path, str) or not ALLOWED.fullmatch(path):
            raise ValueError("VM evaluator currently only accepts source Python files")
        if path in seen or path.split("/")[-1] in PROTECTED:
            raise ValueError("duplicate or protected candidate path")
        seen.add(path)
        original = repo / path
        proposed = work / path
        if original.is_symlink() or proposed.is_symlink() or not original.is_file() or not proposed.is_file():
            raise ValueError("candidate source is missing, not a file or a symlink")
        before, after = original.read_bytes(), proposed.read_bytes()
        if sha(before) != item["before_sha256"] or sha(after) != item["after_sha256"]:
            raise ValueError("source contents do not match original/staged receipts")
        if not after or len(after) > 64_000:
            raise ValueError("candidate size outside validated Stage 1 limits")
        verified.append((Path(path), after))
    return receipt, verified


def verify_iso(repo: Path, iso: Path, expected_sha: str, files: list[tuple[Path, bytes]],
               work: Path) -> tuple[Path, Path]:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise ValueError("explicit trusted ISO SHA-256 required")
    iso = iso.resolve(strict=True)
    if not iso.is_file():
        raise ValueError("ISO is not a regular file")
    hasher = hashlib.sha256()
    with iso.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            hasher.update(block)
    if hasher.hexdigest() != expected_sha:
        raise ValueError("Synapse candidate ISO SHA-256 mismatch")
    image = work / "filesystem.squashfs"
    kernel, initrd = work / "vmlinuz", work / "initrd.img"
    for path, dest in (
        ("/live/filesystem.squashfs", image),
        ("/live/vmlinuz", kernel), ("/live/initrd.img", initrd),
    ):
        tool("xorriso", "-osirrox", "on", "-indev", str(iso),
             "-extract", path, str(dest), timeout=80)
        if not dest.is_file() or not dest.stat().st_size:
            raise ValueError("required file missing from verified Synapse image")
    expected_guest = (repo / GUEST_SCRIPT).read_bytes()
    actual_guest = tool("unsquashfs", "-cat", str(image),
                        "usr/local/lib/synapse/evolution-vm-evaluator.py", timeout=80)
    if sha(expected_guest) != sha(actual_guest):
        raise ValueError("live guest evaluator does not match trusted source")
    for path, _ in files:
        relative = str(path).removeprefix("src/")
        from_image = tool("unsquashfs", "-cat", str(image),
                          "usr/lib/synapse/python/" + relative, timeout=80)
        from_repo = (repo / path).read_bytes()
        if sha(from_image) != sha(from_repo):
            raise ValueError("image base Python file differs from exact repo")
    return kernel, initrd


def create_payload(receipt: dict, files: list[tuple[Path, bytes]], work: Path) -> Path:
    folder = work / "seed"
    folder.mkdir()
    out = folder / "files"
    for path, contents in files:
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(contents)
    manifest = {
        "schema": SCHEMA,
        "base_commit": receipt["base_commit"],
        "changes": receipt["changes"],
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8"
    )
    iso = work / "evolution-payload.iso"
    tool("xorriso", "-as", "mkisofs", "-r", "-J", "-V", "SYNAPSE_EVO",
         "-o", str(iso), str(folder), timeout=80)
    if not iso.stat().st_size:
        raise ValueError("bounded read-only candidate ISO not produced")
    return iso


def qemu_args(iso: Path, payload: Path, kernel: Path, initrd: Path,
              role: str, serial: Path) -> list[str]:
    if role not in {"baseline", "candidate"}:
        raise ValueError("unsupported role")
    return [
        "qemu-system-x86_64", "-machine", "q35,accel=tcg", "-cpu", "qemu64",
        "-smp", "2", "-m", "4096",
        "-kernel", str(kernel), "-initrd", str(initrd),
        "-append", (
            "boot=live components live-media=/dev/vda console=ttyS0 "
            "systemd.unit=multi-user.target systemd.show_status=1 "
            f"synapse.evolve_vm=1 synapse.evolve_role={role}"
        ),
        "-drive", f"file={iso},format=raw,if=virtio,readonly=on",
        "-drive", f"file={payload},format=raw,if=ide,media=cdrom,readonly=on",
        "-nic", "none", "-display", "none", "-monitor", "none",
        "-serial", f"file:{serial}", "-no-reboot",
    ]


def vm_trial(args: list[str], serial: Path, err: Path, role: str,
             timeout: int) -> dict:
    with err.open("wb") as errors:
        guest = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=errors,
            start_new_session=True
        )
        try:
            cutoff = time.monotonic() + timeout
            while time.monotonic() < cutoff:
                if serial.is_file():
                    log = serial.read_text(encoding="utf-8", errors="replace")
                    for line in log.splitlines():
                        if "SYNAPSE_EVO_FAIL:" in line:
                            kind = line.split("SYNAPSE_EVO_FAIL:", 1)[1].strip()[:100]
                            raise ValueError(f"{role} guest rejected evaluation: {kind}")
                        if RESULT in line:
                            content = line.split(RESULT, 1)[1].strip()
                            try:
                                receipt = json.loads(content)
                            except ValueError as exc:
                                raise ValueError("unparseable guest result marker") from exc
                            if not isinstance(receipt, dict) or (
                                receipt.get("schema") != "synapse.evolution.vm.guest_result.v1"
                                or receipt.get("role") != role
                                or receipt.get("candidate_files_applied") != (role == "candidate")
                                or receipt.get("production_modified") is not False
                                or receipt.get("network_policy") != "HOST_QEMU_NIC_DISABLED"
                                or set(receipt.get("checks", {})) != {"status", "doctor"}
                                or not all(v.get("passed") for v in receipt["checks"].values())
                            ):
                                raise ValueError("guest acceptance receipt malformed")
                            return receipt
                if guest.poll() is not None:
                    raise ValueError(f"{role} QEMU exited before trusted receipt")
                time.sleep(1)
            raise ValueError(f"{role} QEMU exceeded {timeout}-second budget")
        finally:
            if guest.poll() is None:
                try:
                    os.killpg(guest.pid, signal.SIGTERM)
                    guest.wait(timeout=6)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    os.killpg(guest.pid, signal.SIGKILL)
                    guest.wait(timeout=6)


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo", required=True, type=Path)
    cli.add_argument("--receipt-dir", required=True, type=Path)
    cli.add_argument("--iso", required=True, type=Path)
    cli.add_argument("--iso-sha256", required=True)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--timeout", type=int, default=300)
    args = cli.parse_args(argv)
    if not 60 <= args.timeout <= 540:
        cli.error("QEMU trial timeout must be 60-540 seconds")
    root = args.repo.resolve(strict=True)
    out = args.output.resolve(strict=False)
    if out == root or out.is_relative_to(root):
        cli.error("never create evaluation artifacts inside source repository")
    receipt, files = validate(root, args.receipt_dir.resolve(strict=True))
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="synapse-qemu-evo-", dir=out) as temporary:
        scratch = Path(temporary)
        kernel, initrd = verify_iso(root, args.iso, args.iso_sha256, files, scratch)
        payload = create_payload(receipt, files, scratch)
        result = {
            "schema": "synapse.evolution.vm.comparison.v1",
            "base_commit": receipt["base_commit"],
            "iso_sha256": args.iso_sha256,
            "payload_sha256": sha(payload.read_bytes()),
            "receipt_patch_sha256": receipt["patch_sha256"],
            "networking": "DISABLED_BY_QEMU_-nic_none",
            "qemu_acceleration": "TCG_ONLY",
            "host_secrets_sent": False,
            "candidate_executed_on_host": False,
            "production_modified": False,
            "promotion": "OWNER_REVIEW_REQUIRED",
            "smoke_only_not_performance_proof": True,
        }
        for role in ("baseline", "candidate"):
            serial = out / f"{role}-serial.log"
            err = out / f"{role}-qemu-stderr.log"
            command = qemu_args(args.iso.resolve(strict=True), payload,
                                kernel, initrd, role, serial)
            result[role] = vm_trial(command, serial, err, role, args.timeout)
            if result[role].get("source_commit") != receipt["base_commit"]:
                raise ValueError("guest receipt base identity mismatch")
        (out / "COMPARISON.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("SYNAPSE_EVO_QEMU_PASS: two real disconnected guest boots,"
              " hash-bound source and fixed baseline/candidate smoke checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
