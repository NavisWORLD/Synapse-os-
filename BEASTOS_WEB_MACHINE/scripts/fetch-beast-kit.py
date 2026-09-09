#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from BEASTOS_WEB_MACHINE.bridge.kit import materialize_kit  # noqa: E402

DEFAULT_MANIFEST = ROOT / "BEASTOS_WEB_MACHINE/manifests/beast-v0.6.0.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch or reuse the pinned Beast Box release kit and verify its exact SHA-256 before use."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--source-file",
        type=Path,
        help="optional already-downloaded kit for offline builds; it is verified against the same manifest",
    )
    parser.add_argument("--extract-to", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = materialize_kit(
            args.manifest,
            args.destination,
            source_file=args.source_file,
            extract_to=args.extract_to,
        )
    except (OSError, ValueError) as exc:
        print(f"fetch-beast-kit: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
