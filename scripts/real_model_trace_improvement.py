#!/usr/bin/env python3
"""A distinct pinned real coder-model attempt after SmolLM2's rejected first trial.

The model generates ONLY a proposed single method-call statement. An exact
allowlist checks the raw suggestion; trusted source assembly then creates an
OPT-IN, backward-compatible argument in Debugger.run. No proposed code runs
outside disposable VM evaluation. Invalid outputs are preserved, never fixed.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import time

import torch
from huggingface_hub import model_info
from transformers import AutoModelForCausalLM, AutoTokenizer

from synapse.evolution import SCHEMA, _repository, stage
from synapse.evolution_model import prepare

MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REVISION = "ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155"
PATH = "src/synapse/debugger.py"
GOAL = "Add an explicitly opt-in fresh trace for Debugger.run while preserving default behavior."
ANCHOR = "    def run(self) -> dict[str, Any]:\n"
NEW_ANCHOR = "    def run(self, *, reset_events: bool = False) -> dict[str, Any]:\n"
ALLOWED = "self.events.clear()"


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def model_turn(model, tokenizer) -> tuple[str, str]:
    # No private code or secrets enter the public model for this experiment.
    task = (
        "Complete the blank with just one valid Python statement. "
        "Inside a Python method, self.events is a list of debugger trace records. "
        "The new optional reset_events flag is True and should empty the existing "
        "list IN PLACE (do not replace the list). "
        "Missing code after 'if reset_events:' is: ____ "
        "Return only the fully qualified missing statement, on one line, "
        "with no code fences, no explanation and no indentation."
    )
    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": "You are a Python code completion engine. Return ONLY the one-line Python statement."},
            {"role": "user", "content": task},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    tokens = tokenizer(prompt, return_tensors="pt", truncation=False)
    with torch.inference_mode():
        output = model.generate(
            **tokens, max_new_tokens=32, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return task, tokenizer.decode(
        output[0, tokens["input_ids"].shape[1]:], skip_special_tokens=True
    )


def package(raw: str, before: str) -> tuple[str, str]:
    # Do not convert untrusted prose into code. The only accepted statement is
    # a known safe single AST method-call, byte-identical to the raw answer.
    statement = raw.strip()
    if statement != ALLOWED:
        raise ValueError("the one model-authored statement did not pass exact review")
    parsed = ast.parse(statement)
    assert len(parsed.body) == 1
    if before.count(ANCHOR) != 1 or NEW_ANCHOR in before:
        raise ValueError("unexpected baseline signature")
    addition = NEW_ANCHOR + "        if reset_events:\n            " + statement + "\n"
    after = before.replace(ANCHOR, addition)
    ast.parse(after, filename=PATH)
    if after.replace(addition, ANCHOR, 1) != before:
        raise ValueError("review diff is not exactly the approved narrow transformation")
    return statement, after


def main() -> int:
    import argparse
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    root, head = _repository(args.repo)
    packet = prepare(root, GOAL, PATH)
    output = args.output.resolve(strict=False)
    if output == root or output.is_relative_to(root):
        raise ValueError("model evidence directory must be outside source checkout")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    hub = model_info(MODEL, revision=REVISION, token=False)
    if hub.sha != REVISION:
        raise RuntimeError("pinned public model revision differs from expected; no silent update")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=REVISION, token=False, trust_remote_code=False
    )
    torch.set_num_threads(2)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, token=False,
        trust_remote_code=False, use_safetensors=True,
        torch_dtype=torch.float32,
    ).eval()
    start = time.monotonic()
    task, raw = model_turn(model, tokenizer)
    elapsed = round(time.monotonic() - start, 2)
    (output / "ACTUAL_MODEL_REPLY.txt").write_text(raw, encoding="utf-8")
    verdict = {
        "schema": "synapse.evolution.model_trace_trial.v1",
        "model_id": MODEL, "model_revision": REVISION,
        "inference_origin": "PINNED_PUBLIC_CPU_TRANSFORMERS",
        "real_inference_completed": bool(raw.strip()),
        "model_wrote_complete_patch": False,
        "model_proposed_one_python_statement": True,
        "raw_output_sha256": sha(raw.encode("utf-8")),
        "task_sha256": sha(task.encode("utf-8")),
        "duration_seconds": elapsed, "source_commit": head,
        "original_source_sha256": packet["before_sha256"],
        "statement_passed_exact_review": False, "candidate_staged": False,
        "tests": "NOT_RUN", "vm_result": "NOT_RUN",
        "production_modified": False, "promotion": "OWNER_REVIEW_REQUIRED",
    }
    try:
        original = (root / PATH).read_text(encoding="utf-8")
        statement, after = package(raw, original)
        proposal = {
            "schema": SCHEMA, "base_commit": head,
            "goal": GOAL,
            "model_label": MODEL + " (pinned model statement, trusted assembly)",
            "changes": [{
                "path": PATH, "before_sha256": packet["before_sha256"],
                "after_text": after,
            }],
        }
        target = output / "MODEL_BOUND_PROPOSAL.json"
        target.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        receipt = stage(target, root, output / "staged")
        receipt_dir = Path(receipt["workspace"]).parent
        for name in ("RECEIPT.json", "PATCH_REVIEW.diff"):
            (output / name).write_bytes((receipt_dir / name).read_bytes())
        verdict.update({
            "statement_passed_exact_review": True,
            "candidate_staged": True,
            "model_statement_sha256": sha(statement.encode("utf-8")),
            "candidate_sha256": sha(after.encode("utf-8")),
            "candidate_kind": "MODEL_AUTHORED_ONE_STATEMENT_TRUSTED_OPTIN_ASSEMBLY",
            "outcome": "REAL_MODEL_SINGLE_STATEMENT_ACCEPTED_REVIEW_ONLY",
        })
    except ValueError:
        verdict["outcome"] = "REAL_INFERENCE_INVALID_STATEMENT_NOT_STAGED"
    (output / "RESULT.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        k: verdict[k] for k in ("real_inference_completed", "candidate_staged",
                                "outcome", "duration_seconds")
    }))
    return 0 if verdict["real_inference_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
