"""FR/EN: Synthetic F26 conflicts and F27 ending-reading-year attribution.

No real meter, lot, account, credentials, HA installation or third-party writes.
"""
from datetime import date

from custom_components.trybatec.parsing import parse_lines, summarize_annual
from custom_components.trybatec.history import build_history, summarize_preview


def fake_line(serial, fluid, readings, *, conso=3.0):
    return {
        "compteur": serial, "fluide": fluid, "lot": "FICTIONAL-LOT",
        "depose": False, "unit": "m3" if fluid != "CET" else "kWh",
        "conso": conso,
        "indexes": [{"date": at, "value": value} for at, value in readings],
    }


def test_f26_identical_same_time_duplicates_remain_valid():
    reading = "2026-11-03T00:00:00+01:00"
    later = "2026-11-04T00:00:00+01:00"
    payload = {"lines": [fake_line("FICTIONAL-EF", "EF", [
        (reading, 10.0), (reading, 10.0), (later, 13.0)
    ])]}
    parsed = parse_lines(payload)["FICTIONAL-EF"]
    assert parsed["has_conflicting_indexes"] is False
    assert parsed["conflicting_index_details"] == []
    assert len(parsed["indexes"]) == 2
    assert parsed["last"][1] == 13.0
    assert summarize_annual(payload)["EF"]["value"] == 3.0


def test_f26_conflicts_fail_closed_only_for_affected_fluid():
    t0 = "2026-11-03T00:00:00+01:00"
    t1 = "2026-11-04T00:00:00+01:00"
    payload = {"lines": [
        fake_line("FICTIONAL-EF", "EF", [
            (t0, 10.0), (t1, 13.0), (t1, 99.0)], conso=3.0),
        fake_line("FICTIONAL-EF-OK", "EF", [
            (t0, 20.0), (t1, 21.0)], conso=1.0),
        fake_line("FICTIONAL-ECS", "ECS", [
            (t0, 30.0), (t1, 32.0)], conso=2.0),
    ]}
    bad = parse_lines(payload)["FICTIONAL-EF"]
    assert bad["has_conflicting_indexes"] is True
    assert bad["indexes"] == [] and bad["last"] is None
    assert bad["period_consumption"] is None
    assert bad["conflicting_index_details"][0]["values"] == [13.0, 99.0]
    assert len(payload["lines"][0]["indexes"]) == 3  # immutable source evidence
    annual = summarize_annual(payload)
    assert annual["EF"]["value"] is None
    assert annual["EF"]["coverage_warning"] is True
    assert annual["EF"]["has_conflicting_indexes"] is True
    assert annual["ECS"]["value"] == 2.0


def test_f27_end_reading_year_is_not_hourly_bucket_year():
    payload = {"lines": [fake_line("FICTIONAL-EF", "EF", [
        ("2025-12-31T23:15:00+01:00", 10.0),
        ("2026-01-01T00:15:00+01:00", 13.0),
    ])]}
    history = build_history([payload], date(2025, 12, 31), date(2026, 1, 1))
    result = summarize_preview(history)["EF"]
    assert result["yearly_consumption_by_end_reading"] == {"2026": 3.0}
    assert result["yearly_consumption_within_same_year"] == {}
    assert result["yearly_daily_cadence_only"] == {"2025": 3.0}
    assert result["intervals_crossing_year_boundary"] == 1
    assert result["observed_consumption"] == 3.0
