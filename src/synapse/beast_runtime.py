"""Opt-in, hash-verified Beast runtime in a user's private virtual environment."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

RELEASE_VERSION = "0.4.0"
RELEASE_WHEEL = "cosmos_beast_box-0.4.0-py3-none-any.whl"
RELEASE_URL = "https://github.com/NavisWORLD/The-beast-box-/releases/download/v0.4.0/" + RELEASE_WHEEL
RELEASE_SHA256 = "e0c2e5f55d594bfdfc0ba1d74ab9d9fd18f683cc0fb153aec3730b2ae428fdd3"


def user_base():
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    if not base.is_absolute():
        raise ValueError("XDG_DATA_HOME must be absolute")
    return base / "synapse-beast"


def install(args, base):
    chosen_python = getattr(args, "python", sys.executable)
    version = subprocess.check_output([chosen_python, "-I", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], text=True).strip()
    if version not in ("3.10", "3.11", "3.12"):
        raise ValueError("Beast requires Python 3.10–3.12; pass --python /path/to/python3.12")
    if any(p.is_symlink() for p in (base, base / "environments", base / "active")):
        raise ValueError("Installation paths must not be symlinks")
    if args.wheel and not args.sha256:
        raise ValueError("--wheel requires --sha256")
    if args.sha256 and not args.wheel:
        raise ValueError("--sha256 requires --wheel; published release hash is pinned")
    expected = args.sha256 or RELEASE_SHA256
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("--sha256 must contain 64 hexadecimal characters")
    # Copy first, verify the exact bytes pip will consume; never install from a
    # mutable caller path after hashing it. No pip index or dependency resolution.
    with tempfile.TemporaryDirectory(prefix="synapse-beast-download-") as temp:
        wheel = Path(temp) / (Path(args.wheel).name if args.wheel else RELEASE_WHEEL)
        if args.wheel:
            wheel.write_bytes(Path(args.wheel).read_bytes())
        else:
            with urllib.request.urlopen(RELEASE_URL, timeout=60) as response:
                wheel.write_bytes(response.read())
        actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if actual != expected.lower():
            raise ValueError("SHA-256 mismatch; nothing installed")
        target = base / "environments" / actual
        if target.is_symlink():
            raise ValueError("Installation paths must not be symlinks")
        marker = target / ".installed"
        if not marker.exists():
            # Incomplete environments are never selected by the launcher.
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            subprocess.run([chosen_python, "-I", "-m", "venv", "--clear", str(target)], check=True)
            subprocess.run([str(target / "bin/python"), "-I", "-m", "pip", "install",
                            "--no-index", "--no-deps", "--disable-pip-version-check", str(wheel)],
                           check=True, stdout=sys.stderr)
            marker.write_text(actual + "\n")
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(mode="w", dir=base, delete=False) as selection:
            selection.write(actual + "\n")
        os.replace(selection.name, base / "active")
    print(f"Beast runtime installed: {target}")


def run(args, base):
    if any(arg == "--data-dir" or arg.startswith("--data-dir=") for arg in args.arguments):
        raise ValueError("--data-dir is managed by synapse-beast")
    try:
        digest = (base / "active").read_text().strip()
    except FileNotFoundError:
        raise ValueError("Run synapse-beast install first") from None
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid active installation record")
    target = base / "environments" / digest
    if not (target / ".installed").is_file():
        raise ValueError("Incomplete installation; run synapse-beast install")
    data = base / "runtime"
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Isolated mode prevents the checkout or PYTHONPATH shadowing the wheel.
    return subprocess.run([str(target / "bin/python"), "-I", "-m", "beastbox", "runtime",
                           args.action, *args.arguments, "--data-dir", str(data)]).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    installer = commands.add_parser("install", help="install the pinned release for this user")
    installer.add_argument("--wheel", help="offline wheel (requires independently verified SHA-256)")
    installer.add_argument("--sha256")
    installer.add_argument("--python", default=sys.executable, help="supported Python executable (3.10–3.12)")
    launcher = commands.add_parser("run", help="run with persistent per-user state")
    launcher.add_argument("action", choices=["init", "chat", "inspect"])
    launcher.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise ValueError("Run as a normal user, without sudo or root")
        os.umask(0o077)
        base = user_base()
        if args.command == "install":
            install(args, base)
            return 0
        return run(args, base)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"synapse-beast: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
