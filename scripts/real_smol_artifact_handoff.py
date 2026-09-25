#!/usr/bin/env python3
"""Proof-preserving handoff of a *real* public SmolLM2 docstring into Stage 2.

The original isolated CPU trial already generated the actual prose. This tool
never calls a model, simulates a reply or invents missing artifacts: it binds
the original byte-for-byte model reply and candidate to the current exact
source-file SHA, and re-stages using the current clean Git HEAD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from synapse.evolution import SCHEMA, _repository, stage

EXPECTED_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
EXPECTED_HUB_REV = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
EXPECTED_RAW_SHA = "8b2f95255b165a817886359dc975fe754738c3e3f0f8457e70f73fcb476ed180"
EXPECTED_SOURCE_SHA = "ee3785e757fed0f52e924831020ad1e57f6184bb33ba3688b38bcab180b19911"
PATH = "src/synapse/debugger.py"
ANCHOR = "    def _trace(self, event: dict[str, Any]) -> None:\n"
GOAL = "Document what Debugger._trace records, without changing executable behavior."


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sentence_from_raw(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("Record and Breakpoint\n\n"):
        raise ValueError("unexpected real-model prose format")
    text = text.removeprefix("Record and Breakpoint\n\n").strip()
    if ("\n" in text or len(text) < 27 or len(text) > 220
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,;.:()/-]{25,219}", text)
            or "event" not in text.lower() or "breakpoint" not in text.lower()
            or not text.endswith(".")):
        raise ValueError("model prose failed independently repeated validation")
    return text


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--artifact", type=Path, required=True)
    cli.add_argument("--repo", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    artifact = args.artifact.resolve(strict=True)
    root, head = _repository(args.repo)
    output = args.output.resolve(strict=False)
    if not output.is_relative_to(root) and output != root:
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
    else:
        raise ValueError("review output must be separate from source tree")
    result = json.loads((artifact / "RESULT.json").read_text(encoding="utf-8"))
    raw = (artifact / "ACTUAL_MODEL_REPLY.txt").read_text(encoding="utf-8")
    old_proposal = json.loads((artifact / "PROPOSAL.json").read_text(encoding="utf-8"))
    if (
        result.get("schema") != "synapse.evolution.smol_doc_trial.v1"
        or result.get("model_id") != EXPECTED_MODEL
        or result.get("hub_revision") != EXPECTED_HUB_REV
        or result.get("raw_reply_sha256") != EXPECTED_RAW_SHA
        or digest(raw.encode("utf-8")) != EXPECTED_RAW_SHA
        or result.get("candidate_staged") is not True
        or result.get("candidate_kind") != "MODEL_SUGGESTED_PROSE_ONLY_TRUSTED_PACKAGING"
        or result.get("production_modified") is not False
        or result.get("passed_vm_evaluation") is not False
        or result.get("original_source_sha256") != EXPECTED_SOURCE_SHA
    ):
        raise ValueError("published model artifact fails pinned provenance checks")
    sentence = sentence_from_raw(raw)
    if sentence != result.get("accepted_docstring"):
        raise ValueError("accepted docstring does not equal actual model bytes")
    current = (root / PATH).read_bytes()
    if digest(current) != EXPECTED_SOURCE_SHA:
        raise ValueError("actual source file differs from original model trial")
    before = current.decode("utf-8")
    if before.count(ANCHOR) != 1:
        raise ValueError("current source does not contain unique method anchor")
    after = before.replace(ANCHOR, ANCHOR + '        """' + sentence + '"""\n')
    old_change = old_proposal.get("changes")
    if not isinstance(old_change, list) or len(old_change) != 1 or (
        old_change[0].get("before_sha256") != EXPECTED_SOURCE_SHA
        or old_change[0].get("path") != PATH
        or old_change[0].get("after_text") != after
    ):
        raise ValueError("trial proposal does not derive byte-for-byte from model artifact")
    renewed = {
        "schema": SCHEMA, "base_commit": head, "goal": GOAL,
        "model_label": EXPECTED_MODEL + " (pinned real local model output; trusted docstring assembly)",
        "changes": [{
            "path": PATH, "before_sha256": EXPECTED_SOURCE_SHA,
            "after_text": after,
        }],
    }
    target = output / "MODEL_BOUND_PROPOSAL.json"
    target.write_text(json.dumps(renewed, indent=2), encoding="utf-8")
    receipt = stage(target, root, output / "staged")
    source = Path(receipt["workspace"]).parent
    handoff = {
        "schema": "synapse.evolution.real_model_handoff.v1",
        "real_model_id": EXPECTED_MODEL,
        "public_model_revision": EXPECTED_HUB_REV,
        "actual_reply_sha256": EXPECTED_RAW_SHA,
        "original_source_sha256": EXPECTED_SOURCE_SHA,
        "candidate_sha256": digest(after.encode("utf-8")),
        "current_review_base_commit": head,
        "original_trial_source_commit": result["source_base_commit"],
        "original_trial_source_commit_differs": head != result["source_base_commit"],
        "matching_source_bytes_verified": True,
        "policy": "DOCSTRING_PROSE_ONLY_TRUSTED_ASSEMBLY_NO_CODE_EXECUTION_UNTIL_VM",
        "model_authored_executable_code": False,
        "vm_evaluation": "NOT_RUN",
        "production_modified": False,
        "auto_promotion": False,
    }
    (output / "ORIGIN_HANDOFF.json").write_text(
        json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "PATCH_REVIEW.diff").write_bytes((source / "PATCH_REVIEW.diff").read_bytes())
    (output / "RECEIPT.json").write_bytes((source / "RECEIPT.json").read_bytes())
    print(json.dumps({
        "source_bytes_match": True,
        "model_reply_sha256": EXPECTED_RAW_SHA,
        "stage1_reviewer_receipt": str(output / "RECEIPT.json"),
        "candidate": "REAL_MODEL_GENERATED_PROSE_ONLY",
        "vm_evaluation": "NOT_RUN",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
