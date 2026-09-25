#!/usr/bin/env python3
"""Trusted stage-2 guest harness, opt-in in a disposable network-free Synapse VM.

The only model-supplied material is a read-only, hash-bound set of source files.
This is not a hardened proof of arbitrary-code safety: QEMU/kernel trust still
matters, and passing fixed smoke checks does not prove a proposed patch correct.
"""
from __future__ import annotations

import compileall
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

SOURCE = Path("/usr/lib/synapse/python/synapse")
SCRATCH = Path("/run/synapse-evolution-eval")
MOUNT = SCRATCH / "payload"
PROTOCOL = "synapse.evolution.vm.payload.v1"
MARKER = "SYNAPSE_EVO_RESULT:"
ALLOWED = re.compile(r"src/synapse/[A-Za-z][A-Za-z0-9_]{0,65}\.py\Z")
PROTECTED = {"evolution.py", "evolution_model.py", "cli.py", "agent.py", "__init__.py"}
SHA = re.compile(r"[a-f0-9]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def report(message: str) -> None:
    # Only this trusted root-owned harness writes receipts; untrusted candidate
    # stdout/stderr is captured, discarded and never treated as a pass marker.
    print(message, flush=True)


def fail(kind: str) -> None:
    report("SYNAPSE_EVO_FAIL:" + kind)
    raise SystemExit(2)


def role() -> str:
    args = Path("/proc/cmdline").read_text(encoding="utf-8").split()
    if "synapse.evolve_vm=1" not in args or "boot=live" not in args:
        fail("NOT_DISPOSABLE_EVALUATION_BOOT")
    found = [arg.partition("=")[2] for arg in args
             if arg.startswith("synapse.evolve_role=")]
    if len(found) != 1 or found[0] not in {"baseline", "candidate"}:
        fail("INVALID_ROLE")
    if not Path("/run/live/medium").is_dir():
        fail("NOT_LIVE_MEDIA")
    return found[0]


def mount_payload() -> Path:
    SCRATCH.mkdir(mode=0o755, parents=True, exist_ok=True)
    MOUNT.mkdir(mode=0o755, exist_ok=True)
    device = Path("/dev/disk/by-label/SYNAPSE_EVO")
    for _ in range(14):
        if device.exists():
            break
        time.sleep(1)
    if not device.exists():
        fail("MISSING_READONLY_PAYLOAD_DISK")
    mounted = subprocess.run(
        ["/usr/bin/mount", "-t", "iso9660", "-o", "ro,nosuid,nodev,noexec",
         str(device), str(MOUNT)],
        capture_output=True, timeout=15, check=False,
    )
    if mounted.returncode:
        fail("PAYLOAD_MOUNT_FAILED")
    return MOUNT


def trusted_payload(root: Path) -> tuple[dict, list[tuple[Path, bytes]]]:
    manifest_file = root / "manifest.json"
    if manifest_file.is_symlink() or not manifest_file.is_file():
        fail("MANIFEST_NOT_REGULAR")
    raw = manifest_file.read_bytes()
    if not raw or len(raw) > 24_000:
        fail("MANIFEST_SIZE")
    try:
        info = json.loads(raw)
    except ValueError:
        fail("MANIFEST_JSON")
    if not isinstance(info, dict) or set(info) != {"schema", "base_commit", "changes"}:
        fail("MANIFEST_FIELDS")
    if info["schema"] != PROTOCOL or not re.fullmatch(r"[a-f0-9]{40}", str(info["base_commit"])):
        fail("MANIFEST_SCHEMA")
    changes = info["changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= 3:
        fail("MANIFEST_CHANGES")
    verified = []
    seen = set()
    for entry in changes:
        if not isinstance(entry, dict) or set(entry) != {
            "path", "before_sha256", "after_sha256"
        }:
            fail("CHANGE_FIELDS")
        rawpath = entry["path"]
        if not isinstance(rawpath, str) or not ALLOWED.fullmatch(rawpath):
            fail("CHANGE_PATH")
        name = rawpath.split("/")[-1]
        if name in PROTECTED or name in seen:
            fail("PROTECTED_OR_DUPLICATE")
        seen.add(name)
        if not all(isinstance(entry[k], str) and SHA.fullmatch(entry[k])
                   for k in ("before_sha256", "after_sha256")):
            fail("INVALID_FILE_SHA")
        origin = SOURCE / name
        if origin.is_symlink() or not origin.is_file():
            fail("BASE_FILE_MISSING")
        original = origin.read_bytes()
        if digest(original) != entry["before_sha256"]:
            fail("ISO_BASE_MISMATCH")
        proposed = root / "files" / "src" / "synapse" / name
        if proposed.is_symlink() or not proposed.is_file():
            fail("CANDIDATE_FILE_MISSING")
        data = proposed.read_bytes()
        if len(data) > 64_000 or not data or digest(data) != entry["after_sha256"]:
            fail("CANDIDATE_DIGEST_MISMATCH")
        verified.append((Path(name), data))
    return info, verified


def run_smoke(work: Path) -> dict:
    if not compileall.compile_dir(str(work / "synapse"), quiet=2, force=True):
        fail("STATIC_SOURCE_COMPILE_FAILED")
    runuser = shutil.which("runuser")
    if runuser is None:
        fail("NONROOT_RUNUSER_MISSING")
    env = ["env", "-i", "PATH=/usr/bin:/bin", "HOME=/tmp",
           "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=" + str(work)]
    checks = [
        ("status", ["/usr/bin/python3", "-m", "synapse.cli", "--json", "status"]),
        ("doctor", ["/usr/bin/python3", "-m", "synapse.cli", "doctor"]),
    ]
    summary = {}
    for name, command in checks:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [runuser, "-u", "nobody", "--", *env, *command],
                cwd=work, capture_output=True, text=True, timeout=35,
                check=False, env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired):
            fail("BOUNDED_SMOKE_" + name.upper())
        if proc.returncode or len(proc.stdout.encode("utf-8")) > 128_000:
            fail("GUEST_SMOKE_" + name.upper())
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            fail("INVALID_SMOKE_JSON_" + name.upper())
        if not isinstance(payload, dict) or (
            name == "status" and not {"kernel", "memory", "cosmos"}.issubset(payload)
        ) or (
            name == "doctor" and not {"commands", "status"}.issubset(payload)
        ):
            fail("INVALID_SMOKE_RESULT_" + name.upper())
        summary[name] = {
            "passed": True,
            "duration_ms": int((time.monotonic() - start) * 1000),
            "json_shape_verified": True,
        }
        # No untrusted program stdout/stderr enters the serial log.
    return summary



# Trusted, fixed independent regression. The candidate may change debugger.py
# ONLY after the previous separate SHA/file allowlist checks. It cannot choose
# which tests to run, change test parameters or forge the harness success marker.
DEBUGGER_CONTRACT_CODE = r"""
import inspect
import json
import sys
from unittest.mock import patch
from synapse.debugger import Debugger

mode = sys.argv[1]
assert mode in ("baseline", "candidate")

class StubVM:
    def __init__(self, module, *, capabilities, trace):
        self.trace = trace

    def run(self):
        original = {"line": 7, "payload": "immutable-input"}
        self.trace(original)
        assert "breakpoint" not in original
        return {"ok": True}

with patch("synapse.debugger.VM", StubVM):
    dbg = Debugger(module=None, breakpoints={7})
    original_events = dbg.events
    first = dbg.run()
    pass_first = (
        len(dbg.events) == 1 and first["events"] is original_events
        and dbg.events[0]["breakpoint"] is True
    )
    second = dbg.run()
    pass_default = (
        pass_first and len(dbg.events) == 2
        and second["events"] is original_events
        and all(item["breakpoint"] is True for item in dbg.events)
    )
    if mode == "candidate":
        sig = inspect.signature(Debugger.run)
        pass_optional = (
            "reset_events" in sig.parameters
            and sig.parameters["reset_events"].default is False
        )
        third = dbg.run(reset_events=True)
        pass_optional = (
            pass_optional and third["events"] is original_events
            and dbg.events is original_events and len(dbg.events) == 1
            and dbg.events[0]["breakpoint"] is True
        )
    else:
        pass_optional = (
            "reset_events" not in inspect.signature(Debugger.run).parameters
        )
    passed = pass_default and pass_optional
    print(json.dumps({
        "passed": passed, "default_behavior_preserved": pass_default,
        "role_specific_expectation_met": pass_optional
    }, sort_keys=True))
    if not passed:
        raise SystemExit(2)
"""


def debugger_contract(work: Path, mode: str) -> dict:
    if mode not in {"baseline", "candidate"}:
        fail("INVALID_DEBUGGER_CONTRACT_MODE")
    runuser = shutil.which("runuser")
    if runuser is None:
        fail("NONROOT_RUNUSER_MISSING")
    environment = [
        "env", "-i", "PATH=/usr/bin:/bin", "HOME=/tmp",
        "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH=" + str(work)
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [runuser, "-u", "nobody", "--", *environment,
             "/usr/bin/python3", "-c", DEBUGGER_CONTRACT_CODE, mode],
            cwd=work, capture_output=True, text=True,
            timeout=35, check=False, env={"PATH": "/usr/bin:/bin"}
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("DEBUGGER_CONTRACT_TIMEOUT_OR_UNAVAILABLE")
    if proc.returncode or len(proc.stdout.encode("utf-8")) > 12_000:
        fail("DEBUGGER_BEHAVIOR_REGRESSION")
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        fail("UNTRUSTED_DEBUGGER_RESULT_JSON")
    if (
        not isinstance(result, dict)
        or set(result) != {
            "passed", "default_behavior_preserved",
            "role_specific_expectation_met"
        }
        or any(result.get(key) is not True for key in result)
    ):
        fail("DEBUGGER_BEHAVIOR_CONTRACT_FAILED")
    return {
        "passed": True,
        "default_behavior_preserved": True,
        "role_specific_expectation_met": True,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "test_input": "TWO_DEFAULT_RUNS_AND_ROLE_GATED_RESET",
    }


def main() -> None:
    mode = role()
    root = mount_payload()
    manifest, files = trusted_payload(root)
    work = SCRATCH / mode
    package = work / "synapse"
    if package.exists():
        fail("WORKDIR_ALREADY_EXISTS")
    shutil.copytree(SOURCE, package, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc"))
    if mode == "candidate":
        for filename, content in files:
            (package / filename).write_bytes(content)
    results = run_smoke(work)
    selected_debugger = any(
        entry["path"] == "src/synapse/debugger.py"
        for entry in manifest["changes"]
    )
    if selected_debugger:
        results["debugger_contract"] = debugger_contract(work, mode)
    receipt = {
        "schema": "synapse.evolution.vm.guest_result.v1",
        "role": mode,
        "source_commit": manifest["base_commit"],
        "verified_source_hashes": True,
        "candidate_files_applied": mode == "candidate",
        "network_policy": "HOST_QEMU_NIC_DISABLED",
        "checks": results,
        "tests": (
            "TWO_FIXED_SMOKE_CHECKS_PLUS_DEBUGGER_BEHAVIOR_CONTRACT"
            if selected_debugger else "TWO_FIXED_BOUNDED_SMOKE_CHECKS"
        ),
        "model_origin_attested": False,
        "production_modified": False,
    }
    report(MARKER + json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Never print untrusted file bytes, full tracebacks or guest diagnostics
        # that might include private prompt data in a publicly archived run.
        fail("TRUSTED_EVALUATOR_ABORTED")
