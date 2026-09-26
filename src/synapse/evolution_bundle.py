"""Stage 3.5: verify the EXACT historical review artifact offline before display.

Pinning bytes in the source tree is a local trust anchor, NOT a GitHub digital
signature or an authorization to merge, run patches, grant tools, or update OS.
The only supported bundle is the historical Qwen statement-correction case.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

from . import evolution_review as historical

SCHEMA = "synapse.evolution.pinned_archive_review.v1"
MAX_ZIP_BYTES = 1_048_576
MAX_TOTAL_BYTES = 400_000
# Hashes obtained from the independently successful immutable artifact
# synapse-evolution-owner-review-bundle, run 36189003354, artifact 10887595798.
# Pin member bytes rather than ZIP container bytes to permit transport re-ZIP.
PINNED_FILES = {
    "ACTUAL_MODEL_CORRECTION.txt": "8723342b9531a7ae1e13d1ade26b8bdaec17aa5bb10f3776235fb554fa477fa1",
    "COMPARISON.json": "842af134691dfd83200b323c51734a9907c4e088713b7299e03c3f1cf6d8a412",
    "ORIGINAL_DEBUGGER_BASELINE.py.txt": "4a771d51fb717cc094f33a0e5852686b5deeac8f295bb8d7d633332fe7a74d43",
    "ORIGIN_HANDOFF.json": "df7784e3a95c4ae680ddd1cc4eadc6bfd286b6ab62c5382d88c8a47e0e47261c",
    "REVIEW_BUNDLE.json": "4bd9c026bce6b89fcec98a543fd2c23c791249b83e9d426747abdb6ca801120e",
    "ROLLBACK_PREVIEW.diff": "39299215f525b8c62db55c413e08d62f6f3cb662e5d13ab65e926b76a72e2975",
    "SHA256SUMS": "28bee69eb683c1950b2af51e2c940c02c7c7cf29973211ed66816fe3ee900fdd",
    "STAGED_PATCH_RECEIPT.json": "94d13d7afd176e3ed106bd7fbe9cbd30c951feb1ad20ac4f79da212d707245a0",
    "VERIFIED_CANDIDATE_CI.json": "df45743da26b4209ae20c555062e67161546eac4df2c415cb75a32c6f24bf570",
}
SOURCE = Path("src/synapse/debugger.py")
ARTIFACT_RUN = 36189003354


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _as_object(blob: bytes, label: str) -> dict:
    try:
        data = json.loads(blob)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid pinned JSON: " + label) from exc
    if not isinstance(data, dict):
        raise ValueError("expected JSON object: " + label)
    return data


def verify_pinned_archive(archive: Path, installed_debugger: Path) -> dict:
    """Read and hash known archive members; never extract, execute or write."""
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("archive must be an existing regular non-symlink file")
    if not 1 <= archive.stat().st_size <= MAX_ZIP_BYTES:
        raise ValueError("archive exceeds pinned import limits")
    if installed_debugger.is_symlink() or not installed_debugger.is_file():
        raise ValueError("installed debugger source unavailable or symlinked")
    if installed_debugger.stat().st_size > 64_000:
        raise ValueError("installed debugger exceeds source size limit")
    if _sha(installed_debugger.read_bytes()) != historical.CANDIDATE_SOURCE_SHA:
        raise ValueError("installed source differs from exact reviewed candidate")

    try:
        with zipfile.ZipFile(archive, "r", allowZip64=False) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(infos) != len(PINNED_FILES) or set(names) != set(PINNED_FILES):
                raise ValueError("archive has missing, duplicate or extra entries")
            if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
                raise ValueError("archive expands beyond pinned budget")
            blobs = {}
            for item in infos:
                mode = (item.external_attr >> 16) & 0o170000
                if (item.is_dir() or item.flag_bits & 1 or
                        mode not in (0, stat.S_IFREG) or
                        item.file_size < 1 or item.file_size > 128_000 or
                        item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError("unsafe archive entry")
                blob = z.read(item, pwd=None)
                if len(blob) != item.file_size or _sha(blob) != PINNED_FILES[item.filename]:
                    raise ValueError("archive member does not match independently pinned bytes")
                blobs[item.filename] = blob
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, EOFError) as exc:
        raise ValueError("unreadable or unsupported review archive") from exc

    checksums = blobs["SHA256SUMS"].decode("ascii", errors="strict").splitlines()
    checksum_map = {}
    for line in checksums:
        if not re.fullmatch(r"[a-f0-9]{64}  [A-Za-z0-9_.-]+", line):
            raise ValueError("unexpected checksum manifest record")
        sha, name = line.split("  ", 1)
        if name in checksum_map:
            raise ValueError("duplicate checksum manifest member")
        checksum_map[name] = sha
    expected = {k: v for k, v in PINNED_FILES.items() if k != "SHA256SUMS"}
    if checksum_map != expected:
        raise ValueError("manifest differs from independent historical pin")

    bundle = _as_object(blobs["REVIEW_BUNDLE.json"], "REVIEW_BUNDLE.json")
    ci = _as_object(blobs["VERIFIED_CANDIDATE_CI.json"], "VERIFIED_CANDIDATE_CI.json")
    comparison = _as_object(blobs["COMPARISON.json"], "COMPARISON.json")
    origin = _as_object(blobs["ORIGIN_HANDOFF.json"], "ORIGIN_HANDOFF.json")
    if (bundle.get("schema") != historical.SCHEMA
            or bundle.get("candidate_sha256") != historical.CANDIDATE_SOURCE_SHA
            or bundle.get("original_sha256") != historical.ORIGINAL_SOURCE_SHA
            or bundle.get("model_revision") != historical.REV
            or bundle.get("model_id") != historical.MODEL
            or bundle.get("original_model_run") != historical.ORIGINAL_RUN
            or bundle.get("feedback_model_run") != historical.FEEDBACK_RUN
            or bundle.get("two_disconnected_vm_run") != historical.TWO_VM_RUN
            or bundle.get("successful_candidate_ci_run") != historical.FULL_CI_RUN
            or bundle.get("production_modified") is not False
            or bundle.get("automated_merge") is not False
            or bundle.get("rollback_preview_sha256") != PINNED_FILES["ROLLBACK_PREVIEW.diff"]
            or bundle.get("review_status") != "SOURCE_AND_PRIOR_TESTS_VERIFIED_OWNER_DECISION_REQUIRED"):
        raise ValueError("pinned review claims fail historical checks")
    if (ci.get("run_id") != historical.FULL_CI_RUN
            or ci.get("head_sha") != historical.FULL_CI_HEAD
            or ci.get("conclusion") != "success"
            or comparison.get("networking") != "DISABLED_BY_QEMU_-nic_none"
            or comparison.get("production_modified") is not False
            or origin.get("only_model_authored_code_statement") != "self.events.clear()"):
        raise ValueError("pinned CI, VM, or model origin fields inconsistent")
    return {
        "schema": SCHEMA,
        "status": "PINNED_HISTORICAL_ARTIFACT_AND_LOCAL_SOURCE_MATCH",
        "historical_artifact_run": ARTIFACT_RUN,
        "candidate_sha256": historical.CANDIDATE_SOURCE_SHA,
        "model_id": historical.MODEL,
        "model_authored_scope": "ONE_CORRECTED_STATEMENT_NOT_COMPLETE_PATCH",
        "vm_runs": historical.TWO_VM_RUN,
        "full_candidate_ci_run": historical.FULL_CI_RUN,
        "checked_members": len(PINNED_FILES),
        "bundle_member_sha256": PINNED_FILES["REVIEW_BUNDLE.json"],
        "cryptographic_github_signature_established": False,
        "production_modified": False,
        "owner_approval_required": True,
    }
