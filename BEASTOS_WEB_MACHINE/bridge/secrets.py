from __future__ import annotations
import json
import re
from typing import Any

_PATTERNS = [
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)\b((?:openai_api_key|api[_-]?key|password|secret|token)\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"\b(sk-[A-Za-z0-9._-]{4,})\b"),
]


def redact_secrets(text: str) -> str:
    out = str(text)
    for pattern in _PATTERNS:
        if pattern.groups == 2:
            out = pattern.sub(lambda m: m.group(1) + "[REDACTED]", out)
        else:
            out = pattern.sub("[REDACTED]", out)
    return out


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if any(word in str(key).lower() for word in ("password", "secret", "token", "authorization", "api_key", "apikey")):
                clean[key] = "[REDACTED]"
            else:
                clean[key] = redact_value(item)
        return clean
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value


def redacted_json(value: Any) -> str:
    return json.dumps(redact_value(value), sort_keys=True, separators=(",", ":"))
