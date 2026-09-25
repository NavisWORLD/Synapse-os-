#!/usr/bin/env python3
"""Brand the already-rendered Debian live-build GRUB menu as Synapse OS.

This intentionally operates on live-build's *generated* grub.cfg so kernel,
initrd, loopback, checksum, and failsafe parameters stay owned by live-build.
Only human-facing labels are changed. The failsafe entry is the existing
GENESIS-gated boot path supplied by --bootappend-live-failsafe.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

LIVE_LABEL = "SYNAPSE OS // NEBULA // LIVE"
GENESIS_LABEL = "SYNAPSE OS // GENESIS // GATED INSTALLER"
ADVANCED_LABEL = "SYNAPSE // ADVANCED"

MENU_RE = re.compile(r'^(?P<indent>\s*)menuentry\s+"(?P<label>[^"]+)"(?P<rest>.*)$')
SUBMENU_RE = re.compile(r"^(?P<indent>\s*)submenu\s+['\"]Utilities\.\.\.['\"](?P<rest>.*)$")


def brand(contents: str) -> str:
    lines = contents.splitlines()
    live_done = False
    genesis_done = False
    advanced_done = False
    out: list[str] = []

    for line in lines:
        match = MENU_RE.match(line)
        if match:
            label = match.group("label")
            indent = match.group("indent")
            rest = match.group("rest")
            lower = label.lower()
            if not genesis_done and "live system" in lower and "fail-safe" in lower:
                # The failsafe entry already carries SYNAPSE_GENESIS bootappend.
                rest = re.sub(r"\s+--hotkey=\S+", "", rest)
                line = f'{indent}menuentry "{GENESIS_LABEL}" --hotkey=g{rest}'
                genesis_done = True
            elif not live_done and "live system" in lower and "fail-safe" not in lower:
                rest = re.sub(r"\s+--hotkey=\S+", "", rest)
                line = f'{indent}menuentry "{LIVE_LABEL}" --hotkey=s{rest}'
                live_done = True

        submenu = SUBMENU_RE.match(line)
        if submenu and not advanced_done:
            line = f'{submenu.group("indent")}submenu "{ADVANCED_LABEL}"{submenu.group("rest")}'
            advanced_done = True

        out.append(line)

    if not live_done:
        raise ValueError("generated GRUB config contains no normal live-system entry")
    if not genesis_done:
        raise ValueError("generated GRUB config contains no fail-safe/GENESIS entry")

    branded = "\n".join(out) + "\n"
    if "Debian GNU/Linux" in branded:
        # A Debian reference in comments or unrelated labels would recreate the
        # stock first impression. Fail closed so CI shows us the exact drift.
        raise ValueError("generated GRUB config still contains Debian branding")
    return branded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    rendered = brand(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
