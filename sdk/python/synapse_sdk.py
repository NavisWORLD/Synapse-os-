"""Tiny zero-dependency Synapse OS SDK."""
from __future__ import annotations
import json
from pathlib import Path
import socket

STATUS_PATH = Path("/run/synapse/status.json")


def status() -> dict:
    return json.loads(STATUS_PATH.read_text())


def service_reachable(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
