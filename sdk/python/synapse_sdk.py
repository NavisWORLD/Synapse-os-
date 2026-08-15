"""Zero-dependency Synapse OS SDK with optional native ABI acceleration."""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
from pathlib import Path
import socket
from typing import Optional

STATUS_PATH = Path("/run/synapse/status.json")


def _load_native() -> Optional[ctypes.CDLL]:
    candidates = []
    explicit = os.environ.get("SYNAPSE_ABI_LIBRARY")
    if explicit:
        candidates.append(explicit)
    found = ctypes.util.find_library("synapse_abi")
    if found:
        candidates.append(found)
    candidates.extend(["libsynapse_abi.so", "libsynapse_abi.dylib", "synapse_abi.dll"])
    for candidate in candidates:
        try:
            lib = ctypes.CDLL(candidate)
            lib.synapse_abi_version.argtypes = []
            lib.synapse_abi_version.restype = ctypes.c_uint32
            lib.synapse_status_read.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
            lib.synapse_status_read.restype = ctypes.c_int
            lib.synapse_service_reachable.argtypes = [ctypes.c_char_p, ctypes.c_uint16, ctypes.c_uint32]
            lib.synapse_service_reachable.restype = ctypes.c_int
            return lib
        except OSError:
            continue
    return None


_NATIVE = _load_native()


def abi_version() -> int:
    return int(_NATIVE.synapse_abi_version()) if _NATIVE is not None else 0


def _native_status(path: Path) -> str:
    assert _NATIVE is not None
    encoded = os.fsencode(path)
    needed = ctypes.c_size_t(0)
    rc = _NATIVE.synapse_status_read(encoded, None, 0, ctypes.byref(needed))
    if rc != 0:
        raise OSError(f"synapse ABI status read failed with code {rc}")
    buffer = ctypes.create_string_buffer(needed.value)
    rc = _NATIVE.synapse_status_read(encoded, buffer, len(buffer), ctypes.byref(needed))
    if rc != 0:
        raise OSError(f"synapse ABI status read failed with code {rc}")
    return buffer.value.decode("utf-8")


def status(path: str | Path = STATUS_PATH) -> dict:
    target = Path(path)
    text = _native_status(target) if _NATIVE is not None else target.read_text(encoding="utf-8")
    return json.loads(text)


def service_reachable(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    if not 1 <= int(port) <= 65535:
        return False
    if _NATIVE is not None:
        ms = max(0, min(int(timeout * 1000), 0xFFFFFFFF))
        return _NATIVE.synapse_service_reachable(host.encode("utf-8"), int(port), ms) == 1
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
