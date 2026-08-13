from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import time

from .core import system_status

RUN = True


def _stop(*_: object) -> None:
    global RUN
    RUN = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synapse OS telemetry agent")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--output", default="/run/synapse/status.json")
    args = parser.parse_args(argv)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    while RUN:
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(system_status(), separators=(",", ":")))
        tmp.replace(out)
        time.sleep(max(0.5, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
