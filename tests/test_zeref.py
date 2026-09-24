import json

import pytest

from synapse.zeref import resolve_resident_state, validate_ibm_receipt


def receipt(**overrides):
    value = {
        "schema": "synapse.zeref.ibm-receipt.v1",
        "authenticated": True,
        "backend": "ibm_marrakesh",
        "job_id": "job-123",
        "job_status": "DONE",
        "source": "ibm-runtime",
        "generated_at": 1000,
        "expires_at": 2000,
        "entropy12": [0.0] * 12,
        "entropy_source_sha256": "a" * 64,
        "counts_sha256": "b" * 64,
        "secret_exposed_to_subject": False,
    }
    value.update(overrides)
    return value


def test_valid_receipt_reports_freshness_without_exposing_secret():
    out = validate_ibm_receipt(receipt(), now=1500)
    assert out["fresh"] is True
    assert out["secret_exposed_to_subject"] is False
    assert "entropy12" in out


def test_stale_receipt_is_valid_but_not_fresh():
    out = validate_ibm_receipt(receipt(), now=2500)
    assert out["fresh"] is False


def test_receipt_rejects_secret_like_fields():
    with pytest.raises(ValueError, match="secret-like"):
        validate_ibm_receipt(receipt(api_token="nope"), now=1500)


def test_receipt_rejects_exposed_subject_flag():
    with pytest.raises(ValueError, match="secret_exposed_to_subject"):
        validate_ibm_receipt(receipt(secret_exposed_to_subject=True), now=1500)


def test_resident_state_is_fail_soft_without_ibm():
    assert resolve_resident_state(runtime_ok=True, native_ok=True, receipt=None) == "READY_NO_IBM"
    assert resolve_resident_state(runtime_ok=False, native_ok=False, receipt=None) == "DEGRADED"


def test_resident_state_distinguishes_stale_and_fresh_ibm():
    fresh = validate_ibm_receipt(receipt(), now=1500)
    stale = validate_ibm_receipt(receipt(), now=2500)
    assert resolve_resident_state(runtime_ok=True, native_ok=True, receipt=fresh) == "READY"
    assert resolve_resident_state(runtime_ok=True, native_ok=True, receipt=stale) == "READY_STALE_IBM"
