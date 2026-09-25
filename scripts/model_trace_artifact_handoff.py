#!/usr/bin/env python3
"""Bind a real, previously recorded model correction to a fresh clean source HEAD.

This NEVER calls a model, accepts an unverified replacement patch or executes
model-supplied code. Its only accepted change is the exact verified statement
in the owner-reviewed optional-reset source template.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

from synapse.evolution import SCHEMA, _repository, stage

MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REV = "ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155"
ORIGINAL_TRIAL_RUN = 36150437142
FEEDBACK_RUN = 36150869207
ORIGINAL_REPLY_SHA = "740ae1c0ac1b46879e00052751e08a7c506df76dcc288bfd79c9f3d5bc0a36fc"
CORRECTED_REPLY_SHA = "8723342b9531a7ae1e13d1ade26b8bdaec17aa5bb10f3776235fb554fa477fa1"
BASE_SOURCE_SHA = "4a771d51fb717cc094f33a0e5852686b5deeac8f295bb8d7d633332fe7a74d43"
PATH = "src/synapse/debugger.py"
OLD = "    def run(self) -> dict[str, Any]:\n"
NEW = (
    "    def run(self, *, reset_events: bool = False) -> dict[str, Any]:\n"
    "        if reset_events:\n"
    "            self.events.clear()\n"
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bound(artifact: Path, root: Path, base: str) -> tuple[str, dict]:
    for name in ("RESULT.json", "VERIFIED_PREVIOUS_REPLY.txt",
                 "ACTUAL_FEEDBACK_REPLY.txt", "MODEL_BOUND_PROPOSAL.json"):
        candidate = artifact / name
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("missing or symlinked original model evidence: " + name)
    result = json.loads((artifact / "RESULT.json").read_text(encoding="utf-8"))
    prior = (artifact / "VERIFIED_PREVIOUS_REPLY.txt").read_text(encoding="utf-8")
    raw = (artifact / "ACTUAL_FEEDBACK_REPLY.txt").read_text(encoding="utf-8")
    trial = json.loads((artifact / "MODEL_BOUND_PROPOSAL.json").read_text(encoding="utf-8"))
    if (
        result.get("schema") != "synapse.evolution.coder_feedback_trial.v1"
        or result.get("prior_run") != ORIGINAL_TRIAL_RUN
        or result.get("prior_raw_sha256") != ORIGINAL_REPLY_SHA
        or result.get("feedback_reply_sha256") != CORRECTED_REPLY_SHA
        or result.get("model_id") != MODEL or result.get("model_revision") != REV
        or result.get("candidate_staged") is not True
        or result.get("statement_passed_exact_review") is not True
        or result.get("normalization") != "STRIPPED_ONLY_SINGLE_CODE_FENCE"
        or result.get("source_sha256") != BASE_SOURCE_SHA
        or result.get("production_modified") is not False
        or result.get("promotion") != "OWNER_REVIEW_REQUIRED"
        or sha(prior.encode("utf-8")) != ORIGINAL_REPLY_SHA
        or sha(raw.encode("utf-8")) != CORRECTED_REPLY_SHA
        or raw.strip() != "```python\nself.events.clear()\n```"
    ):
        raise ValueError("model response or predecessor provenance did not verify")
    source = (root / PATH).read_bytes()
    if sha(source) != BASE_SOURCE_SHA:
        raise ValueError("real source differs from original model inference task")
    before = source.decode("utf-8")
    if before.count(OLD) != 1 or NEW in before:
        raise ValueError("exact source review anchor is not unique")
    after = before.replace(OLD, NEW)
    ast.parse(after, filename=PATH)
    if (
        trial.get("schema") != SCHEMA
        or not isinstance(trial.get("changes"), list)
        or len(trial["changes"]) != 1
        or trial["changes"][0] != {
            "path": PATH, "before_sha256": BASE_SOURCE_SHA,
            "after_text": after,
        }
        or result.get("candidate_sha256") != sha(after.encode("utf-8"))
    ):
        raise ValueError("original staged source is not the exact verified corrected model line")
    proposal = {
        "schema": SCHEMA, "base_commit": base,
        "goal": "Add an explicitly opt-in fresh trace for Debugger.run while preserving default behavior.",
        "model_label": MODEL + " (real corrected one-liner; trusted assembly)",
        "changes": [{"path": PATH, "before_sha256": BASE_SOURCE_SHA,
                     "after_text": after}],
    }
    return after, proposal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, head = _repository(args.repo)
    output = args.output.resolve(strict=False)
    if output == root or output.is_relative_to(root):
        raise ValueError("review output must be outside the live source checkout")
    # Fail closed BEFORE creating files if the public model artifact or source
    # does not match its full original trial evidence.
    after, proposal = bound(args.artifact.resolve(strict=True), root, head)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = output / "MODEL_BOUND_PROPOSAL.json"
    target.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    receipt = stage(target, root, output / "isolated-review")
    staged_root = Path(receipt["workspace"]).parent
    for name in ("RECEIPT.json", "PATCH_REVIEW.diff"):
        (output / name).write_bytes((staged_root / name).read_bytes())
    origin = {
        "schema": "synapse.evolution.real_model_behavior_handoff.v1",
        "source_commit": head, "original_source_sha256": BASE_SOURCE_SHA,
        "candidate_sha256": sha(after.encode("utf-8")),
        "original_real_model_run": ORIGINAL_TRIAL_RUN,
        "corrected_real_model_run": FEEDBACK_RUN,
        "model_id": MODEL, "pinned_public_revision": REV,
        "initial_model_reply_sha256": ORIGINAL_REPLY_SHA,
        "corrected_model_reply_sha256": CORRECTED_REPLY_SHA,
        "only_model_authored_code_statement": "self.events.clear()",
        "rest_of_patch_trusted_fixed_template": True,
        "baseline_bytes_verified": True,
        "model_origin": "PREVIOUS_PINNED_PUBLIC_CPU_INFERENCE_ARTIFACT",
        "vm_test": "NOT_RUN",
        "production_modified": False,
        "promotion": "OWNER_REVIEW_REQUIRED",
    }
    (output / "ORIGIN_HANDOFF.json").write_text(
        json.dumps(origin, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "SOURCE_AND_MODEL_BOUND": True,
        "candidate_sha256": origin["candidate_sha256"],
        "source_commit": head, "vm_test": "NOT_RUN"
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
