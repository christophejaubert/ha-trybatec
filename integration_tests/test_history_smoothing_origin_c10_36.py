"""#36/#155 C10: an unknown origin is a draft, not an approved reason.

Synthetic-only validation: never opens Recorder or Energy or a real vendor API.
"""
from __future__ import annotations

import pytest

from custom_components.trybatec.history_smoothing_store import (
    validate_choice,
    validate_store,
)


_FAKE_TIME = "2026-11-01T12:00:00+00:00"
_FAKE_KEY = "a" * 32


@pytest.mark.parametrize("mode", ["none", "linear"])
@pytest.mark.parametrize(
    "unknown", ["undetermined", "unknown", "unknown_manual_or_automatic", ""],
)
def test_unknown_origin_cannot_be_persisted_as_approved_decision(mode, unknown):
    """The frontend sentinel must never be rewritten as manual_periodic."""
    with pytest.raises(ValueError, match="Unsupported sparse interval"):
        validate_choice({
            "mode": mode, "reason": unknown, "updated_at": _FAKE_TIME,
        })


def test_confirmed_legacy_manual_and_telemetry_reasons_remain_unchanged():
    """Never migrate an approved old reason into a different declaration."""
    payload = {
        "version": 1,
        "choices": {
            _FAKE_KEY: {
                "mode": "linear",
                "reason": "manual_periodic",
                "updated_at": _FAKE_TIME,
            },
            "b" * 32: {
                "mode": "none",
                "reason": "telemetry_failure",
                "updated_at": _FAKE_TIME,
            },
        },
    }
    loaded = validate_store(payload)
    assert loaded[_FAKE_KEY]["reason"] == "manual_periodic"
    assert loaded["b" * 32]["reason"] == "telemetry_failure"
    assert loaded[_FAKE_KEY]["mode"] == "linear"
    assert loaded["b" * 32]["mode"] == "none"


def test_no_default_decision_is_stored_for_unreviewed_interval():
    assert validate_store(None) == {}
    assert validate_store({"version": 1, "choices": {}}) == {}


@pytest.mark.parametrize("mode", ["none", "linear"])
def test_only_explicit_known_reason_survives_validation(mode):
    for reason in ("manual_periodic", "telemetry_failure", "other"):
        valid = validate_choice({
            "mode": mode, "reason": reason, "updated_at": _FAKE_TIME,
        })
        assert valid["mode"] == mode
        assert valid["reason"] == reason
        assert valid["updated_at"] == _FAKE_TIME


def test_unqualified_legacy_decision_is_rejected_not_migrated():
    with pytest.raises(ValueError, match="Unsupported sparse interval"):
        validate_store({
            "version": 1,
            "choices": {
                _FAKE_KEY: {
                    "mode": "linear",
                    "reason": "undetermined",
                    "updated_at": _FAKE_TIME,
                },
            },
        })
