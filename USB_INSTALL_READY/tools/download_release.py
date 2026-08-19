#!/usr/bin/env python3
"""Download the latest verified Synapse OS USB installer release assets."""

from __future__ import annotations

import json
from pathlib import Path
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com/repos/NavisWORLD/Synapse-os-/releases/latest"
PART_PREFIX = "SynapseOS-Nebula-amd64.iso.part-"
REQUIRED = {
    "SynapseOS-Nebula-amd64.iso.sha256",
    "SynapseOS-Nebula-amd64.iso.parts.sha256",
    "reassemble-usb-installer.ps1",
    "reassemble-usb-installer.sh",
}


def select_installer_assets(assets: list[dict]) -> list[dict]:
    selected = []
    found = set()
    part_count = 0
    for asset in assets:
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        if name.startswith(PART_PREFIX):
            selected.append(asset)
            part_count += 1
        elif name in REQUIRED:
            selected.append(asset)
            found.add(name)
    missing = REQUIRED - found
    if part_count == 0 or missing:
        detail = []
        if part_count == 0:
            detail.append("no ISO part files")
        if missing:
            detail.append("missing " + ", ".join(sorted(missing)))
        raise ValueError("Latest release is incomplete: " + "; ".join(detail))
    return sorted(selected, key=lambda a: str(a["name"]))


def request_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SynapseOS-USB-Installer",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, destination: Path) -> None:
    tmp = destination.with_suffix(destination.suffix + ".download")
    req = urllib.request.Request(url, headers={"User-Agent": "SynapseOS-USB-Installer"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response, open(tmp, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if total:
                    pct = done * 100.0 / total
                    print(f"\r  {destination.name}: {pct:6.2f}%", end="", flush=True)
        os.replace(tmp, destination)
        print(f"\r  {destination.name}: complete{' ' * 20}")
    except Exception:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    print("Synapse OS installer downloader")
    print("Fetching latest GitHub release metadata...")
    try:
        release = request_json(API)
        assets = select_installer_assets(release.get("assets") or [])
        print(f"Release: {release.get('tag_name', 'unknown')}")
        for asset in assets:
            destination = base / asset["name"]
            if destination.exists() and destination.stat().st_size == int(asset.get("size") or -1):
                print(f"  {destination.name}: already present")
                continue
            download(asset["browser_download_url"], destination)
        print("\nInstaller release files are ready beside this script's parent folder.")
        return 0
    except urllib.error.HTTPError as exc:
        print(f"GitHub returned HTTP {exc.code}. If the repository is private or rate-limited, download the release assets manually.", file=sys.stderr)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
