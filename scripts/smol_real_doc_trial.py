#!/usr/bin/env python3
"""Real public local SmolLM2 Instruct one-shot *documentation* proposal trial.

This script does not call Beast Box, change a deployed OS or claim native
RAWRPHOS origin. It tests whether a replaceable public instruct model can
supply a narrow natural-language docstring that a trusted, bounded packager
converts into an independently checked Stage 1 source proposal.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
import time

import torch
from huggingface_hub import model_info
from transformers import AutoModelForCausalLM, AutoTokenizer

from synapse.evolution import SCHEMA, _repository, stage
from synapse.evolution_model import prepare

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
PATH = "src/synapse/debugger.py"
GOAL = "Document what Debugger._trace records, without changing executable behavior."
ANCHOR = "    def _trace(self, event: dict[str, Any]) -> None:\n"
MAX_NEW = 56


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate(model, tokenizer, user: str) -> str:
    prompt = tokenizer.apply_chat_template([
        {"role": "system", "content": "You write accurate, short Python docstrings. Return ONLY one plain English sentence. No quotes, code or markdown."},
        {"role": "user", "content": user},
    ], tokenize=False, add_generation_prompt=True)
    tokens = tokenizer(prompt, return_tensors="pt", truncation=False)
    with torch.inference_mode():
        output = model.generate(
            **tokens, max_new_tokens=MAX_NEW, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(output[0, tokens["input_ids"].shape[1]:], skip_special_tokens=True)


def validate_docstring(raw: str) -> str:
    # Never concatenate arbitrary model output into a Python source file.
    # Keep generated prose as data, never model-selected executable code.
    sentence = raw.strip()
    if sentence.startswith(('"', "'")) and sentence.endswith(('"', "'")):
        sentence = sentence[1:-1].strip()
    if "\n" in sentence or len(sentence) > 150 or len(sentence) < 27:
        raise ValueError("not a single short sentence")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,;.:()/-]{25,149}", sentence):
        raise ValueError("contains unsupported non-prose characters")
    if "event" not in sentence.lower() or "breakpoint" not in sentence.lower():
        raise ValueError("does not correctly describe event and breakpoint behavior")
    if not sentence.endswith("."):
        raise ValueError("docstring must end in a period")
    return sentence


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, head = _repository(args.repo)
    packet = prepare(root, GOAL, PATH)
    output = args.output.resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    meta = model_info(MODEL, token=False)
    sha = meta.sha
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise RuntimeError("unversioned Hub checkpoint rejected")
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=sha, token=False, trust_remote_code=False
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=sha, token=False, trust_remote_code=False,
        use_safetensors=True, torch_dtype=torch.float32
    ).eval()
    task = (
        "Write exactly ONE short English documentation sentence. "
        "Start the sentence with Record and include the words event and breakpoint. "
        "Behavior to document: a debugger creates a copy of an incoming event, "
        "marks the copy as a breakpoint when its line matches one of the "
        "configured breakpoints, and appends the copied event to its event list. "
        "Only provide the plain-English sentence. This is not a programming "
        "or code-generation question.\n"
    )
    before = time.monotonic()
    raw = generate(model, tokenizer, task)
    seconds = round(time.monotonic() - before, 2)
    (output / "ACTUAL_MODEL_REPLY.txt").write_text(raw, encoding="utf-8")
    verdict = {
        "schema": "synapse.evolution.smol_doc_trial.v1",
        "model_id": MODEL,
        "model_origin": "PUBLIC_TRANSFORMERS_CPU_PINNED_REVISION",
        "hub_revision": sha,
        "model_parameters": 134_500_000,
        "real_model_inference_completed": bool(raw.strip()),
        "task_sha256": digest(task.encode()),
        "raw_reply_sha256": digest(raw.encode()),
        "response_seconds": seconds,
        "original_source_sha256": packet["before_sha256"],
        "source_base_commit": head,
        "candidate_staged": False,
        "candidate_kind": "MODEL_SUGGESTED_PROSE_ONLY_TRUSTED_PACKAGING",
        "model_wrote_executable_code": False,
        "passed_vm_evaluation": False,
        "production_modified": False,
        "auto_deployment": False,
    }
    try:
        sentence = validate_docstring(raw)
        before_source = (root / PATH).read_text(encoding="utf-8")
        if before_source.count(ANCHOR) != 1:
            raise ValueError("source anchor did not match exactly")
        after_source = before_source.replace(ANCHOR, ANCHOR + '        """' + sentence + '"""\n')
        ast.parse(after_source, filename=PATH)
        proposal = {
            "schema": SCHEMA, "base_commit": head, "goal": GOAL,
            "model_label": MODEL + " (source verified by model hub revision)",
            "changes": [{
                "path": PATH, "before_sha256": packet["before_sha256"],
                "after_text": after_source,
            }],
        }
        candidate = output / "PROPOSAL.json"
        candidate.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        staged = stage(candidate, root, output / "staged")
        verdict["candidate_staged"] = True
        verdict["review_receipt"] = str(Path(staged["workspace"]).parent / "RECEIPT.json")
        verdict["accepted_docstring"] = sentence
        verdict["outcome"] = "MODEL_PROSE_STAGED_AS_DOCSTRING_FOR_REVIEW_ONLY"
    except ValueError as exc:
        verdict["outcome"] = "REAL_INFERENCE_COMPLETED_BUT_PROSE_REJECTED"
        verdict["rejection_class"] = type(exc).__name__
    (output / "RESULT.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    print(json.dumps({k: verdict[k] for k in (
        "model_id", "hub_revision", "real_model_inference_completed",
        "candidate_staged", "outcome", "response_seconds",
    )}, sort_keys=True))
    return 0 if verdict["real_model_inference_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
