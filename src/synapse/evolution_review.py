"""Stage 3: read-only, fail-closed review of a previously recorded model+VM trial.

This module never checks out patches, runs model code, sends credentials,
merges a PR, installs software, or changes the machine. The pinned audit
is deliberately limited to the *actual* reviewed debugger experiment.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "synapse.evolution.owner_review.v1"
MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
REV = "ea99d3edbfc6669b8b24cbaa6a98ec0e857f0155"
ORIGINAL_RUN = 36150437142
FEEDBACK_RUN = 36150869207
TWO_VM_RUN = 36151721750
FULL_CI_RUN = 36154999097
FULL_CI_HEAD = "f851993d0737a8c218c06c5792b7688b125a5f2c"
ORIGINAL_REPLY_SHA = "740ae1c0ac1b46879e00052751e08a7c506df76dcc288bfd79c9f3d5bc0a36fc"
CORRECTED_REPLY_SHA = "8723342b9531a7ae1e13d1ade26b8bdaec17aa5bb10f3776235fb554fa477fa1"
ORIGINAL_SOURCE_SHA = "4a771d51fb717cc094f33a0e5852686b5deeac8f295bb8d7d633332fe7a74d43"
CANDIDATE_SOURCE_SHA = "4855aa5be41c3581f4e37e22384915b736c1b7c7d15140bd66d5460c806ea8ee"
SOURCE = Path("src/synapse/debugger.py")
OLD = "    def run(self) -> dict[str, Any]:\n"
NEW = (
    "    def run(self, *, reset_events: bool = False) -> dict[str, Any]:\n"
    "        if reset_events:\n"
    "            self.events.clear()\n"
)
ARTIFACT_FILES = (
    "ORIGIN_HANDOFF.json", "COMPARISON.json", "STAGED_PATCH_RECEIPT.json",
    "STAGED_PATCH_REVIEW.diff", "ORIGINAL_REAL_MODEL_FEEDBACK.json",
    "ORIGINAL_REJECTED_MODEL_REPLY.txt", "ACTUAL_MODEL_CORRECTION.txt",
)
HEX = re.compile("[a-f0-9]{64}\\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, name: str, limit: int = 300_000) -> bytes:
    item = root / name
    if root.is_symlink() or item.is_symlink() or not item.is_file():
        raise ValueError("artifact is missing, symlinked or not a regular file: " + name)
    size = item.stat().st_size
    if size < 1 or size > limit:
        raise ValueError("artifact size limit: " + name)
    return item.read_bytes()


def _json(root: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(_read(root, name))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("artifact JSON is invalid: " + name) from exc
    if not isinstance(value, dict):
        raise ValueError("artifact JSON must be an object")
    return value


def _must(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError("owner-review gate rejected: " + reason)


def verify(artifact: Path, candidate_repo: Path, ci_run: Path) -> tuple[dict, bytes, str]:
    """Validate pinned source/VM/provenance and release candidate CI metadata."""
    artifact = artifact.resolve(strict=True)
    source = candidate_repo.resolve(strict=True) / SOURCE
    _must(source.is_file() and not source.is_symlink(), "candidate source unavailable")
    current = source.read_bytes()
    _must(digest(current) == CANDIDATE_SOURCE_SHA, "candidate not exact reviewed bytes")
    current_text = current.decode("utf-8")
    _must(current_text.count(NEW) == 1 and OLD not in current_text,
          "candidate shape differs from exact reviewed transformation")
    previous_text = current_text.replace(NEW, OLD)
    previous = previous_text.encode("utf-8")
    _must(digest(previous) == ORIGINAL_SOURCE_SHA, "inferred baseline bytes differ")

    origin = _json(artifact, "ORIGIN_HANDOFF.json")
    correction = _json(artifact, "ORIGINAL_REAL_MODEL_FEEDBACK.json")
    receipt = _json(artifact, "STAGED_PATCH_RECEIPT.json")
    comparison = _json(artifact, "COMPARISON.json")
    first_reply = _read(artifact, "ORIGINAL_REJECTED_MODEL_REPLY.txt", 1024)
    second_reply = _read(artifact, "ACTUAL_MODEL_CORRECTION.txt", 1024)
    review_diff = _read(artifact, "STAGED_PATCH_REVIEW.diff")

    _must(origin.get("schema") == "synapse.evolution.real_model_behavior_handoff.v1"
          and origin.get("model_id") == MODEL
          and origin.get("pinned_public_revision") == REV
          and origin.get("original_real_model_run") == ORIGINAL_RUN
          and origin.get("corrected_real_model_run") == FEEDBACK_RUN
          and origin.get("initial_model_reply_sha256") == ORIGINAL_REPLY_SHA
          and origin.get("corrected_model_reply_sha256") == CORRECTED_REPLY_SHA
          and origin.get("original_source_sha256") == ORIGINAL_SOURCE_SHA
          and origin.get("candidate_sha256") == CANDIDATE_SOURCE_SHA
          and origin.get("only_model_authored_code_statement") == "self.events.clear()"
          and origin.get("rest_of_patch_trusted_fixed_template") is True
          and origin.get("baseline_bytes_verified") is True
          and origin.get("production_modified") is False
          and origin.get("promotion") == "OWNER_REVIEW_REQUIRED",
          "model origin handoff does not match pinned prior run")
    _must(digest(first_reply) == ORIGINAL_REPLY_SHA
          and digest(second_reply) == CORRECTED_REPLY_SHA
          and second_reply.strip() == b"\x60\x60\x60python\nself.events.clear()\n\x60\x60\x60",
          "genuine feedback text or hashes do not match")
    _must(correction.get("schema") == "synapse.evolution.coder_feedback_trial.v1"
          and correction.get("model_id") == MODEL
          and correction.get("model_revision") == REV
          and correction.get("source_sha256") == ORIGINAL_SOURCE_SHA
          and correction.get("candidate_sha256") == CANDIDATE_SOURCE_SHA
          and correction.get("prior_run") == ORIGINAL_RUN
          and correction.get("prior_raw_sha256") == ORIGINAL_REPLY_SHA
          and correction.get("feedback_reply_sha256") == CORRECTED_REPLY_SHA
          and correction.get("candidate_staged") is True
          and correction.get("statement_passed_exact_review") is True
          and correction.get("model_wrote_complete_patch") is False
          and correction.get("normalization") == "STRIPPED_ONLY_SINGLE_CODE_FENCE"
          and correction.get("production_modified") is False,
          "feedback experiment receipt failed provenance gates")

    changes = receipt.get("changes")
    _must(receipt.get("schema") == "synapse.evolution.receipt.v1"
          and isinstance(changes, list) and len(changes) == 1
          and changes[0].get("path") == SOURCE.as_posix()
          and changes[0].get("before_sha256") == ORIGINAL_SOURCE_SHA
          and changes[0].get("after_sha256") == CANDIDATE_SOURCE_SHA
          and receipt.get("base_commit") == origin.get("source_commit")
          and HEX.fullmatch(str(receipt.get("patch_sha256", ""))) is not None
          and digest(review_diff) == receipt.get("patch_sha256")
          and receipt.get("production_modified") is False
          and receipt.get("promotion") == "OWNER_REVIEW_REQUIRED",
          "Stage 1 receipt or actual stored diff does not match")
    # The patch is review-only. Check that it is the exact one-file change
    # rather than relying solely on a self-asserted receipt and hash.
    _must(review_diff.startswith(b"diff --git a/src/synapse/debugger.py b/src/synapse/debugger.py\n")
          and b"diff --git " not in review_diff.split(b"\n", 1)[1]
          and b"+            self.events.clear()" in review_diff,
          "review diff contains unauthorized changes")

    _must(comparison.get("schema") == "synapse.evolution.vm.comparison.v1"
          and comparison.get("base_commit") == origin.get("source_commit")
          and comparison.get("receipt_patch_sha256") == receipt["patch_sha256"]
          and comparison.get("functional_comparison")
          == "INDEPENDENT_DEBUGGER_DEFAULT_AND_OPT_IN_REGRESSION"
          and comparison.get("networking") == "DISABLED_BY_QEMU_-nic_none"
          and comparison.get("qemu_acceleration") == "TCG_ONLY"
          and comparison.get("production_modified") is False
          and comparison.get("candidate_executed_on_host") is False
          and comparison.get("host_secrets_sent") is False
          and comparison.get("promotion") == "OWNER_REVIEW_REQUIRED"
          and comparison.get("smoke_only_not_performance_proof") is True,
          "Stage 2 run receipts do not meet limited two-guest contract")
    durations = {}
    for mode in ("baseline", "candidate"):
        item = comparison.get(mode)
        _must(isinstance(item, dict)
              and item.get("role") == mode
              and item.get("source_commit") == origin.get("source_commit")
              and item.get("schema") == "synapse.evolution.vm.guest_result.v1"
              and item.get("verified_source_hashes") is True
              and item.get("network_policy") == "HOST_QEMU_NIC_DISABLED"
              and item.get("production_modified") is False
              and item.get("candidate_files_applied") is (mode == "candidate"),
              "missing genuine separate " + mode + " guest receipt")
        checks = item.get("checks")
        _must(isinstance(checks, dict) and set(checks)
              == {"status", "doctor", "debugger_contract"}
              and all(isinstance(c, dict) and c.get("passed") is True
                      for c in checks.values())
              and checks["debugger_contract"].get("default_behavior_preserved") is True
              and checks["debugger_contract"].get("role_specific_expectation_met") is True,
              "guest functional checks were not independently completed")
        durations[mode] = {name: checks[name].get("duration_ms")
                           for name in ("status", "doctor", "debugger_contract")}

    ci = _json(ci_run.parent, ci_run.name)
    _must(ci.get("id") == FULL_CI_RUN and ci.get("head_sha") == FULL_CI_HEAD
          and ci.get("conclusion") == "success" and ci.get("status") == "completed"
          and ci.get("head_branch") == "feature/synapse-reviewed-debugger-reset-011"
          and ci.get("repository", {}).get("full_name") == "NavisWORLD/Synapse-os-",
          "exact candidate's full CI was not independently confirmed")
    rollback_diff = "".join(difflib.unified_diff(
        current_text.splitlines(keepends=True),
        previous_text.splitlines(keepends=True),
        fromfile="a/src/synapse/debugger.py (reviewed candidate)",
        tofile="b/src/synapse/debugger.py (original baseline)",
        lineterm="\n",
    ))
    bundle = {
        "schema": SCHEMA,
        "model_id": MODEL,
        "model_revision": REV,
        "model_authored_scope": "ONE_FEEDBACK_CORRECTED_STATEMENT_ONLY",
        "trusted_template_used": True,
        "original_model_run": ORIGINAL_RUN,
        "feedback_model_run": FEEDBACK_RUN,
        "two_disconnected_vm_run": TWO_VM_RUN,
        "successful_candidate_ci_run": FULL_CI_RUN,
        "successful_candidate_ci_sha": FULL_CI_HEAD,
        "source_path": SOURCE.as_posix(),
        "candidate_sha256": digest(current),
        "original_sha256": digest(previous),
        "staged_review_patch_sha256": digest(review_diff),
        "two_vm_checks": {
            "baseline": sorted(comparison["baseline"]["checks"]),
            "candidate": sorted(comparison["candidate"]["checks"]),
        },
        "guest_timings_ms_observational_only": durations,
        "no_performance_comparison_claimed": True,
        "isolated_trial_recorded_network_off": True,
        "rollback_preview_sha256": digest(rollback_diff.encode("utf-8")),
        "automated_merge": False,
        "production_modified": False,
        "review_status": "SOURCE_AND_PRIOR_TESTS_VERIFIED_OWNER_DECISION_REQUIRED",
        "review_limit": (
            "Prior successful checks do not validate this new review UI or "
            "prove that external JSON was signed by GitHub; use pinned run links."
        ),
    }
    return bundle, previous, rollback_diff


def write_review(artifact: Path, repo: Path, ci_run: Path, output: Path) -> dict:
    bundle, previous, rollback_diff = verify(artifact, repo, ci_run)
    output = output.resolve(strict=False)
    repo_root = repo.resolve(strict=True)
    if output == repo_root or output.is_relative_to(repo_root):
        raise ValueError("review output must live outside the source repository")
    if output.is_symlink():
        raise ValueError("review output cannot be a symlink")
    if output.exists() and any(output.iterdir()):
        raise ValueError("review output must be a new or empty directory")
    output.mkdir(parents=True, mode=0o700, exist_ok=True)
    (output / "ROLLBACK_PREVIEW.diff").write_text(rollback_diff, encoding="utf-8")
    (output / "ORIGINAL_DEBUGGER_BASELINE.py.txt").write_bytes(previous)
    (output / "REVIEW_BUNDLE.json").write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return bundle


def review_display(bundle: object) -> str:
    """Safe informational display of an untrusted imported receipt; no granting."""
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA:
        raise ValueError("unsupported evolution review receipt")
    checks = bundle.get("two_vm_checks")
    if not isinstance(checks, dict):
        raise ValueError("receipt has no declared VM evidence")
    fields = [
        ("Candidate", bundle.get("source_path")),
        ("Model label", bundle.get("model_id")),
        ("Model-authored scope", bundle.get("model_authored_scope")),
        ("Baseline checks", ", ".join(checks.get("baseline", []))
         if isinstance(checks.get("baseline"), list) else "not established"),
        ("Candidate checks", ", ".join(checks.get("candidate", []))
         if isinstance(checks.get("candidate"), list) else "not established"),
        ("Source hash", bundle.get("candidate_sha256")),
        ("Review status", "READ ONLY — requires independent approval"),
    ]
    # This file is only a display: no path/command execution, no trust elevation.
    return "\n".join(f"{label}: {str(value)[:150]}" for label, value in fields)

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Verify pinned model-assisted debugger source and real VM receipts for read-only owner review"
    )
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--ci-run-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = write_review(args.artifact, args.repo, args.ci_run_json, args.output)
    print(json.dumps({
        "schema": result["schema"],
        "review_status": result["review_status"],
        "candidate_sha256": result["candidate_sha256"],
        "production_modified": result["production_modified"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
