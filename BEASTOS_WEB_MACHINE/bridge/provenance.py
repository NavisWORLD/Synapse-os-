from __future__ import annotations
from hashlib import sha256
import json
from time import time
from typing import Any
from .secrets import redact_value


class ProvenanceLog:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def append(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        previous = self._records[-1]["hash"] if self._records else "0" * 64
        record = {
            "event": str(event),
            "data": redact_value(data),
            "at": time(),
            "previous_hash": previous,
        }
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        record["hash"] = sha256(canonical).hexdigest()
        self._records.append(record)
        return dict(record)

    def records(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._records]
