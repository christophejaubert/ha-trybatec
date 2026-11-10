"""Approved estimated origins contribute only to selected, labelled consumption variants."""
from datetime import date

import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_origin_decisions import proposed_choice
from custom_components.trybatec.history_plan_b15 import make_b15_plan
from custom_components.trybatec.history_variants_b15 import variants_preview
from custom_components.trybatec.units import meter_key


def _history(first_index=332.0):
    payload = {"lines": [{
        "compteur": "SYNTH-METER", "fluide": "EF", "lot": "SYNTH-LOT",
        "depose": False, "indexUnit": "m3",
        "indexes": [
            {"date": "2022-01-20T10:00:00+01:00", "value": first_index},
            {"date": "2022-01-21T10:00:00+01:00", "value": first_index + 4},
        ],
    }]}
    history = build_history(
        [payload], date(2022, 1, 18), date(2022, 1, 25),
        allowed_lots={"SYNTH-LOT"},
    )
    key = ("SYNTH-LOT", "EF", "SYNTH-METER")
    meter = history["__physical_meters__"][key]
    first_at, first_value = meter["reviewed_readings"][0]
    approval = proposed_choice(
        lot=key[0], fluid=key[1], serial=key[2],
        source_fingerprint=meter["source_fingerprint"],
        first_observed_at=first_at.isoformat(),
        first_observed_index=first_value,
        estimated_start_date="2022-01-18",
        estimated_start_index=316.0,
        reason="manual_periodic",
    )
    return history, {key: "m³"}, {meter_key(*key): approval}


def test_approved_origin_creates_consumption_not_measured_index():
    history, units, origins = _history()
    source_before = list(history["__physical_meters__"][next(iter(units))]["reviewed_readings"])
    preview = variants_preview(history, units, approved_origins=origins)
    physical = preview["meters"][0]
    assert physical["selected_gap_fingerprints"] == [
        "approved_origin:" + next(iter(origins.values()))["approval_fingerprint"]
    ]
    assert physical["raw_total"] == 4.0
    assert physical["smoothed_total"] == pytest.approx(20.0)
    assert physical["raw"] == {date(2022, 1, 21): 4.0}
    assert physical["smoothed"][date(2022, 1, 19)] == pytest.approx(8.0)
    assert physical["smoothed"][date(2022, 1, 20)] == pytest.approx(8.0)
    assert physical["smoothed"][date(2022, 1, 21)] == pytest.approx(4.0)
    assert preview["approved_estimated_origins"] == 1
    assert history["__physical_meters__"][next(iter(units))]["reviewed_readings"] == source_before

    plan = make_b15_plan(history, units, {}, "SYNTH-ACCOUNT", approved_origins=origins)
    physical_raw = next(x for x in plan["series"] if x["kind"] == "physical" and x["variant"] == "raw")
    physical_smooth = next(x for x in plan["series"] if x["kind"] == "physical" and x["variant"] == "smoothed")
    collective = next(x for x in plan["series"] if x["kind"] == "consolidated")
    assert physical_raw["rows"][-1]["sum"] == pytest.approx(4.0)
    assert physical_smooth["rows"][-1]["sum"] == pytest.approx(20.0)
    assert collective["rows"][-1]["sum"] == pytest.approx(20.0)
    assert collective["selected_meters"] == {"SYNTH-METER": "smoothed"}
    assert plan["approved_estimated_origins"] == 1

    original = make_b15_plan(history, units, {}, "SYNTH-ACCOUNT")
    assert original["fingerprint"] != plan["fingerprint"]
    assert next(x for x in original["series"] if x["kind"] == "consolidated")["rows"][-1]["sum"] == 4.0


def test_unapproved_or_stale_origin_cannot_be_selected_silently():
    history, units, origins = _history()
    original = variants_preview(history, units)
    assert original["meters"][0]["smoothed_total"] == 4.0
    assert original["approved_estimated_origins"] == 0

    key = next(iter(origins))
    changed = {key: {**origins[key], "source_fingerprint": "b" * 64}}
    with pytest.raises(ValueError):
        variants_preview(history, units, approved_origins=changed)
    history["__physical_meters__"][next(iter(units))]["source_fingerprint"] = "b" * 64
    with pytest.raises(ValueError, match="stale"):
        variants_preview(history, units, approved_origins=origins)


def test_origin_refuses_other_meter_or_unsupported_source():
    history, units, origins = _history()
    with pytest.raises(ValueError, match="missing physical meter"):
        variants_preview(history, units, approved_origins={
            meter_key("DIFFERENT-LOT", "EF", "SYNTH-METER"): next(iter(origins.values()))
        })
    history["__physical_meters__"][next(iter(units))]["conflicts"] = 1
    blocked = variants_preview(history, units, approved_origins=origins)
    assert blocked["meters"][0]["status"] == "blocked_source_conflict"
    with pytest.raises(ValueError, match="Unverified or conflicted"):
        make_b15_plan(history, units, {}, "SYNTH-ACCOUNT", approved_origins=origins)
