from __future__ import annotations

import argparse
import sys

from . import __version__
from .core import benchmark, cosmos_probe, doctor, dump_json, current_power_profile, set_profile, system_status
from .dsl import apply as apply_plan, parse_file


def _human_status(data: dict) -> str:
    mem = data["memory"]
    total_gib = mem["total_bytes"] / 1073741824 if mem["total_bytes"] else 0
    used_gib = mem["used_bytes"] / 1073741824 if mem["used_bytes"] else 0
    reachable = [name for name, item in data["cosmos"].items() if item["reachable"]]
    lines = [
        f"Synapse OS {data['synapse_version']}",
        f"Host: {data['hostname']} | Kernel: {data['kernel']} | {data['machine']}",
        f"CPU: {data['cpu']} ({data['cpu_count']} logical cores)",
        f"Memory: {used_gib:.1f}/{total_gib:.1f} GiB | Load: {data['load_1m']:.2f}",
        f"Power: {data['power_profile']} | AC: {data['ac_power']} | Battery: {data['battery']}",
        f"zram: {'on' if data['zram']['enabled'] else 'off'} | Temp: {data['temperature_c']}",
        f"COSMOS reachable: {', '.join(reachable) if reachable else 'none'}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="synapse", description="Synapse OS control plane")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--json", action="store_true", dest="as_json")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("doctor")
    sub.add_parser("bench")
    profile = sub.add_parser("profile")
    psub = profile.add_subparsers(dest="profile_command", required=True)
    psub.add_parser("get")
    pset = psub.add_parser("set")
    pset.add_argument("name", choices=["pulse", "balanced", "quiet", "auto"])
    cosmos = sub.add_parser("cosmos")
    csub = cosmos.add_subparsers(dest="cosmos_command", required=True)
    csub.add_parser("probe")
    plan = sub.add_parser("apply")
    plan.add_argument("path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            data = system_status()
            print(dump_json(data) if args.as_json else _human_status(data))
        elif args.command == "doctor":
            print(dump_json(doctor()))
        elif args.command == "bench":
            print(dump_json(benchmark()))
        elif args.command == "profile":
            if args.profile_command == "get":
                data = {"profile": current_power_profile()}
            else:
                data = set_profile(args.name)
            print(dump_json(data))
            if isinstance(data, dict) and data.get("ok") is False:
                return 2
        elif args.command == "cosmos":
            print(dump_json(cosmos_probe()))
        elif args.command == "apply":
            print(dump_json(apply_plan(parse_file(args.path))))
        return 0
    except (ValueError, OSError) as exc:
        print(f"synapse: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
