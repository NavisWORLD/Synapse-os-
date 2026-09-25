#!/usr/bin/env python3
"""Real, bounded, independently verified RAWRPHOS 12K proposal trial.

Never fake model replies; there is no scripted replacement patch, reference
model or cloud-provider fallback. Failed strict parsing is a valid experiment
result, not proof that an accepted patch exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from synapse.evolution import stage, validate
from synapse.evolution_model import prepare, parse_reply


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--beast-source", required=True, type=Path)
    p.add_argument("--checkpoint", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--evidence", required=True, type=Path)
    a = p.parse_args()
    root = a.repo.resolve(strict=True)
    evidence = a.evidence.resolve(strict=False)
    evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    packet = prepare(
        root,
        "Improve the documentation for Debugger._trace without changing runtime behavior.",
        "src/synapse/debugger.py",
    )
    raw = (
        "You are proposing ONE source code improvement to your operating system.\n"
        "Output ONLY a single JSON object matching this response_contract; no Markdown, "
        "no extra commentary or shell commands. Return the full replacement file in "
        "changes[0].after_text. Keep behavior unchanged; add a helpful short docstring "
        "to the _trace method. Keep all other code unchanged.\n"
        + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        + "\nJSON:"
    )
    request_sha = sha256(raw.encode("utf-8"))
    print(f"REAL_MODEL_ATTEMPT: model=rawrphos-native pinned=12K input_sha256={request_sha}")
    start = time.monotonic()
    cmd = [
        "python3", "-m", "rawrphos.inference.cli",
        "--checkpoint", str(a.checkpoint),
        "--expected-sha256", "339fb8e1d6f3950e2aa15a6e33bf8c0f28dd655cefc93b7926fb7545e7e97601",
        "--threads", "2", "prompt", raw, "--max-tokens", "256",
        "--temperature", "0", "--seed", "67",
    ]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("RUNNER_TEMP", "/tmp"),
        "PYTHONPATH": str(a.beast_source / "models"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    }
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True,
                                timeout=240, check=False, cwd=root)
    except subprocess.TimeoutExpired:
        (evidence / "PROBE_VERDICT.json").write_text(json.dumps({
            "schema": "synapse.evolution.real_model_probe.v1",
            "model_id": "rawrphos-native", "training_steps": 12000,
            "inference_completed": False, "strict_proposal_passed": False,
            "result": "MODEL_GENERATION_TIMEOUT_NO_PATCH",
        }, indent=2))
        return 2
    elapsed = time.monotonic() - start
    # Save exact generated text for inspection; it derives only from public
    # source and contains no owner memory or API credentials.
    generated = result.stdout if len(result.stdout.encode()) <= 250_000 else ""
    (evidence / "RAW_MODEL_OUTPUT.txt").write_text(generated, encoding="utf-8")
    verdict = {
        "schema": "synapse.evolution.real_model_probe.v1",
        "model_id": "rawrphos-native", "training_steps": 12000,
        "checkpoint_sha256": "339fb8e1d6f3950e2aa15a6e33bf8c0f28dd655cefc93b7926fb7545e7e97601",
        "source_commit": packet["base_commit"],
        "task_sha256": request_sha,
        "raw_reply_sha256": sha256(generated.encode()),
        "duration_seconds": round(elapsed, 2),
        "native_inference_exit_code": result.returncode,
        "inference_completed": result.returncode == 0 and bool(generated.strip()),
        "strict_proposal_passed": False, "production_modified": False,
        "model_origin": "LOCAL_VERIFIED_PINNED_NATIVE_CLI",
        "provider_fallback": False,
        "tests": "NOT_RUN",
        "outcome": "INFERENCE_ERROR" if result.returncode else "REPLY_NEEDS_VALIDATION",
    }
    if result.returncode == 0 and generated.strip():
        try:
            # Wrapper is trusted transport only; payload is the ACTUAL native
            # model text; parse_reply does not generate or repair JSON.
            proposed = parse_reply(
                {"schema": "beastbox-response-v1", "ok": True,
                 "result": {"response": generated}},
                packet,
            )
            _, current = __import__("synapse.evolution", fromlist=["_repository"])._repository(root)
            validate(proposed, root, current)
            proposal = evidence / "VALIDATED_MODEL_PROPOSAL.json"
            proposal.write_text(json.dumps(proposed, indent=2), encoding="utf-8")
            receipt = stage(proposal, root, evidence / "isolated-review")
            verdict["strict_proposal_passed"] = True
            verdict["outcome"] = "REAL_MODEL_PROPOSAL_STAGED_REVIEW_ONLY"
            verdict["staged_receipt"] = str(Path(receipt["workspace"]).parent / "RECEIPT.json")
        except (ValueError, TypeError, KeyError, OSError) as exc:
            verdict["outcome"] = "REAL_INFERENCE_OUTPUT_NOT_A_VALID_PROPOSAL"
            verdict["rejection_class"] = type(exc).__name__
            # Never replace invalid model text with a synthetic patch.
    (evidence / "PROBE_VERDICT.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "native_inference_exit_code": result.returncode,
        "real_inference_completed": verdict["inference_completed"],
        "strict_proposal_passed": verdict["strict_proposal_passed"],
        "outcome": verdict["outcome"],
        "generation_seconds": verdict["duration_seconds"],
        "reply_sha256": verdict["raw_reply_sha256"],
    }, sort_keys=True))
    # Invalid generated proposals are measured, not silently presented as success.
    return 0 if verdict["inference_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
