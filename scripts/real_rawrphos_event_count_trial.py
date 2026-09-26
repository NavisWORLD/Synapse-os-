#!/usr/bin/env python3
"""Actual pinned RAWRPHØS CPU proposal probe; only stage accepted raw model text.

This experiment cannot execute model-authored code, authorize tools or promote
source. Rejected generations and infrastructure errors remain distinct.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import time

from synapse.evolution import SCHEMA, _repository, stage
from synapse.evolution_model import prepare

MODEL = "rawrphos-native"
SOURCE_COMMIT = "4054d675c4ef85d1343890f2e956dbc2fe88b2e6"
RELEASE = "rawrphos-native-step-00012000-run-35819774878"
EXPECTED_WEIGHT_SHA256 = "339fb8e1d6f3950e2aa15a6e33bf8c0f28dd655cefc93b7926fb7545e7e97601"
EXPECTED_STEPS = 12_000
PATH = "src/synapse/debugger.py"
GOAL = "Add a read-only Debugger.event_count method reporting the number of trace events."
ACCEPTED_STATEMENT = "return len(self.events)"
SUFFIX = ("\n    def event_count(self) -> int:\n"
          '        """Return the current number of debugger trace events."""\n')
PROMPTS = (
    "Python. Inside a method, self.events is a list. Write ONE return statement "
    "giving its number of elements. Output one Python code line only.",
    "That did not pass validation. Output one Python return statement that "
    "computes the length of self.events using Python's built-in len. "
    "No explanations or markdown.",
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def normalize(raw: str) -> str:
    """No answer extraction, case repair, completion synthesis or fuzzy matching."""
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 256:
        raise ValueError("missing or oversized raw generation")
    answer = raw.strip()
    fence = re.fullmatch(r"\x60{3}(?:python)?\r?\n([^\r\n]+)\r?\n\x60{3}", answer)
    if fence:
        answer = fence.group(1).strip()
    if answer != ACCEPTED_STATEMENT:
        raise ValueError("model did not produce the exact validated source statement")
    if len(ast.parse("def f(self):\n    " + answer + "\n").body) != 1:
        raise ValueError("invalid statement")
    return answer

def package(raw: str, before: str) -> tuple[str, str]:
    statement = normalize(raw)
    if (before.count("class Debugger:") != 1
        or before.count("def run(self, *, reset_events: bool = False)") != 1
        or before.count("self.events.clear()") != 1
        or "def event_count(" in before):
        raise ValueError("base no longer matches the reviewed debugger contract")
    after = before + SUFFIX + "        " + statement + "\n"
    ast.parse(after, filename=PATH)
    return statement, after

def verify_model_info(info: dict) -> None:
    if (info.get("model_id") != MODEL
        or info.get("checkpoint_sha256") != EXPECTED_WEIGHT_SHA256
        or info.get("training_steps") != EXPECTED_STEPS
        or info.get("serving_backend") != "pytorch-cpu"):
        raise ValueError("native model identity, checkpoint, step or CPU backend mismatch")

def trial(repo: Path, checkpoint: Path, output: Path) -> dict:
    root, head = _repository(repo)
    task = prepare(root, GOAL, PATH)
    before = (root / PATH).read_text(encoding="utf-8")
    if not checkpoint.is_dir() or checkpoint.is_symlink():
        raise ValueError("checkpoint must be a real extracted release directory")
    out = output.resolve(strict=False)
    if out == root or out.is_relative_to(root) or out == checkpoint or out.is_relative_to(checkpoint):
        raise ValueError("evidence must stay outside source and the checkpoint")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    verdict = {
        "schema": "synapse.evolution.real_rawrphos_trial.v1",
        "model_id": MODEL, "model_source_commit": SOURCE_COMMIT,
        "model_release": RELEASE, "expected_weight_sha256": EXPECTED_WEIGHT_SHA256,
        "source_commit": head, "baseline_source_sha256": task["before_sha256"],
        "model_authored_scope": "ONE_EXACT_STATEMENT_ONLY_IF_ACCEPTED",
        "raw_model_turns": 0, "candidate_staged": False,
        "tests": "NOT_RUN", "vm_result": "NOT_RUN",
        "production_modified": False, "promotion": "OWNER_REVIEW_REQUIRED",
    }
    try:
        # The pinned public checkout is installed by the workflow. Inference is
        # native and happens locally in this job, without hosted-model calls.
        from rawrphos.inference.engine import Engine
        started = time.monotonic()
        engine = Engine(checkpoint, max_new_tokens=64, threads=2,
                        expected_sha256=EXPECTED_WEIGHT_SHA256)
        info = engine.info()
        verify_model_info(info)
        verdict["actual_checkpoint_sha256"] = info["checkpoint_sha256"]
        verdict["tokenizer_sha256"] = info["tokenizer_sha256"]
        for turn, prompt in enumerate(PROMPTS, 1):
            # Bounded *independent* prompts, not a claim of chat-memory feedback.
            raw = engine.complete(prompt, max_tokens=48, temperature=0, seed=67)
            verdict["raw_model_turns"] = turn
            verdict[f"raw_turn_{turn}_sha256"] = sha(raw.encode("utf-8"))
            (out / f"ACTUAL_RAWRPHOS_TURN_{turn}.txt").write_text(raw, encoding="utf-8")
            try:
                statement, after = package(raw, before)
            except ValueError:
                continue
            if _repository(root)[1] != head or (root / PATH).read_text(encoding="utf-8") != before:
                raise RuntimeError("source changed during native inference")
            proposal = {
                "schema": SCHEMA, "base_commit": head, "goal": GOAL,
                "model_label": "rawrphos-native (actual CPU generation; one validated line)",
                "changes": [{"path": PATH, "before_sha256": task["before_sha256"],
                             "after_text": after}],
            }
            proposal_path = out / "STRICT_MODEL_BOUND_PROPOSAL.json"
            proposal_path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
            staged = stage(proposal_path, root, out / "staged")
            stage_dir = Path(staged["workspace"]).parent
            for name in ("RECEIPT.json", "PATCH_REVIEW.diff"):
                (out / name).write_bytes((stage_dir / name).read_bytes())
            verdict.update({
                "candidate_staged": True, "accepted_turn": turn,
                "accepted_statement_sha256": sha(statement.encode("utf-8")),
                "candidate_source_sha256": sha(after.encode("utf-8")),
                "outcome": "GENUINE_NATIVE_ONE_LINE_STAGED_REVIEW_ONLY",
            })
            break
        if not verdict["candidate_staged"]:
            verdict["outcome"] = "TWO_NATIVE_GENERATIONS_REJECTED_NO_PATCH"
        verdict["native_trial_seconds"] = round(time.monotonic() - started, 3)
    except Exception as exc:
        verdict["outcome"] = "CHECKPOINT_INFERENCE_OR_STAGE_ERROR"
        verdict["error_class"] = type(exc).__name__
        # Do not upload host paths or arbitrary exception text.
    (out / "TRIAL_VERDICT.json").write_text(json.dumps(verdict, sort_keys=True, indent=2) + "\n")
    return verdict

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verdict = trial(args.repo, args.checkpoint, args.output)
    print(json.dumps({k: verdict.get(k) for k in (
        "model_id", "raw_model_turns", "candidate_staged", "outcome"
    )}, sort_keys=True))
    return 0 if verdict["candidate_staged"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
