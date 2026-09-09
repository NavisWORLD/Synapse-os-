from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
from typing import Protocol
from .authority import AuthorityLedger


@dataclass(frozen=True)
class MachineSpec:
    memory_mb: int = 2048
    cpus: int = 2
    network_mode: str = "none"

    def __post_init__(self) -> None:
        if not (256 <= self.memory_mb <= 16384):
            raise ValueError("memory_mb outside safe range")
        if not (1 <= self.cpus <= 8):
            raise ValueError("cpus outside safe range")
        if self.network_mode not in {"none", "user"}:
            raise ValueError("network mode must be none or user")


class VMBackend(Protocol):
    def create(self, spec: MachineSpec) -> dict: ...
    def destroy(self) -> dict: ...


class InMemoryVMBackend:
    def __init__(self) -> None:
        self.running = False

    def create(self, spec: MachineSpec) -> dict:
        if self.running:
            raise RuntimeError("VM already running")
        self.running = True
        return {"state": "RUNNING", "engine": "test-double", "memory_mb": spec.memory_mb, "cpus": spec.cpus, "network_mode": spec.network_mode}

    def destroy(self) -> dict:
        self.running = False
        return {"state": "DESTROYED", "engine": "test-double"}


class QemuVMBackend:
    """Fixed-purpose disposable QEMU backend. No arbitrary command surface is exposed."""

    def __init__(self, *, image: Path, image_sha256: str, qemu_binary: str = "qemu-system-x86_64") -> None:
        self.image = image.resolve()
        self.image_sha256 = image_sha256.lower().strip()
        self.qemu_binary = qemu_binary
        self.process: subprocess.Popen[bytes] | None = None

    def _verify(self) -> None:
        if not self.image.is_file():
            raise FileNotFoundError(self.image)
        digest = sha256(self.image.read_bytes()).hexdigest()
        if digest != self.image_sha256:
            raise ValueError("VM image SHA-256 mismatch")
        if not shutil.which(self.qemu_binary):
            raise FileNotFoundError(self.qemu_binary)

    def command(self, spec: MachineSpec) -> list[str]:
        nic = ["-nic", "none"] if spec.network_mode == "none" else ["-nic", "user,model=virtio-net-pci"]
        return [
            self.qemu_binary,
            "-snapshot",
            "-display",
            "none",
            "-serial",
            "none",
            "-monitor",
            "none",
            "-no-reboot",
            "-m",
            str(spec.memory_mb),
            "-smp",
            str(spec.cpus),
            "-drive",
            f"file={self.image},if=virtio",
            *nic,
        ]

    def create(self, spec: MachineSpec) -> dict:
        if self.process and self.process.poll() is None:
            raise RuntimeError("VM already running")
        self._verify()
        self.process = subprocess.Popen(
            self.command(spec),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "state": "RUNNING",
            "engine": "qemu",
            "pid": self.process.pid,
            "memory_mb": spec.memory_mb,
            "cpus": spec.cpus,
            "network_mode": spec.network_mode,
        }

    def destroy(self) -> dict:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
        return {"state": "DESTROYED", "engine": "qemu"}


class VMController:
    def __init__(self, backend: VMBackend, authority: AuthorityLedger) -> None:
        self.backend = backend
        self.authority = authority
        self.state = "STOPPED"

    def create(self, spec: MachineSpec) -> dict:
        if not self.authority.allowed("vm.control"):
            raise PermissionError("vm.control authority required")
        receipt = self.backend.create(spec)
        self.state = str(receipt.get("state", "RUNNING"))
        return receipt

    def destroy(self) -> dict:
        receipt = self.backend.destroy()
        self.state = str(receipt.get("state", "DESTROYED"))
        self.authority.revoke("vm.control")
        return receipt
