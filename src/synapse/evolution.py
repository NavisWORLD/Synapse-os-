"""Evolution Engine v0: observe and stage proposed edits without self-deployment.

Proposal text may originate from any model (including RAWRPHØS), but is
UNTRUSTED INPUT. This engine never executes staged code, grants tools,
transfers credentials, updates the live machine or promotes a release.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile

from . import core

SCHEMA = "synapse.evolution.proposal.v1"
RECEIPT_SCHEMA = "synapse.evolution.receipt.v1"
MAX_CHANGES = 3
MAX_TEXT_BYTES = 64_000
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str, cwd: Path, timeout: int = 45) -> str:
    """Local-only fixed git operations; never invoke a model-provided command."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(cwd),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, env=env, text=True,
            capture_output=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("local git operation unavailable or timed out") from exc
    if result.returncode:
        raise ValueError(f"local git operation failed (exit {result.returncode})")
    return result.stdout.strip()


def _repository(repo: Path) -> tuple[Path, str]:
    repo = repo.resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("source repository is not a directory")
    root = Path(_git("rev-parse", "--show-toplevel", cwd=repo)).resolve()
    if root != repo:
        raise ValueError("provide the repository root, not a subdirectory")
    if _git("status", "--porcelain", "--untracked-files=no", cwd=root):
        raise ValueError("tracked source changes exist; commit or inspect them first")
    head = _git("rev-parse", "HEAD", cwd=root)
    if not HEX40.fullmatch(head):
        raise ValueError("source HEAD is not a SHA-1 commit")
    return root, head


def observe(repo: Path) -> dict:
    """Collect bounded local telemetry; never read Beast memory or credentials."""
    root, head = _repository(repo)
    status = core.system_status()
    payload = {
        "schema": "synapse.evolution.observation.v1",
        "repo_commit": head,
        "synapse_version": status["synapse_version"],
        "machine": status["machine"],
        "cpu_count": status["cpu_count"],
        "load_1m": status["load_1m"],
        "memory_available_bytes": status["memory"]["available_bytes"],
        "cosmos": {
            name: bool(info["reachable"]) for name, info in status["cosmos"].items()
        },
        "execution": "OBSERVATION_ONLY",
        "model_input": "NOT_SENT",
    }
    # Sort keys for reproducible hashing; timestamps/host identifiers are omitted.
    payload["observation_sha256"] = digest(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return payload


def _allowed_path(raw: object) -> PurePosixPath:
    if not isinstance(raw, str) or len(raw) > 190 or "\\" in raw:
        raise ValueError("change path must be a short forward-slash path")
    path = PurePosixPath(raw)
    if (not raw or raw != path.as_posix() or path.is_absolute()
            or any(p in {"", ".", ".."} for p in raw.split("/"))
            or any(p.startswith(".") for p in path.parts)):
        raise ValueError("unsafe or non-canonical change path")
    if (raw.startswith("src/synapse/") and path.suffix == ".py"
            and len(path.parts) == 3 and path.name not in {"evolution.py", "evolution_model.py", "evolution_review.py", "evolution_bundle.py", "cli.py", "agent.py", "__init__.py"}):
        return path
    if raw.startswith("docs/") and path.suffix == ".md" and len(path.parts) == 2:
        return path
    # Tests are reviewed as generated changes, never trusted as proof of passing.
    if raw.startswith("tests/") and path.suffix == ".py" and len(path.parts) == 2:
        return path
    raise ValueError("change path is outside the initial evolution allowlist")


def validate(proposal: object, root: Path, head: str) -> list[tuple[PurePosixPath, bytes, bytes]]:
    if not isinstance(proposal, dict) or set(proposal) != {
        "schema", "base_commit", "goal", "model_label", "changes"
    }:
        raise ValueError("proposal must contain only the documented fields")
    if proposal["schema"] != SCHEMA or proposal["base_commit"] != head:
        raise ValueError("proposal schema or exact base commit mismatch")
    if not isinstance(proposal["goal"], str) or not 1 <= len(proposal["goal"]) <= 500:
        raise ValueError("goal must be 1-500 characters")
    if not isinstance(proposal["model_label"], str) or not 1 <= len(proposal["model_label"]) <= 100:
        raise ValueError("model_label must be 1-100 characters; it is not attestation")
    changes = proposal["changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_CHANGES:
        raise ValueError("proposal must include 1-3 changes")
    verified = []
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {
            "path", "before_sha256", "after_text"
        }:
            raise ValueError("each change needs path, before_sha256 and after_text")
        path = _allowed_path(change["path"])
        if str(path) in seen:
            raise ValueError("duplicate change path")
        seen.add(str(path))
        if not isinstance(change["before_sha256"], str) or not HEX64.fullmatch(change["before_sha256"]):
            raise ValueError("invalid baseline SHA-256")
        if not isinstance(change["after_text"], str):
            raise ValueError("replacement must be UTF-8 text")
        after = change["after_text"].encode("utf-8")
        if not after or len(after) > MAX_TEXT_BYTES or b"\x00" in after:
            raise ValueError("replacement size/content violates limit")
        # Reject symlink components, not just the final file.
        current = root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink target or ancestor is forbidden")
        if not current.is_file():
            raise ValueError("version one only changes existing regular files")
        _git("ls-files", "--error-unmatch", "--", str(path), cwd=root)
        before = current.read_bytes()
        if digest(before) != change["before_sha256"]:
            raise ValueError("baseline digest mismatch; re-observe and re-propose")
        if before == after:
            raise ValueError("proposal does not change content")
        if path.suffix == ".py":
            try:
                ast.parse(after, filename=str(path))
            except (SyntaxError, ValueError) as exc:
                raise ValueError("proposed Python fails syntax parsing") from exc
        verified.append((path, before, after))
    return verified


def stage(proposal_path: Path, repo: Path, output_parent: Path) -> dict:
    """Create a detached, isolated Git copy containing a *non-executed* patch.

    The real repo, booted OS, keys, tool grants and persistent COSMOS memory
    never enter the staging operation. Receipts are evidence of staging only.
    """
    root, head = _repository(repo)
    if proposal_path.is_symlink() or not proposal_path.is_file():
        raise ValueError("proposal must be a regular JSON file")
    if proposal_path.stat().st_size > MAX_CHANGES * MAX_TEXT_BYTES + 4096:
        raise ValueError("proposal too large")
    try:
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON proposal") from exc
    verified = validate(proposal, root, head)  # fail before any staging writes
    if output_parent.is_symlink():
        raise ValueError("output cannot be a symlink")
    candidate = output_parent.resolve(strict=False)
    if candidate == root or candidate.is_relative_to(root):
        raise ValueError("output must live outside the source repository")
    output_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = output_parent.resolve(strict=True)
    if parent == root or parent.is_relative_to(root):
        raise ValueError("output must live outside the source repository")
    scratch = Path(tempfile.mkdtemp(prefix="synapse-evolution-", dir=parent))
    checkout = scratch / "checkout"
    try:
        _git("clone", "--quiet", "--no-local", "--no-hardlinks",
             "--no-checkout", str(root), str(checkout), cwd=root, timeout=120)
        _git("checkout", "--quiet", "--detach", head, cwd=checkout)
        _git("remote", "remove", "origin", cwd=checkout)
        change_receipts = []
        for path, before, after in verified:
            file = checkout.joinpath(*path.parts)
            if file.is_symlink() or not file.is_file() or digest(file.read_bytes()) != digest(before):
                raise ValueError("detached checkout disagrees with checked source")
            file.write_bytes(after)
            change_receipts.append({
                "path": str(path),
                "before_sha256": digest(before),
                "after_sha256": digest(after),
            })
        diff = _git("diff", "--no-ext-diff", "--", *[str(p) for p, _, _ in verified],
                    cwd=checkout)
        if not diff:
            raise ValueError("no Git diff produced")
        (scratch / "PATCH_REVIEW.diff").write_text(diff + "\n", encoding="utf-8")
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "base_commit": head,
            "goal": proposal["goal"],
            "model_label_unverified": proposal["model_label"],
            "changes": change_receipts,
            "patch_sha256": digest((diff + "\n").encode("utf-8")),
            "execution": "STATIC_SYNTAX_ONLY",
            "tests": "NOT_RUN",
            "vm_boot": "NOT_RUN",
            "production_modified": False,
            "promotion": "OWNER_REVIEW_REQUIRED",
            "workspace": str(checkout),
        }
        (scratch / "RECEIPT.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return receipt
    except Exception:
        shutil.rmtree(scratch)
        raise
