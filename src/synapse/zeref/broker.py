from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .receipt import validate_receipt

DEFAULT_CONFIG = Path("/etc/synapse/zeref-ibm.json")


@dataclass(frozen=True)
class BrokerConfig:
    job_id: str
    backend: str
    shots: int
    circuit_sha256: str
    receipt_path: str = "/var/lib/synapse/zeref/ibm/latest.json"
    instance: str | None = None
    ttl_seconds: int = 24 * 60 * 60

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> "BrokerConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("IBM broker config must be a JSON object")
        allowed = set(cls.__dataclass_fields__)
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError("unknown IBM broker config keys: " + ", ".join(unknown))
        return cls(**raw)


def _read_credential(path: str | Path) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("IBM credential file is empty")
    return value


def _atomic_json(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".ibm-receipt-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, target)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def refresh_ibm_receipt(config: BrokerConfig, *, credential_file: str | Path) -> dict[str, Any]:
    token = _read_credential(credential_file)
    try:
        from beastbox.quantum_divergence.resident_broker import refresh_existing_job
    except ImportError as exc:
        raise RuntimeError("Beast Box quantum broker support is not installed") from exc

    receipt = refresh_existing_job(
        token=token,
        job_id=config.job_id,
        backend=config.backend,
        shots=int(config.shots),
        circuit_sha256=config.circuit_sha256,
        instance=config.instance,
        ttl_seconds=int(config.ttl_seconds),
    )
    clean = validate_receipt(receipt)
    clean.pop("fresh", None)
    _atomic_json(config.receipt_path, clean)
    return validate_receipt(clean)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse-zeref-ibm-broker")
    parser.add_argument("command", choices=["refresh", "status"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--credential-file")
    args = parser.parse_args(argv)
    config = BrokerConfig.load(args.config)
    if args.command == "status":
        from .receipt import load_receipt

        receipt = load_receipt(config.receipt_path)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    if not args.credential_file:
        parser.error("refresh requires --credential-file")
    receipt = refresh_ibm_receipt(config, credential_file=args.credential_file)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
