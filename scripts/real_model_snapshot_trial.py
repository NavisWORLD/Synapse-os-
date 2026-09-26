#!/usr/bin/env python3
"""Real pinned CPU model proposes ONE verified source statement; no deployments."""
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

MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REVISION = "ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155"
PATH = "src/synapse/debugger.py"
GOAL = "Add a non-mutating shallow snapshot method for the debugger trace."
ALLOWED = frozenset({
    "return [dict(event) for event in self.events]",
    "return [event.copy() for event in self.events]",
})
SUFFIX = ("\n    def snapshot_events(self) -> list[dict[str, Any]]:\n"
          '        """Return independent shallow copies of trace events."""\n')

def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def normalize(raw: str) -> tuple[str, str]:
    answer = raw.strip()
    fence = re.fullmatch(r"\x60{3}(?:python)?\r?\n([^\r\n]+)\r?\n\x60{3}", answer)
    note = "SINGLE_FENCE_STRIPPED" if fence else "RAW_ONE_LINE"
    if fence:
        answer = fence.group(1).strip()
    if "\n" in answer or "\r" in answer or len(answer) > 130 or answer not in ALLOWED:
        raise ValueError("model statement outside narrow one-line allowlist")
    tree = ast.parse(answer)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Return):
        raise ValueError("not exactly one return statement")
    return answer, note

def package(raw: str, before: str) -> tuple[str, str, str]:
    line, note = normalize(raw)
    if (before.count("class Debugger:") != 1
        or before.count("def run(self, *, reset_events: bool = False)") != 1
        or "def snapshot_events(" in before
        or "self.events.clear()" not in before):
        raise ValueError("unexpected source: the previously reviewed reset must exist")
    proposed = before + SUFFIX + "        " + line + "\n"
    ast.parse(proposed, filename=PATH)
    return line, note, proposed

def model_turn(model, tokenizer, conversation: list[dict[str, str]]) -> str:
    import torch
    prompt = tokenizer.apply_chat_template(conversation, tokenize=False,
                                            add_generation_prompt=True)
    tokenized = tokenizer(prompt, return_tensors="pt", truncation=False)
    with torch.inference_mode():
        response = model.generate(**tokenized, max_new_tokens=72, do_sample=False,
                                  pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(response[0, tokenized["input_ids"].shape[1]:],
                            skip_special_tokens=True)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, head = _repository(args.repo)
    task = prepare(root, GOAL, PATH)
    baseline = (root / PATH).read_text(encoding="utf-8")
    output = args.output.resolve(strict=False)
    if output == root or output.is_relative_to(root):
        raise ValueError("output must be outside source")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    verdict = {
        "schema": "synapse.evolution.real_snapshot_trial.v1",
        "model_id": MODEL, "model_revision": REVISION, "source_commit": head,
        "baseline_source_sha256": task["before_sha256"],
        "model_authored_scope": "ONE_STATEMENT_ONLY",
        "raw_model_turns": 0, "candidate_staged": False,
        "vm_result": "NOT_RUN", "tests": "NOT_RUN",
        "production_modified": False, "promotion": "OWNER_REVIEW_REQUIRED"
    }
    try:
        import torch
        from huggingface_hub import model_info
        from transformers import AutoTokenizer, AutoModelForCausalLM
        actual = model_info(MODEL, revision=REVISION, token=False)
        if actual.sha != REVISION:
            raise RuntimeError("model revision identity mismatch")
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL, revision=REVISION, token=False, trust_remote_code=False
        )
        torch.set_num_threads(2)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL, revision=REVISION, token=False, trust_remote_code=False,
            use_safetensors=True, torch_dtype=torch.float32
        ).eval()
        task_text = (
            "Complete one single Python statement inside a method of a debugger. "
            "Its self.events is a list of dictionaries. Return a NEW LIST of "
            "INDEPENDENT SHALLOW COPIES of each dictionary, in original order. "
            "Use a Python list comprehension and a standard per-dict copying operation. "
            "Do NOT modify the original list or dictionaries. Reply with JUST the "
            "one Python return statement, no explanation, no code fence."
        )
        conversation = [
            {"role": "system", "content": "Output one Python statement only. No tools."},
            {"role": "user", "content": task_text},
        ]
        started = time.monotonic()
        for turn in (1, 2):
            raw = model_turn(model, tokenizer, conversation)
            verdict["raw_model_turns"] = turn
            verdict["raw_turn_" + str(turn) + "_sha256"] = sha(raw.encode())
            (output / ("ACTUAL_MODEL_TURN_" + str(turn) + ".txt")).write_text(raw)
            try:
                line, note, after = package(raw, baseline)
            except ValueError:
                if turn == 1:
                    conversation.extend([
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": (
                            "Rejected by the validator. Return a list comprehension "
                            "of shallow copies of the existing event dicts, using "
                            "their built-in copy behavior. One return statement only."
                        )}
                    ])
                    continue
                verdict["outcome"] = "TWO_REAL_TURNS_REJECTED_NO_PATCH"
                break
            if _repository(root)[1] != head or (root / PATH).read_text() != baseline:
                raise RuntimeError("source changed while real model was running")
            proposal = {
                "schema": SCHEMA, "base_commit": head, "goal": GOAL,
                "model_label": MODEL + " (real one-line statement, trusted template)",
                "changes": [{"path": PATH, "before_sha256": task["before_sha256"],
                             "after_text": after}],
            }
            source = output / "STRICT_MODEL_BOUND_PROPOSAL.json"
            source.write_text(json.dumps(proposal, sort_keys=True, indent=2) + "\n")
            receipt = stage(source, root, output / "staged")
            receipt_dir = Path(receipt["workspace"]).parent
            for name in ("RECEIPT.json", "PATCH_REVIEW.diff"):
                (output / name).write_bytes((receipt_dir / name).read_bytes())
            verdict.update({
                "candidate_staged": True, "accepted_turn": turn,
                "normalization": note, "accepted_statement_sha256": sha(line.encode()),
                "candidate_source_sha256": sha(after.encode()),
                "outcome": "REAL_MODEL_ONE_LINE_ACCEPTED_REVIEW_ONLY",
            })
            break
        verdict["model_turn_seconds"] = round(time.monotonic() - started, 2)
    except Exception as exc:
        verdict["outcome"] = "MODEL_OR_STAGE_ERROR"
        verdict["error_class"] = type(exc).__name__
    (output / "TRIAL_VERDICT.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({k: verdict.get(k) for k in (
        "model_id", "raw_model_turns", "candidate_staged", "outcome"
    )}, sort_keys=True))
    return 0 if verdict["candidate_staged"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
