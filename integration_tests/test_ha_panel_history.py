"""Admin Trybatec history-panel read/confirm regression tests (synthetic)."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.trybatec import panel_history
from custom_components.trybatec.units import meter_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

ZONE=ZoneInfo("Europe/Paris")
FIRST=datetime(2021,12,22,0,0,tzinfo=ZONE)
LAST=datetime(2022,1,20,0,0,tzinfo=ZONE)
KEY=("LOT-TEST","EF","SYNTH-OLD")


def _fixture(monkeypatch, *, blocked=False):
    coordinator=SimpleNamespace(
        entry=SimpleNamespace(
            entry_id="ci-panel-history",
            options={
                "meter_units": {meter_key(*KEY): "m³"},
                "sparse_interval_hours": 27,
                "zero_index_review_days": 1,
            },
        ),
        _history_review_cache=([], FIRST.date(), LAST.date(), {"LOT-TEST"}),
        _history_review_candidates=[],
    )
    meter={
        "reviewed_readings": [(FIRST, 316.0),(LAST, 332.0)],
        "portal_unit": "m³",
        "source_fingerprint": "CI-EXPECTED-SOURCE",
        "fatal_conflicts": False,
        "conflicts": [],
        "unreviewed_zero_times": [FIRST] if blocked else [],
        "qualified_zero_times": [],
    }
    def build(*args, **kwargs):
        return {"__physical_meters__": {KEY: meter}, "__review_candidates__": []}
    monkeypatch.setattr(panel_history,"build_history",build)
    monkeypatch.setattr(panel_history,"load_decisions",AsyncMock(return_value={}))
    monkeypatch.setattr(panel_history,"load_choices",AsyncMock(return_value={}))
    persisted={}
    async def save(_hass, _entry, interval_key, *, mode, reason):
        persisted[interval_key]={"mode":mode,"reason":reason,"updated_at":"2026-11-09T18:00:00+00:00"}
        return persisted
    monkeypatch.setattr(panel_history,"save_choice",save)
    return coordinator,meter,persisted


@pytest.mark.asyncio
async def test_panel_history_preview_reuses_validated_cache_and_preserves_indexes(monkeypatch):
    coord,meter,_=_fixture(monkeypatch)
    raw=list(meter["reviewed_readings"])
    view=await panel_history._proposals_from_cached_history(object(),coord)
    assert view["recorder_writes"] is False
    assert view["energy_writes"] is False
    assert len(view["proposals"]["intervals"])==1
    gap=view["proposals"]["intervals"][0]
    assert gap["status"]=="linear_available_after_explicit_confirmation"
    assert gap["source_start_index"]==316.0
    assert gap["source_end_index"]==332.0
    assert gap["bounded_consumption"]==16
    assert gap["days"]==29
    assert sum(row["quantity"] for row in gap["daily_preview"])==pytest.approx(16)
    assert all(row["provenance"]=="estimated_linear" for row in gap["daily_preview"])
    assert meter["reviewed_readings"]==raw


@pytest.mark.asyncio
async def test_panel_history_confirm_requires_valid_preview_and_explicit_decision(monkeypatch):
    coord,meter,persisted=_fixture(monkeypatch)
    hass=object()
    view=await panel_history._proposals_from_cached_history(hass,coord)
    key=view["proposals"]["intervals"][0]["interval_key"]
    with pytest.raises(ValueError,match="explicit"):
        await panel_history.save_panel_smoothing_choice(
            hass,coord,interval_key=key,mode="linear",
            reason="manual_periodic",confirm=False,
        )
    with pytest.raises(ValueError,match="no longer present"):
        await panel_history.save_panel_smoothing_choice(
            hass,coord,interval_key="0"*32,mode="linear",
            reason="manual_periodic",confirm=True,
        )
    assert persisted=={}
    good=await panel_history.save_panel_smoothing_choice(
        hass,coord,interval_key=key,mode="linear",
        reason="manual_periodic",confirm=True,
    )
    assert good["status"]=="smoothing_choice_saved"
    assert persisted[key]["mode"]=="linear"
    assert good["source_indices_unchanged"] and good["recorder_unchanged"]
    meter["reviewed_readings"]=[(FIRST,316.0),(LAST,333.0)]
    with pytest.raises(ValueError,match="no longer present"):
        await panel_history.save_panel_smoothing_choice(
            hass,coord,interval_key=key,mode="linear",
            reason="manual_periodic",confirm=True,
        )


@pytest.mark.asyncio
async def test_panel_history_zero_is_never_implicitly_accepted(monkeypatch):
    coord,meter,persisted=_fixture(monkeypatch,blocked=True)
    preview=await panel_history._proposals_from_cached_history(object(),coord)
    interval=preview["proposals"]["intervals"][0]
    assert interval["status"]=="blocked_unreviewed_zero"
    with pytest.raises(ValueError,match="not safely eligible"):
        await panel_history.save_panel_smoothing_choice(
            object(),coord,interval_key=interval["interval_key"],
            mode="linear",reason="other",confirm=True,
        )
    assert persisted=={}
    no_smoothing=await panel_history.save_panel_smoothing_choice(
        object(),coord,interval_key=interval["interval_key"],
        mode="none",reason="other",confirm=True,
    )
    assert no_smoothing["choice"]["mode"]=="none"


@pytest.mark.asyncio
async def test_panel_history_rejects_future_or_reversed_or_too_long_ranges(monkeypatch):
    coord,meter,_=_fixture(monkeypatch)
    async def must_not_read(*args,**kwargs):
        pytest.fail("An invalid preview may never call the vendor")
    monkeypatch.setattr(panel_history,"_load",must_not_read)
    for start,end in [
        ("2023-01-01","2022-01-01"),("2020-01-01","2040-01-01"),
        ("2000-01-01","2026-11-01"),
    ]:
        with pytest.raises(ValueError):
            await panel_history.preview_history_for_panel(
                object(),coord,start_date=start,end_date=end,
            )


def test_panel_estimated_start_only_as_confirmed_estimate_not_real_reading():
    with pytest.raises(ValueError,match="explicit"):
        panel_history.preview_estimated_initial_interval(
            end_at=LAST,end_index=332,
            estimated_start_date=date(2021,12,22),estimated_start_index=0,
            confirm_estimated_start=False,
        )
    result=panel_history.preview_estimated_initial_interval(
        end_at=LAST,end_index=332,
        estimated_start_date=date(2021,12,22),estimated_start_index=0,
        confirm_estimated_start=True,
    )
    assert result["origin"]=="estimated_confirmed"
    assert result["total"]==332
    assert len(result["allocations"])==29
    assert sum(x["quantity"] for x in result["allocations"])==pytest.approx(332)
    assert all(x["provenance"]=="estimated_linear" for x in result["allocations"])
    with pytest.raises(ValueError,match="declin|Decreas|Index"):
        panel_history.preview_estimated_initial_interval(
            end_at=LAST,end_index=332,
            estimated_start_date=date(2021,12,22),estimated_start_index=340,
            confirm_estimated_start=True,
        )



def test_exact_reading_to_previous_interval_link_never_guesses_another_meter():
    key = "a" * 32
    reading = {
        "key": "source-1", "lot": "LOT-TEST",
        "fluid": "EF", "meter_serial": "SYNTH-OLD",
        "source_date": LAST.isoformat(), "index": 332,
    }
    interval = {
        "interval_key": key, "lot": "LOT-TEST",
        "fluid": "EF", "meter_serial": "SYNTH-OLD",
        "source_end_at": LAST.isoformat(),
        "status": "linear_available_after_explicit_confirmation",
    }
    result = panel_history.link_review_candidates_to_previous_intervals(
        [reading], [interval],
    )
    assert result[0]["preceding_interval_key"] == key
    assert result[0]["preceding_interval_status"] == interval["status"]
    assert "preceding_interval_key" not in reading
    assert panel_history.link_review_candidates_to_previous_intervals(
        [{**reading, "meter_serial": "ANOTHER"}], [interval],
    )[0]["preceding_interval_key"] is None
    assert panel_history.link_review_candidates_to_previous_intervals(
        [{**reading, "source_date": FIRST.isoformat()}], [interval],
    )[0]["preceding_interval_key"] is None


def test_multiple_endpoints_or_unreviewed_zero_cannot_bypass_decision_controls():
    reading = {
        "key": "source-2", "lot": "LOT-TEST", "fluid": "EF",
        "meter_serial": "SYNTH-OLD", "source_date": LAST.isoformat(),
    }
    source = {
        "interval_key": "b" * 32, "lot": "LOT-TEST", "fluid": "EF",
        "meter_serial": "SYNTH-OLD", "source_end_at": LAST.isoformat(),
        "status": "blocked_unreviewed_zero",
    }
    verified = panel_history.link_review_candidates_to_previous_intervals(
        [reading], [source],
    )
    assert verified[0]["preceding_interval_key"] == source["interval_key"]
    assert verified[0]["preceding_interval_status"] == "blocked_unreviewed_zero"
    ambiguous = panel_history.link_review_candidates_to_previous_intervals(
        [reading], [source, {**source, "interval_key": "c" * 32}],
    )
    assert ambiguous[0]["preceding_interval_key"] is None
    assert ambiguous[0]["preceding_interval_status"] == "ambiguous"
