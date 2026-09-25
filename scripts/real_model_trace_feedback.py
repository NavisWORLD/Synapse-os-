#!/usr/bin/env python3
"""One REAL feedback iteration on an independently archived invalid coder reply.

The first pinned CPU run is historical evidence, not a fabricated assistant
message. A different GitHub Actions run feeds back only its proven failure.
No model output is silently changed to pass review or executed on the host.
"""
from __future__ import annotations

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
from scripts.real_model_trace_improvement import (
    MODEL, REVISION, PATH, GOAL, package
)

PRIOR_RUN = 36150437142
PRIOR_RAW_SHA = "740ae1c0ac1b46879e00052751e08a7c506df76dcc288bfd79c9f3d5bc0a36fc"
SOURCE_SHA = "4a771d51fb717cc094f33a0e5852686b5deeac8f295bb8d7d633332fe7a74d43"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def previous(artifact: Path) -> tuple[str, dict]:
    raw_file = artifact / "ACTUAL_MODEL_REPLY.txt"
    result_file = artifact / "RESULT.json"
    if raw_file.is_symlink() or result_file.is_symlink():
        raise ValueError("untrusted symlink artifact rejected")
    raw = raw_file.read_text(encoding="utf-8")
    result = json.loads(result_file.read_text(encoding="utf-8"))
    if (
        result.get("schema") != "synapse.evolution.model_trace_trial.v1"
        or result.get("model_id") != MODEL
        or result.get("model_revision") != REVISION
        or result.get("raw_output_sha256") != PRIOR_RAW_SHA
        or result.get("original_source_sha256") != SOURCE_SHA
        or result.get("real_inference_completed") is not True
        or result.get("candidate_staged") is not False
        or result.get("production_modified") is not False
        or sha(raw.encode("utf-8")) != PRIOR_RAW_SHA
    ):
        raise ValueError("initial real-model artifact failed independent checks")
    return raw, result


def reply(model, tokenizer, prior_raw: str) -> tuple[str, str]:
    original_task = (
        "Complete the blank with just one valid Python statement. "
        "Inside a Python method, self.events is a list of debugger trace records. "
        "The new optional reset_events flag is True and should empty the existing "
        "list IN PLACE (do not replace the list). "
        "Missing code after 'if reset_events:' is: ____ "
        "Return only the fully qualified missing statement, on one line, "
        "with no code fences, no explanation and no indentation."
    )
    correction = (
        "The validator rejected your previous answer. Assigning [] creates a "
        "new list and breaks identity for other references. Correct only that "
        "error: invoke the existing list's built-in in-place clearing method. "
        "Give EXACTLY the one corrected Python statement, nothing else. "
        "Do not explain and do not add a Markdown code fence."
    )
    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": "You are a Python code completion engine. Return ONLY the one-line Python statement."},
            {"role": "user", "content": original_task},
            {"role": "assistant", "content": prior_raw},
            {"role": "user", "content": correction},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    tokens = tokenizer(prompt, return_tensors="pt", truncation=False)
    with torch.inference_mode():
        output = model.generate(
            **tokens, max_new_tokens=40, do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )
    raw = tokenizer.decode(
        output[0, tokens["input_ids"].shape[1]:], skip_special_tokens=True
    )
    return correction, raw


def normalize(raw: str) -> tuple[str, str]:
    text = raw.strip()
    m = re.fullmatch(r"```(?:python)?\n([^\n]+)\n```", text)
    if m:
        return m.group(1).strip(), "STRIPPED_ONLY_SINGLE_CODE_FENCE"
    if "\n" in text or text.startswith("```"):
        raise ValueError("multi-line explanation or ambiguous code rejected")
    return text, "NO_NORMALIZATION"


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--original-artifact", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root, head = _repository(args.repo)
    prior_raw, prior_verdict = previous(args.original_artifact.resolve(strict=True))
    packet = prepare(root, GOAL, PATH)
    if packet["before_sha256"] != SOURCE_SHA:
        raise ValueError("current source differs from initial independent trial")
    output = args.output.resolve(strict=False)
    if output == root or output.is_relative_to(root):
        raise ValueError("output must be outside source")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    (output / "VERIFIED_PREVIOUS_REPLY.txt").write_text(prior_raw, encoding="utf-8")
    identity = model_info(MODEL, revision=REVISION, token=False)
    if identity.sha != REVISION:
        raise RuntimeError("immutable model revision metadata mismatch")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=REVISION, token=False, trust_remote_code=False
    )
    torch.set_num_threads(2)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, token=False, trust_remote_code=False,
        use_safetensors=True, torch_dtype=torch.float32
    ).eval()
    started = time.monotonic()
    correction, raw = reply(model, tokenizer, prior_raw)
    elapsed = round(time.monotonic() - started, 2)
    (output / "ACTUAL_FEEDBACK_REPLY.txt").write_text(raw, encoding="utf-8")
    verdict = {
        "schema": "synapse.evolution.coder_feedback_trial.v1",
        "prior_run": PRIOR_RUN, "prior_raw_sha256": PRIOR_RAW_SHA,
        "prior_outcome": prior_verdict["outcome"],
        "model_id": MODEL, "model_revision": REVISION,
        "real_feedback_inference_completed": bool(raw.strip()),
        "feedback_sha256": sha(correction.encode("utf-8")),
        "feedback_reply_sha256": sha(raw.encode("utf-8")),
        "duration_seconds": elapsed,
        "source_commit": head,
        "source_sha256": SOURCE_SHA,
        "statement_passed_exact_review": False,
        "candidate_staged": False,
        "model_wrote_complete_patch": False,
        "code_execution": "NOT_RUN",
        "vm_result": "NOT_RUN",
        "production_modified": False,
        "promotion": "OWNER_REVIEW_REQUIRED",
    }
    try:
        line, normalization = normalize(raw)
        before = (root / PATH).read_text(encoding="utf-8")
        statement, after = package(line, before)
        proposal = {
            "schema": SCHEMA, "base_commit": head,
            "goal": GOAL,
            "model_label": MODEL + " (real corrected statement, trusted assembly)",
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
            "normalization": normalization,
            "accepted_statement_sha256": sha(statement.encode("utf-8")),
            "candidate_sha256": sha(after.encode("utf-8")),
            "outcome": "REAL_MODEL_FEEDBACK_FIXED_STATEMENT_REVIEW_ONLY",
        })
    except ValueError:
        verdict["outcome"] = "REAL_MODEL_FEEDBACK_STILL_INVALID_NO_PATCH"
    (output / "RESULT.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        k: verdict[k] for k in (
            "prior_run", "real_feedback_inference_completed", "candidate_staged",
            "outcome", "duration_seconds",
        )
    }, sort_keys=True))
    return 0 if verdict["real_feedback_inference_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
