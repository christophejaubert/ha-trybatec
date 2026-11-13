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


@pytest.mark.parametrize("mode", ["none", "linear"])
def test_user_may_confirm_unknown_origin_without_inventing_a_cause(mode):
    """Unknown confirmed is NOT either telemetry failure or manual periodic."""
    result = validate_choice({
        "mode": mode,
        "reason": "undetermined_confirmed",
        "confirmed_unknown_origin": True,
        "updated_at": _FAKE_TIME,
    })
    assert result["reason"] == "undetermined_confirmed"
    assert result["confirmed_unknown_origin"] is True
    assert result["mode"] == mode


@pytest.mark.parametrize("confirmation", [None, False, 0, "true", 1])
def test_unknown_origin_requires_distinct_boolean_confirmation(confirmation):
    payload = {"mode": "linear", "reason": "undetermined_confirmed",
               "updated_at": _FAKE_TIME}
    if confirmation is not None:
        payload["confirmed_unknown_origin"] = confirmation
    with pytest.raises(ValueError, match="explicit confirmation"):
        validate_choice(payload)


def test_confirmation_cannot_be_silently_attached_to_known_origin():
    with pytest.raises(ValueError, match="Known origin"):
        validate_choice({
            "mode": "linear", "reason": "manual_periodic",
            "confirmed_unknown_origin": True, "updated_at": _FAKE_TIME,
        })


def test_legacy_and_explicit_unknown_origin_can_coexist_in_v1_store():
    payload = {
        "version": 1,
        "choices": {
            _FAKE_KEY: {"mode": "none", "reason": "manual_periodic",
                        "updated_at": _FAKE_TIME},
            "b" * 32: {"mode": "linear", "reason": "undetermined_confirmed",
                        "confirmed_unknown_origin": True, "updated_at": _FAKE_TIME},
        },
    }
    before = __import__("copy").deepcopy(payload)
    checked = validate_store(payload)
    assert checked[_FAKE_KEY] == before["choices"][_FAKE_KEY]
    assert checked["b" * 32] == before["choices"]["b" * 32]
    assert payload == before


@pytest.mark.asyncio
async def test_save_choice_rejects_unknown_without_separate_confirm(hass, monkeypatch):
    """No Recorder/Energy import; only synthetic storage for confirmed review."""
    from custom_components.trybatec import history_smoothing_store as store

    # A test-local memory Store, not a production HA persistence operation.
    class MemoryStore:
        def __init__(self):
            self.current = None

        async def async_load(self):
            return self.current

        async def async_save(self, data):
            self.current = data

    fake = MemoryStore()
    monkeypatch.setattr(store, "_store", lambda _hass, _entry: fake)
    with pytest.raises(ValueError, match="separate, explicit approval"):
        await store.save_choice(
            hass, "synthetic-entry", _FAKE_KEY,
            mode="linear", reason="undetermined_confirmed",
        )
    assert fake.current is None
    result = await store.save_choice(
        hass, "synthetic-entry", _FAKE_KEY,
        mode="linear", reason="undetermined_confirmed",
        confirm_unknown_origin=True,
    )
    assert result[_FAKE_KEY]["reason"] == "undetermined_confirmed"
    assert result[_FAKE_KEY]["confirmed_unknown_origin"] is True
    assert validate_store(fake.current) == result


@pytest.mark.asyncio
async def test_explicit_unknown_confirmation_cannot_modify_known_legacy_reason(
    hass, monkeypatch,
):
    from custom_components.trybatec import history_smoothing_store as store

    class MemoryStore:
        def __init__(self):
            self.current = {"version": 1, "choices": {
                _FAKE_KEY: {"mode": "linear", "reason": "manual_periodic",
                            "updated_at": _FAKE_TIME},
            }}
        async def async_load(self):
            return self.current
        async def async_save(self, data):
            self.current = data

    fake = MemoryStore()
    monkeypatch.setattr(store, "_store", lambda _hass, _entry: fake)
    with pytest.raises(ValueError, match="conflicts with known reason"):
        await store.save_choice(
            hass, "synthetic-entry", _FAKE_KEY,
            mode="linear", reason="manual_periodic",
            confirm_unknown_origin=True,
        )
    assert fake.current["choices"][_FAKE_KEY]["reason"] == "manual_periodic"
