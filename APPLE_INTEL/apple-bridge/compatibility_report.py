from __future__ import annotations

import json
import os
import plistlib
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from inspect_macho import inspect_macho


def resolve_bundle_executable(app_path: str | Path) -> Path:
    app = Path(app_path)
    info = app / "Contents" / "Info.plist"
    if not app.is_dir() or app.suffix.lower() != ".app":
        raise ValueError("path is not a .app bundle directory")
    try:
        payload = plistlib.loads(info.read_bytes())
    except (OSError, plistlib.InvalidFileException) as exc:
        raise ValueError(f"invalid or missing Info.plist: {exc}") from exc
    name = payload.get("CFBundleExecutable")
    if not isinstance(name, str) or not name or "/" in name or "\\" in name:
        raise ValueError("CFBundleExecutable is missing or unsafe")
    exe = app / "Contents" / "MacOS" / name
    if not exe.is_file():
        raise ValueError("bundle executable does not exist")
    return exe


def _native_kind(path: Path) -> str | None:
    try:
        head = path.read_bytes()[:4]
    except OSError:
        return None
    if head.startswith(b"#!"):
        return "script"
    if head == b"\x7fELF":
        return "elf"
    return None


def compatibility_report(app_path: str | Path, available_dependencies: Iterable[str] | None = None) -> dict[str, Any]:
    app = Path(app_path)
    try:
        exe = resolve_bundle_executable(app)
    except ValueError as exc:
        return {"bundle_path": str(app), "executable_path": None, "architecture": "unknown", "macho_valid": False, "dependency_count": 0, "recognized_dependencies": [], "missing_dependencies": [], "classification": "unsupported", "reasons": [str(exc)]}

    native = _native_kind(exe)
    if native:
        return {"bundle_path": str(app), "executable_path": str(exe), "architecture": "native", "macho_valid": False, "dependency_count": 0, "recognized_dependencies": [], "missing_dependencies": [], "classification": "native-tool", "reasons": [f"bundle executable is a local {native} tool, not Mach-O"]}

    macho = inspect_macho(exe)
    deps = list(macho.get("dependencies") or [])
    available = set(available_dependencies or [])
    recognized = [d for d in deps if d in available]
    missing = [d for d in deps if d not in available]
    reasons: list[str] = []
    if not macho.get("valid"):
        classification = "unsupported"
        reasons.append(str(macho.get("reason") or "invalid Mach-O"))
    elif macho.get("architecture") != "x86_64":
        classification = "unsupported"
        reasons.append(f"architecture {macho.get('architecture')} is outside this Intel target")
    elif missing:
        classification = "unsupported"
        reasons.append("required Mach-O dependencies are not provided by the local compatibility environment")
    else:
        classification = "experimental"
        reasons.append("x86_64 Mach-O structure is inspectable; execution compatibility is not guaranteed")
    return {
        "bundle_path": str(app),
        "executable_path": str(exe),
        "architecture": macho.get("architecture", "unknown"),
        "macho_valid": bool(macho.get("valid")),
        "dependency_count": len(deps),
        "recognized_dependencies": recognized,
        "missing_dependencies": missing,
        "classification": classification,
        "reasons": reasons,
        "macho": macho,
    }


def _available_from_env() -> set[str]:
    path = os.environ.get("SYNAPSE_APPLE_BRIDGE_CAPABILITIES", "")
    if not path:
        return set()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    deps = payload.get("available_dependencies", []) if isinstance(payload, dict) else []
    return {str(x) for x in deps}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Classify a macOS .app bundle without executing it")
    parser.add_argument("app")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = compatibility_report(args.app, _available_from_env())
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["classification"] != "unsupported" else 2


if __name__ == "__main__":
    raise SystemExit(main())
