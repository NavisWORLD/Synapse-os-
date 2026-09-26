#!/usr/bin/env python3
"""Rebind exact pinned genuine model output to a NEW clean development source HEAD.

No model is contacted, source patch is never executed on the host, and no
untrusted artifact metadata is trusted without independent known byte pins.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from synapse.evolution import SCHEMA, _repository, stage
from synapse.evolution_model import prepare
from scripts.real_model_snapshot_trial import (
    MODEL, REVISION, PATH, GOAL, package
)

HISTORICAL_RUN=36213993540
HISTORICAL_COMMIT="84c4dcad3e22031f0832e61c1f38de4391f9a00b"
MODEL_VERDICT_SHA="3de47fec9a72db7ecab9f23e39d6d168072f6c0cc487216e0f83c6bad2679402"
RAW1_SHA="c3140bd5664824fecd79e8f5236f4105eab5d80fe4a46b943a5dc42329d86e82"
RAW2_SHA="8eb36aa479b37478e510e16edebd700cee75692a98b68697a97c564ceee31fd0"
BASE_SHA="4855aa5be41c3581f4e37e22384915b736c1b7c7d15140bd66d5460c806ea8ee"
CANDIDATE_SHA="38848291aa12bf5491dd981ff1d896c5c850ebfe0f598db3b61118b84c7e6076"
REVIEW_PATCH_SHA="2a0be4a718f2fef8371f128a802bbf0a3930fe6bd073f6ebbfc012d8a182e314"

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def from_exact_artifact(folder: Path) -> tuple[str, str, dict]:
    files={
        "TRIAL_VERDICT.json":MODEL_VERDICT_SHA,
        "ACTUAL_MODEL_TURN_1.txt":RAW1_SHA,
        "ACTUAL_MODEL_TURN_2.txt":RAW2_SHA,
        "PATCH_REVIEW.diff":REVIEW_PATCH_SHA,
    }
    blobs={}
    for name,expected in files.items():
        path=folder/name
        if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= 4096:
            raise ValueError("actual pinned original artifact member missing or unsafe")
        data=path.read_bytes()
        if sha(data)!=expected:
            raise ValueError("historical model transcript or reviewer artifact digest mismatch")
        blobs[name]=data
    verdict=json.loads(blobs["TRIAL_VERDICT.json"])
    if (
        verdict.get("schema")!="synapse.evolution.real_snapshot_trial.v1"
        or verdict.get("model_id")!=MODEL
        or verdict.get("model_revision")!=REVISION
        or verdict.get("source_commit")!=HISTORICAL_COMMIT
        or verdict.get("candidate_staged") is not True
        or verdict.get("accepted_turn")!=2
        or verdict.get("raw_model_turns")!=2
        or verdict.get("raw_turn_1_sha256")!=RAW1_SHA
        or verdict.get("raw_turn_2_sha256")!=RAW2_SHA
        or verdict.get("baseline_source_sha256")!=BASE_SHA
        or verdict.get("candidate_source_sha256")!=CANDIDATE_SHA
        or verdict.get("production_modified") is not False
        or verdict.get("promotion")!="OWNER_REVIEW_REQUIRED"
    ):
        raise ValueError("historical model verdict disagrees with independently pinned bytes")
    raw1=blobs["ACTUAL_MODEL_TURN_1.txt"].decode("utf-8")
    raw2=blobs["ACTUAL_MODEL_TURN_2.txt"].decode("utf-8")
    return raw1,raw2,verdict

def handoff(artifact: Path, repo: Path, out: Path) -> dict:
    root,head=_repository(repo)
    target=out.resolve(strict=False)
    if target==root or target.is_relative_to(root):
        raise ValueError("output must be outside the code repository")
    raw1,raw2,verdict=from_exact_artifact(artifact.resolve(strict=True))
    baseline=(root/PATH).read_text(encoding="utf-8")
    packet=prepare(root,GOAL,PATH)
    if packet["before_sha256"]!=BASE_SHA:
        raise ValueError("candidate would be built from a different debugger baseline")
    # Prove original model was genuinely rejected, do not hide first-turn error.
    try:
        package(raw1,baseline)
    except ValueError:
        pass
    else:
        raise ValueError("original first-turn rejection could not be reproduced")
    statement,note,after=package(raw2,baseline)
    if sha(after.encode("utf-8"))!=CANDIDATE_SHA:
        raise ValueError("trusted assembly produced an unexpected candidate")
    target.mkdir(parents=True,mode=0o700,exist_ok=True)
    proposal={
        "schema":SCHEMA,
        "base_commit":head,
        "goal":GOAL,
        "model_label":MODEL+" (exact pinned one-line model output, fixed template)",
        "changes":[{
            "path":PATH,"before_sha256":BASE_SHA,"after_text":after,
        }],
    }
    review_file=target/"REBOUND_PINNED_MODEL_PROPOSAL.json"
    if review_file.exists():
        raise ValueError("reuse a fresh output directory")
    review_file.write_text(json.dumps(proposal,indent=2,sort_keys=True)+"\n")
    receipt=stage(review_file,root,target/"staged")
    stage_dir=Path(receipt["workspace"]).parent
    patch=(stage_dir/"PATCH_REVIEW.diff").read_bytes()
    if sha(patch)!=REVIEW_PATCH_SHA:
        raise ValueError("rebound patch differs from reviewed historical source delta")
    for name in ("PATCH_REVIEW.diff","RECEIPT.json"):
        (target/name).write_bytes((stage_dir/name).read_bytes())
    handoff={
        "schema":"synapse.evolution.snapshot_rebound.v1",
        "historical_model_run":HISTORICAL_RUN,
        "historical_source_commit":HISTORICAL_COMMIT,
        "new_source_commit":head,
        "historical_verdict_sha256":MODEL_VERDICT_SHA,
        "first_actual_model_turn_sha256":RAW1_SHA,
        "accepted_actual_model_turn_sha256":RAW2_SHA,
        "only_model_authored_statement":statement,
        "first_turn_rejection_reproduced":True,
        "candidate_sha256":CANDIDATE_SHA,
        "rebound_stage_patch_sha256":REVIEW_PATCH_SHA,
        "tests":"NOT_RUN","vm_result":"NOT_RUN",
        "production_modified":False,"promotion":"OWNER_REVIEW_REQUIRED",
    }
    (target/"ORIGIN_HANDOFF.json").write_text(json.dumps(handoff,indent=2,sort_keys=True)+"\n")
    return handoff

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--artifact",type=Path,required=True)
    cli.add_argument("--repo",type=Path,required=True)
    cli.add_argument("--output",type=Path,required=True)
    a=cli.parse_args()
    receipt=handoff(a.artifact,a.repo,a.output)
    print("PINNED_ACTUAL_MODEL_HANDOFF_PASS",receipt["new_source_commit"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
