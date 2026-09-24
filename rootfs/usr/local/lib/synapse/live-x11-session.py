#!/usr/bin/env python3
"""Select a supported Plasma X11 session for the temporary Synapse live user.

This is an SDDM ExecStartPre hook, after live-config has generated its own
autologin settings and before the display manager reads those settings.
Never creates an autologin user and never modifies an installed boot.
"""
from __future__ import annotations

import configparser
from pathlib import Path
import re


def patch_autologin(contents: str) -> str:
    """Override only the session in /etc/sddm.conf, preserving other sections."""
    session = "Session=plasmax11.desktop"
    section = re.search(r"(?ms)^\[Autologin\][^\n]*\n(.*?)(?=^\[|\Z)", contents)
    if section:
        body = section.group(1)
        if re.search(r"(?m)^\s*Session\s*=", body):
            new_body = re.sub(r"(?m)^\s*Session\s*=.*$", session, body)
        else:
            new_body = body + ("" if not body or body.endswith("\n") else "\n") + session + "\n"
        return contents[:section.start(1)] + new_body + contents[section.end(1):]
    return contents + ("" if not contents or contents.endswith("\n") else "\n") + "\n[Autologin]\n" + session + "\n"


def main() -> int:
    cmdline = Path("/proc/cmdline").read_text(encoding="utf-8")
    if "boot=live" not in cmdline.split():
        return 0

    required = (
        Path("/usr/share/xsessions/plasmax11.desktop"),
        Path("/usr/bin/startplasma-x11"),
        Path("/usr/bin/kwin_x11"),
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("SYNAPSE_LIVE_GUI:X11 unavailable, no session override: " + ", ".join(missing), flush=True)
        return 0

    config_paths = (
        sorted(Path("/usr/lib/sddm/sddm.conf.d").glob("*.conf"))
        + sorted(Path("/etc/sddm.conf.d").glob("*.conf"))
        + [Path("/etc/sddm.conf")]
    )
    effective = configparser.ConfigParser(interpolation=None, strict=False)
    effective.optionxform = str
    effective.read([str(path) for path in config_paths if path.is_file()], encoding="utf-8")

    # Respect ordinary installed user sessions, administrator choices and the
    # default SDDM login screen. This only changes an EXISTING live user.
    if effective.get("Autologin", "User", fallback="") != "cory":
        print("SYNAPSE_LIVE_GUI:no generated cory autologin; leaving login untouched", flush=True)
        return 0

    target = Path("/etc/sddm.conf")
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    updated = patch_autologin(original)
    if updated != original:
        target.write_text(updated, encoding="utf-8")
    print("SYNAPSE_LIVE_GUI:selected Plasma X11 for existing live user", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
