from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any

COSMOS_PORTS = {
    "ollama": 11434,
    "helper": 11435,
    "native_bridge": 11501,
    "sensory_api": 8765,
    "web": 8081,
    "web_fallback": 8090,
}

PROFILE_MAP = {
    "pulse": "performance",
    "balanced": "balanced",
    "quiet": "power-saver",
}


def _read(path: str | Path, default: str = "") -> str:
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return default


def _run(args: list[str], timeout: float = 2.0) -> tuple[int, str]:
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
        out = (p.stdout or p.stderr).strip()
        return p.returncode, out
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def cpu_model() -> str:
    for line in _read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name") and ":" in line:
            return line.split(":", 1)[1].strip()
    return os.uname().machine


def memory_status() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in _read("/proc/meminfo").splitlines():
        parts = line.replace(":", "").split()
        if len(parts) >= 2 and parts[1].isdigit():
            values[parts[0]] = int(parts[1]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return {"total_bytes": total, "available_bytes": available, "used_bytes": max(0, total - available)}


def battery_status() -> dict[str, Any]:
    roots = sorted(Path("/sys/class/power_supply").glob("BAT*"))
    if not roots:
        return {"present": False}
    bat = roots[0]
    capacity = _read(bat / "capacity")
    status = _read(bat / "status")
    try:
        pct = int(capacity)
    except ValueError:
        pct = None
    return {"present": True, "percent": pct, "status": status or "unknown"}


def on_ac_power() -> bool | None:
    for pattern in ("AC*", "ADP*", "Mains*"):
        for p in Path("/sys/class/power_supply").glob(pattern):
            online = _read(p / "online")
            if online in {"0", "1"}:
                return online == "1"
    bat = battery_status()
    if bat.get("present"):
        return str(bat.get("status", "")).lower() in {"charging", "full"}
    return None


def current_power_profile() -> str:
    if not shutil.which("powerprofilesctl"):
        return "unsupported"
    rc, out = _run(["powerprofilesctl", "get"])
    return out if rc == 0 and out else "unknown"


def set_profile(profile: str) -> dict[str, Any]:
    profile = profile.lower()
    requested = profile
    if profile == "auto":
        ac = on_ac_power()
        profile = "balanced" if ac is not False else "quiet"
    if profile not in PROFILE_MAP:
        raise ValueError(f"unknown profile: {requested}")
    target = PROFILE_MAP[profile]
    if not shutil.which("powerprofilesctl"):
        return {"ok": False, "requested": requested, "resolved": profile, "target": target, "reason": "powerprofilesctl unavailable"}
    rc, out = _run(["powerprofilesctl", "set", target], timeout=5.0)
    return {"ok": rc == 0, "requested": requested, "resolved": profile, "target": target, "detail": out}


def zram_status() -> dict[str, Any]:
    devices = []
    for dev in sorted(Path("/sys/block").glob("zram*")):
        disksize = _read(dev / "disksize", "0")
        comp = _read(dev / "comp_algorithm")
        devices.append({"device": dev.name, "disksize": int(disksize or 0), "compression": comp})
    return {"enabled": bool(devices), "devices": devices}


def probe_port(port: int, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def cosmos_probe() -> dict[str, dict[str, Any]]:
    return {name: {"port": port, "reachable": probe_port(port)} for name, port in COSMOS_PORTS.items()}


def zeref_probe() -> dict[str, Any]:
    sock = Path("/run/synapse/zeref/zeref.sock")
    reachable = sock.is_socket()
    return {
        "state": "DEGRADED" if reachable else "OFFLINE",
        "socket_reachable": reachable,
        "service_unit_present": Path("/etc/systemd/system/synapse-zeref.service").is_file(),
        "config_present": Path("/etc/synapse/zeref.json").is_file(),
        "credential_exposed_to_subject": False,
    }


def temperature_c() -> float | None:
    candidates = sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    values = []
    for p in candidates:
        raw = _read(p)
        try:
            v = float(raw)
            if v > 1000:
                v /= 1000.0
            if 0 < v < 150:
                values.append(v)
        except ValueError:
            pass
    return max(values) if values else None


def system_status() -> dict[str, Any]:
    try:
        load = os.getloadavg()
    except OSError:
        load = (0.0, 0.0, 0.0)
    return {
        "synapse_version": "0.1.0-alpha.1",
        "hostname": socket.gethostname(),
        "kernel": os.uname().release,
        "machine": os.uname().machine,
        "cpu": cpu_model(),
        "cpu_count": os.cpu_count(),
        "load_1m": load[0],
        "memory": memory_status(),
        "battery": battery_status(),
        "ac_power": on_ac_power(),
        "power_profile": current_power_profile(),
        "zram": zram_status(),
        "temperature_c": temperature_c(),
        "cosmos": cosmos_probe(),
        "timestamp": int(time.time()),
    }


def doctor() -> dict[str, Any]:
    commands = ["systemctl", "powerprofilesctl", "python3", "git", "curl", "ip", "nmcli"]
    return {
        "commands": {name: bool(shutil.which(name)) for name in commands},
        "os_release": _read("/etc/os-release"),
        "cosmos": cosmos_probe(),
        "zeref": zeref_probe(),
        "status": system_status(),
    }


def benchmark(size_mb: int = 32) -> dict[str, Any]:
    block = b"synapse-os-nebula" * 4096
    rounds = max(1, (size_mb * 1024 * 1024) // len(block))
    start = time.perf_counter()
    h = hashlib.sha256()
    for _ in range(rounds):
        h.update(block)
    elapsed = max(time.perf_counter() - start, 1e-9)
    hashed = len(block) * rounds

    payload = os.urandom(1024 * 1024)
    write_rounds = max(8, size_mb)
    with tempfile.NamedTemporaryFile(prefix="synapse-bench-", delete=True) as f:
        start_w = time.perf_counter()
        for _ in range(write_rounds):
            f.write(payload)
        f.flush()
        os.fsync(f.fileno())
        write_elapsed = max(time.perf_counter() - start_w, 1e-9)
    written = len(payload) * write_rounds
    return {
        "sha256_mib_s": round((hashed / 1048576) / elapsed, 2),
        "temp_write_mib_s": round((written / 1048576) / write_elapsed, 2),
        "digest": h.hexdigest()[:16],
        "note": "microbenchmark only; compare runs on the same hardware",
    }


def dump_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)