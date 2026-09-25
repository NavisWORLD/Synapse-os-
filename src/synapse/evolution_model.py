"""Strict local-model proposal adapter for the Synapse Evolution Engine.

Only an explicitly owner-selected local Beast provider is accepted. No default
cloud provider, no automatic provider fallback and no model-generated shell.
Generating a proposal is NEVER permission to execute or deploy it.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from .evolution import (
    MAX_TEXT_BYTES, SCHEMA, _allowed_path, _git, _repository, digest, stage, validate,
)

TASK_SCHEMA = "synapse.evolution.task.v1"
EXCHANGE_MAX_BYTES = 16_000
RESPONSE_MAX_BYTES = 300_000
ALLOWED_PROVIDERS = frozenset({"ollama", "compatible"})
MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:@+-]{0,110}\Z")


def prepare(repo: Path, goal: str, path_name: str) -> dict:
    """Explicitly selected single-file prompt; nothing is sent anywhere."""
    root, head = _repository(repo)
    if not isinstance(goal, str) or not 1 <= len(goal) <= 400:
        raise ValueError("goal must contain 1 to 400 characters")
    path = _allowed_path(path_name)
    selected = root.joinpath(*path.parts)
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("selected path contains a symlink")
    if not selected.is_file():
        raise ValueError("source file does not exist")
    _git("ls-files", "--error-unmatch", "--", str(path), cwd=root)
    raw = selected.read_bytes()
    if len(raw) > 7_500 or not raw:
        raise ValueError("local model request is limited to 7,500 source bytes")
    try:
        content = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("source file must be UTF-8 text") from exc
    packet = {
        "schema": TASK_SCHEMA,
        "proposal_schema": SCHEMA,
        "base_commit": head,
        "goal": goal,
        "path": str(path),
        "before_sha256": digest(raw),
        "before_text": content,
        "response_contract": {
            "schema": SCHEMA, "base_commit": head,
            "goal": goal, "model_label": "LOCAL_MODEL_UNVERIFIED",
            "changes": [{"path": str(path), "before_sha256": digest(raw),
                         "after_text": "COMPLETE_REPLACEMENT_FILE_TEXT"}],
        },
        "authority": "PROPOSAL_ONLY_NO_TOOLS_NO_EXECUTION_NO_DEPLOYMENT",
    }
    return packet


def local_url(value: str) -> str:
    """No remote host, URL indirection, credentials or exotic hostname."""
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise ValueError("local provider must use unauthenticated HTTP loopback")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/", "/v1", "/v1/"):
        raise ValueError("unsupported local provider URL")
    try:
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError("malformed local provider URL") from exc
    if not host or not port or not 1 <= port <= 65535:
        raise ValueError("local provider URL requires an explicit port")
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError("remote model endpoints are disabled")
        except ValueError as exc:
            raise ValueError("remote or ambiguous host rejected") from exc
    return value.rstrip("/")


def parse_reply(response: object, packet: dict) -> dict:
    """Accept exact structured model output; never infer missing fields."""
    if not isinstance(response, dict) or response.get("schema") != "beastbox-response-v1":
        raise ValueError("Beast returned no documented exchange schema")
    if response.get("ok") is not True:
        raise ValueError("Beast did not confirm a completed turn")
    result = response.get("result")
    if not isinstance(result, dict):
        raise ValueError("Beast provided no structured completion")
    # Different documented adapter versions use one of these text fields.
    possible = [result.get(k) for k in ("response", "text", "reply", "output")]
    options = [x for x in possible if isinstance(x, str) and x.strip()]
    if len(options) != 1:
        raise ValueError("Beast reply text is missing or ambiguous")
    raw = options[0]
    if len(raw.encode("utf-8")) > RESPONSE_MAX_BYTES:
        raise ValueError("model response exceeds cap")
    try:
        proposal = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("model reply must be exactly one JSON proposal object") from exc
    if not isinstance(proposal, dict) or proposal.get("schema") != SCHEMA:
        raise ValueError("invalid model proposal schema")
    for name, expected in (("base_commit", packet["base_commit"]),
                           ("goal", packet["goal"])):
        if proposal.get(name) != expected:
            raise ValueError("model changed pinned task identity")
    changes = proposal.get("changes")
    if not isinstance(changes, list) or len(changes) != 1:
        raise ValueError("model must propose exactly one requested change")
    change = changes[0]
    if not isinstance(change, dict) or change.get("path") != packet["path"] or change.get("before_sha256") != packet["before_sha256"]:
        raise ValueError("model attempted to change task path or baseline digest")
    # Do not treat model-provided identity as a verified model receipt.
    if not isinstance(proposal.get("model_label"), str):
        raise ValueError("model label missing")
    return proposal


def run_local(
    *, repo: Path, goal: str, path_name: str, executable: Path,
    data_dir: Path, provider: str, model: str, url: str,
    output_parent: Path, code_memory_approved: bool,
    runner=subprocess.run,
) -> dict:
    """One user-approved local Beast exchange, then stage a strict proposal."""
    if not code_memory_approved:
        raise ValueError("explicit owner approval is required before code enters Beast continuity")
    packet = prepare(repo, goal, path_name)
    if provider not in ALLOWED_PROVIDERS or not MODEL_NAME.fullmatch(model):
        raise ValueError("only explicit local ollama/compatible inference is permitted")
    safe_url = local_url(url)
    exe = executable.resolve(strict=True)
    if not exe.is_file() or not os.access(exe, os.X_OK):
        raise ValueError("specified local Beast executable is unavailable")
    src = repo.resolve(strict=True)
    home = data_dir.resolve(strict=False)
    if home == src or home.is_relative_to(src):
        raise ValueError("Beast continuity directory must be outside source repository")
    if home.is_symlink() or not home.is_dir():
        raise ValueError("use an existing real owner-controlled continuity directory")
    out = output_parent.resolve(strict=False)
    if out == src or out.is_relative_to(src) or out.is_relative_to(home):
        raise ValueError("staging output must be outside source and continuity directories")
    prompt = (
        "You are generating an UNTRUSTED CODE PROPOSAL, NOT running tools. "
        "Return one JSON object conforming exactly to response_contract. "
        "Do not use Markdown fences, change protected fields, suggest commands, "
        "include secrets or claim tests ran. Only replace the one file listed. "
        "All output will be reviewed; do not assume permission to deploy.\n"
        + json.dumps(packet, separators=(",", ":"), ensure_ascii=False)
    )
    request = {"schema": "beastbox-request-v1", "operation": "chat", "text": prompt}
    request_bytes = json.dumps(request, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(request_bytes) > EXCHANGE_MAX_BYTES:
        raise ValueError("single-file prompt exceeds bounded Beast exchange limit")
    argv = [str(exe), "runtime", "exchange", "--data-dir", str(home),
            "--provider", provider, "--model", model, "--url", safe_url]
    # No remote provider grants, arbitrary additional flags, shell execution,
    # inherited cloud API tokens or modification of the running Synapse OS.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        result = runner(argv, input=request_bytes.decode("utf-8"), capture_output=True,
                        text=True, timeout=240, check=False, shell=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("local Beast exchange unavailable or timed out") from exc
    if result.returncode != 0:
        raise ValueError("local Beast exchange rejected the turn; no fallback")
    raw = result.stdout
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > RESPONSE_MAX_BYTES:
        raise ValueError("oversized or missing Beast response")
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid Beast exchange JSON") from exc
    proposal = parse_reply(response, packet)
    root, head = _repository(repo)
    if head != packet["base_commit"]:
        raise ValueError("source changed while model was generating")
    validate(proposal, root, head)
    output_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Never write raw prompt, secrets, tokens or unvalidated text to a repo.
    temp = output_parent / ("proposal-" + digest(raw.encode("utf-8"))[:16] + ".json")
    try:
        with temp.open("x", encoding="utf-8") as file:
            json.dump(proposal, file)
        receipt = stage(temp, repo, output_parent)
    finally:
        temp.unlink(missing_ok=True)
    receipt["model_adapter"] = {
        "provider": provider, "claimed_model": model,
        "model_origin_attested": False, "remote_inference": False,
        "code_sent_to_continuity": True,
        "output_validated": True,
    }
    return receipt
