"""Synthetic Trybatec in-panel source reading decisions and DST safety."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.trybatec import panel_review
from custom_components.trybatec.history_review import reading_key

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _case(monkeypatch):
    source={
        "key":"a"*32,"lot":"LOT","fluid":"EF","meter_serial":"METER",
        "source_date":"2022-01-20T12:00:00+01:00","index":332.0,
        "previous_date":"2021-12-22T12:00:00+01:00",
        "previous_index":316.0,
        "reasons":["sparse_interval","index_zero"],"decision":"unreviewed",
    }
    before=dict(source)
    current={}
    count={"n":0}
    coordinator=SimpleNamespace(
        entry=SimpleNamespace(entry_id="ci-reading",options={}),
        _history_review_cache=([],date(2021,12,22),date(2022,1,20),{"LOT"}),
    )
    def build(payloads,start,end,**kwargs):
        choice=kwargs.get("decisions",{}).get(source["key"])
        row={**source,"decision":choice["action"] if choice else "unreviewed"}
        return {"__review_candidates__":[row]}
    async def load(*args):
        return dict(current)
    async def save(hass,entry,key,decision):
        count["n"]+=1
        current[key]=dict(decision)
        return dict(current)
    monkeypatch.setattr(panel_review,"build_history",build)
    monkeypatch.setattr(panel_review,"load_decisions",load)
    monkeypatch.setattr(panel_review,"save_decision",save)
    return coordinator,current,count,source,before


@pytest.mark.asyncio
async def test_reading_accepts_source_zero_explicitly_without_changing_raw_data(monkeypatch):
    coord,store,count,source,before=_case(monkeypatch)
    with pytest.raises(ValueError,match="explicit"):
        await panel_review.save_panel_reading_decision(
            object(),coord,reading_key=source["key"],
            action="accept",confirm=False,
        )
    assert count["n"]==0
    result=await panel_review.save_panel_reading_decision(
        object(),coord,reading_key=source["key"],
        action="accept",confirm=True,
    )
    assert result["status"]=="reading_decision_saved"
    assert result["review_candidates"][0]["decision"]=="accept"
    assert store[source["key"]]["action"]=="accept"
    assert source==before
    assert result["source_indices_unchanged"] is True
    assert result["recorder_unchanged"] and result["energy_unchanged"]


@pytest.mark.asyncio
async def test_measured_date_correction_needs_justification_and_unique_paris_time(monkeypatch):
    coord,store,count,source,before=_case(monkeypatch)
    with pytest.raises(ValueError,match="justification"):
        await panel_review.save_panel_reading_decision(
            object(),coord,reading_key=source["key"],action="correct",
            mode="measurement",date="2022-01-19",time="12:00:00",
            reason="short",confirm=True,
        )
    result=await panel_review.save_panel_reading_decision(
        object(),coord,reading_key=source["key"],action="correct",
        mode="measurement",date="2022-01-19",time="12:00:00",
        reason="Relevé confirmé par facture",confirm=True,
    )
    assert result["action"]=="correct"
    assert store[source["key"]]["mode"]=="measurement"
    assert store[source["key"]]["timestamp"].startswith("2022-01-19T12:00:00")
    assert source==before
    assert count["n"]==1


@pytest.mark.asyncio
async def test_out_of_period_accounting_requires_separate_confirmation(monkeypatch):
    coord,store,count,source,before=_case(monkeypatch)
    args=dict(
        reading_key=source["key"],action="correct",mode="accounting",
        date="2021-01-20",time="12:00:00",
        reason="Comptabilisation annuelle explicite",
        confirm=True,
    )
    with pytest.raises(ValueError,match="separate"):
        await panel_review.save_panel_reading_decision(
            object(),coord,**args,
        )
    assert count["n"]==0
    result=await panel_review.save_panel_reading_decision(
        object(),coord,**args,out_of_period_confirmed=True,
    )
    assert result["action"]=="correct"
    assert store[source["key"]]["out_of_period_confirmed"] is True
    assert source==before


@pytest.mark.parametrize("day,time", [
    ("2025-03-30","02:30:00"),
    ("2025-10-26","02:30:00"),
])
def test_nonexistent_and_ambiguous_dst_times_are_rejected(day,time):
    with pytest.raises(ValueError,match="daylight-saving"):
        panel_review._verified_local_timestamp(day,time)


@pytest.mark.asyncio
async def test_source_choice_not_in_current_preview_refused(monkeypatch):
    coord,store,count,source,before=_case(monkeypatch)
    with pytest.raises(ValueError,match="no longer"):
        await panel_review.save_panel_reading_decision(
            object(),coord,reading_key="0"*32,action="reject",confirm=True,
        )
    assert count["n"]==0
    assert store=={}


@pytest.mark.asyncio
async def test_postpone_not_presented_as_no_effect(monkeypatch):
    coord,store,count,source,before=_case(monkeypatch)
    result=await panel_review.save_panel_reading_decision(
        object(),coord,reading_key=source["key"],
        action="postpone",confirm=True,
    )
    assert store[source["key"]]["action"]=="postpone"
    assert result["review_candidates"][0]["decision"]=="postpone"
    assert result["source_indices_unchanged"]
