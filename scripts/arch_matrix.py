#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "build" / "architectures.json"
REQUIRED_FIELDS = {
    "aliases", "kernel_package", "qemu_system", "qemu_machine", "qemu_cpu",
    "serial_console", "qemu_static", "bootstrap_qemu_arch", "binary_image", "support_state"
}


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("architectures"), dict):
        raise ValueError("invalid architecture registry schema")
    for name, profile in data["architectures"].items():
        missing = REQUIRED_FIELDS.difference(profile)
        if missing:
            raise ValueError(f"architecture {name} missing fields: {', '.join(sorted(missing))}")
        if name not in profile["aliases"]:
            raise ValueError(f"architecture {name} must list itself as an alias")
    return data


def normalize_arch(value: str, registry: dict[str, Any] | None = None) -> str:
    reg = registry or load_registry()
    wanted = value.strip().lower()
    for name, profile in reg["architectures"].items():
        if wanted == name or wanted in [str(x).lower() for x in profile["aliases"]]:
            return name
    raise ValueError(f"unsupported architecture: {value}")


def profile_for_arch(value: str, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = registry or load_registry()
    name = normalize_arch(value, reg)
    return {"name": name, **reg["architectures"][name]}


def shell_exports(profile: dict[str, Any]) -> str:
    mapping = {
        "SYNAPSE_ARCH_NORMALIZED": profile["name"],
        "SYNAPSE_KERNEL_PACKAGE": profile["kernel_package"],
        "SYNAPSE_QEMU_SYSTEM": profile["qemu_system"],
        "SYNAPSE_QEMU_MACHINE": profile["qemu_machine"],
        "SYNAPSE_QEMU_CPU": profile["qemu_cpu"],
        "SYNAPSE_SERIAL_CONSOLE": profile["serial_console"],
        "SYNAPSE_QEMU_STATIC": profile["qemu_static"] or "",
        "SYNAPSE_BOOTSTRAP_QEMU_ARCH": profile["bootstrap_qemu_arch"],
        "SYNAPSE_BINARY_IMAGE": profile["binary_image"],
        "SYNAPSE_SUPPORT_STATE": profile["support_state"],
    }
    return "\n".join(f"export {key}={shlex.quote(str(value))}" for key, value in mapping.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    shell = sub.add_parser("shell")
    shell.add_argument("arch")
    shell.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    norm = sub.add_parser("normalize")
    norm.add_argument("arch")
    norm.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    js = sub.add_parser("json")
    js.add_argument("arch")
    js.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    try:
        reg = load_registry(args.registry)
        if args.command == "validate":
            for name in reg["architectures"]:
                profile_for_arch(name, reg)
            print("architecture registry: ok")
        elif args.command == "shell":
            print(shell_exports(profile_for_arch(args.arch, reg)))
        elif args.command == "normalize":
            print(normalize_arch(args.arch, reg))
        else:
            print(json.dumps(profile_for_arch(args.arch, reg), sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
