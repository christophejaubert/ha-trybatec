"""Synthetic estimated-origin panel previews; no measured index is fabricated."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from zoneinfo import ZoneInfo

from custom_components.trybatec import panel_origin

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")
PARIS = ZoneInfo("Europe/Paris")
START = date(2021, 1, 1)
FIRST = datetime(2022, 1, 20, 10, 0, tzinfo=PARIS)


def _case(monkeypatch, *, readings=None, unit="m³", conflicts=False, zero_times=()):
    m = {
        "reviewed_readings": readings if readings is not None else [(FIRST, 332.0)],
        "portal_unit": "m³",
        "conflicts": ["synthetic conflict"] if conflicts else [],
        "fatal_conflicts": [],
        "unreviewed_zero_times": zero_times,
        "qualified_zero_times": [],
        # A synthetic, stable digest shaped like the real build_history source proof.
        "source_fingerprint": "a" * 64,
    }
    payloads = [{"synthetic": "not a real API reading"}]
    coord = SimpleNamespace(
        entry=SimpleNamespace(entry_id="ci-estimated-origin", options={}),
        _history_review_cache=(payloads, START, date(2022, 2, 1), {"LOT"}),
    )
    monkeypatch.setattr(panel_origin, "load_decisions",
                        AsyncMock(return_value={}))
    monkeypatch.setattr(panel_origin, "build_history",
                        lambda *_args, **_kwargs: {
                            "__physical_meters__": {("LOT", "EF", "METER"): m}
                        })
    monkeypatch.setattr(panel_origin, "resolve_meter_unit",
                        lambda *_args: unit)
    return coord, m


def _preview(hass, coord, **overrides):
    kwargs={
        "lot": "LOT", "fluid": "EF", "serial": "METER",
        "estimated_start_date": "2021-12-22",
        "estimated_start_index": 316.0,
        "confirm": True,
    }
    kwargs.update(overrides)
    return panel_origin.preview_first_observed_meter(hass, coord, **kwargs)


@pytest.mark.asyncio
async def test_estimated_origin_preserves_raw_index_and_total(monkeypatch):
    coord, raw = _case(monkeypatch)
    before = dict(raw)
    result = await _preview(object(), coord)
    assert result["status"] == "estimated_origin_preview_only"
    assert result["origin"] == "estimated_confirmed"
    assert result["total"] == 16.0
    assert result["estimated_total"] == 16.0
    assert result["measured_total"] == 0
    assert result["first_observed_index"] == 332.0
    assert result["estimated_initial_index"] == 316.0
    assert result["first_observed_at"] == FIRST.isoformat()
    assert result["origin_is_not_a_measured_reading"] is True
    assert result["saved_decision"] is False
    assert result["recorder_writes"] is False
    assert result["energy_writes"] is False
    assert len(result["daily_preview"]) == 29
    assert sum(x["quantity"] for x in result["daily_preview"]) == pytest.approx(16.0)
    assert raw == before


@pytest.mark.asyncio
@pytest.mark.parametrize("parameters,message", [
    ({"confirm": False}, "acceptance"),
    ({"estimated_start_date": "2020-01-01"}, "Re-run"),
    ({"estimated_start_date": "2022-01-20"}, "precede"),
    ({"estimated_start_date": "2022-02-01"}, "precede"),
    ({"estimated_start_index": -1}, "nonnegative"),
    ({"estimated_start_index": float("nan")}, "nonnegative"),
    ({"estimated_start_index": 340}, "Decreasing"),
    ({"fluid": "CET"}, "not found"),
])
async def test_estimated_origin_refuses_unproven_hypotheses(monkeypatch, parameters, message):
    coord, raw = _case(monkeypatch)
    with pytest.raises(ValueError, match=message):
        await _preview(object(), coord, **parameters)


@pytest.mark.asyncio
async def test_estimated_origin_blocks_unreviewed_zero_and_source_conflict(monkeypatch):
    coord, _ = _case(monkeypatch, zero_times=[FIRST])
    with pytest.raises(ValueError, match="zero"):
        await _preview(object(), coord)
    coord, _ = _case(monkeypatch, conflicts=True)
    with pytest.raises(ValueError, match="conflicts"):
        await _preview(object(), coord)


@pytest.mark.asyncio
async def test_estimated_origin_rejects_unverified_unit_and_no_reading(monkeypatch):
    coord, _ = _case(monkeypatch, unit=None)
    with pytest.raises(ValueError, match="unit"):
        await _preview(object(), coord)
    coord, _ = _case(monkeypatch, readings=[])
    with pytest.raises(ValueError, match="No verified first"):
        await _preview(object(), coord)


@pytest.mark.asyncio
async def test_estimated_origin_requires_fresh_preview(monkeypatch):
    coord, _ = _case(monkeypatch)
    coord._history_review_cache = None
    with pytest.raises(ValueError, match="fresh"):
        await _preview(object(), coord)


@pytest.mark.asyncio
async def test_estimated_origin_first_source_zero_cannot_be_invented(monkeypatch):
    coord, _ = _case(monkeypatch, readings=[(FIRST, 0.0)])
    with pytest.raises(ValueError, match="zero index"):
        await _preview(object(), coord, estimated_start_index=0)


@pytest.mark.asyncio
async def test_estimated_origin_refuses_missing_raw_source_proof(monkeypatch):
    coord, meter = _case(monkeypatch)
    del meter["source_fingerprint"]
    with pytest.raises(ValueError, match="verified raw source fingerprint"):
        await _preview(object(), coord)


@pytest.mark.asyncio
async def test_estimated_origin_save_rechecks_exact_source_and_user_consent(monkeypatch):
    """Persist an assumption only with fresh identical source proof, never an index."""
    coord, raw = _case(monkeypatch)
    source_before = list(raw["reviewed_readings"])
    preview = await _preview(object(), coord)
    saved = AsyncMock(return_value={"status": "estimated_origin_decision_saved"})
    monkeypatch.setattr(panel_origin, "save_origin_choice", saved)
    args = {
        "lot": "LOT", "fluid": "EF", "serial": "METER",
        "estimated_start_date": "2021-12-22",
        "estimated_start_index": 316.0,
        "reason": "manual_periodic",
        "expected_fingerprint": preview["approval_fingerprint"],
        "confirm": True,
        "confirm_revision": False,
    }
    result = await panel_origin.save_confirmed_estimated_origin(object(), coord, **args)
    assert result["status"] == "estimated_origin_decision_saved"
    assert saved.await_count == 1
    choice = saved.await_args.args[2]
    assert choice["source_fingerprint"] == raw["source_fingerprint"]
    assert choice["first_observed_index"] == 332.0
    assert choice["estimated_start_index"] == 316.0
    assert choice["reason"] == "manual_periodic"
    assert saved.await_args.kwargs["confirm_revision"] is False
    assert raw["reviewed_readings"] == source_before

    with pytest.raises(ValueError, match="explicit confirmation"):
        await panel_origin.save_confirmed_estimated_origin(
            object(), coord, **{**args, "confirm": False},
        )
    assert saved.await_count == 1

    raw["source_fingerprint"] = "b" * 64
    with pytest.raises(ValueError, match="Source or parameters changed"):
        await panel_origin.save_confirmed_estimated_origin(object(), coord, **args)
    assert saved.await_count == 1
