"""b7 costing and diagnostic regression fixtures — no real meters or accounts."""
from datetime import date, datetime, timedelta, timezone
import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.historical_costs import estimate_historical_costs
from custom_components.trybatec.history_diagnostics import diagnose_history
from custom_components.trybatec.units import meter_key


def row(serial, fluid, points, *, lot="FAKE-A", unit=None, retired=False):
    result = {
        "compteur": serial, "fluide": fluid, "lot": lot, "depose": retired,
        "indexes": [{"date": at, "value": val} for at, val in points],
    }
    if unit is not None:
        result["indexUnit"] = unit
    return result


def history(*items, start="2025-01-01", end="2026-11-07"):
    return build_history(
        [{"lines": list(items)}], date.fromisoformat(start), date.fromisoformat(end)
    )


def times(start, values):
    first = datetime.fromisoformat(start)
    return [((first + timedelta(days=i)).isoformat(), val)
            for i, val in enumerate(values)]


def find(result, year, fluid, kind="measured_daily"):
    return next(x for x in result["annual"]
                if (x["year"], x["fluid"], x["evidence_type"]) == (year, fluid, kind))


def test_annual_costs_are_explicit_and_per_physical_meter():
    h = history(
        row("SAME", "EF", times("2026-02-01T00:00:00+01:00", [10, 12]), lot="FAKE-A", unit="m3"),
        row("SAME", "EF", times("2026-02-01T00:00:00+01:00", [1000, 3000]), lot="FAKE-B", unit="L"),
    )
    report = estimate_historical_costs(h, {"2026": {"EF": {"rate": 2.25, "status": "approved"}}})
    result = find(report, 2026, "EF")
    assert result["quantity"] == 4.0
    assert result["estimated_cost"] == 9.0
    assert result["tariff_status"] == "approved"
    assert result["billing_status"] == "estimate_not_approved_charges"
    assert result["currency"] == "EUR"
    assert result["meter_count"] == 2
    assert report["withheld_total"] == 0


def test_thermal_conversion_mwh_and_gj_keeps_accounting_units_explicit():
    h = history(
        row("H1", "CET", times("2026-05-01T00:00:00+02:00", [1, 2]), unit="MWh"),
        row("H2", "CET", times("2026-05-01T00:00:00+02:00", [0, 3.6]), unit="GJ"),
    )
    data = estimate_historical_costs(h, {"2026": {"CET": {"rate": 0.18, "status": "provisional"}}})
    result = find(data, 2026, "CET")
    assert result["quantity"] == pytest.approx(2000.0, abs=1e-6)
    assert result["unit"] == "kWh"
    assert result["estimated_cost"] == 360.0
    assert result["tariff_status"] == "provisional"


def test_costs_use_bucket_local_year_not_utc_year():
    h = history(
        row("M", "ECS", times("2025-12-30T00:00:00+01:00", [1, 2, 3, 4]), unit="m³"),
        start="2025-12-28", end="2026-01-04",
    )
    result = estimate_historical_costs(h, {
        "2025": {"ECS": {"rate": 3, "status": "approved"}},
        "2026": {"ECS": {"rate": 5, "status": "provisional"}},
    })
    assert find(result, 2025, "ECS")["quantity"] == 2.0
    assert find(result, 2026, "ECS")["quantity"] == 1.0
    assert find(result, 2025, "ECS")["estimated_cost"] == 6.0
    assert find(result, 2026, "ECS")["estimated_cost"] == 5.0


def test_no_tariff_never_uses_prior_year_fallback():
    h = history(row("M", "EF", times("2026-05-01T00:00:00+02:00", [0, 4]), unit="m3"))
    result = estimate_historical_costs(h, {"2025": {"EF": {"rate": 9, "status": "approved"}}})
    item = find(result, 2026, "EF")
    assert item["quantity"] == 4
    assert item["estimated_cost"] is None
    assert item["tariff_status"] == "missing"
    assert item["rate"] is None


def test_manual_override_and_unknown_meter_are_separate():
    h = history(
        row("KNOWN", "EF", times("2026-06-01T00:00:00+02:00", [0, 1])),
        row("UNKNOWN", "EF", times("2026-06-01T00:00:00+02:00", [0, 200])),
    )
    options = {meter_key("FAKE-A", "EF", "KNOWN"): "m³"}
    result = estimate_historical_costs(h, {"2026": {"EF": {"rate": 1, "status": "provisional"}}}, options)
    assert find(result, 2026, "EF")["quantity"] == 1
    assert result["withheld_total"] == 1
    assert result["withheld"][0]["meter_serial"] == "UNKNOWN"
    assert result["withheld"][0]["reason"] == "unit_unverified_or_conflicting"


def test_fatal_source_conflicts_never_enter_costs():
    h = history(row("BAD", "EF", times("2026-06-01T00:00:00+02:00", [10, 13]), unit="m3"))
    meter = h["__physical_meters__"][("FAKE-A", "EF", "BAD")]
    meter["fatal_conflicts"] = True
    result = estimate_historical_costs(h, {"2026": {"EF": {"rate": 10, "status": "approved"}}})
    assert result["annual"] == []
    assert result["withheld"][0]["reason"] == "unresolved_source_conflict"


def test_sparse_intervals_not_priced_without_approved_allocation():
    h = history(row("M", "EF", [
        ("2025-01-01T00:00:00+01:00", 100),
        ("2026-01-01T00:00:00+01:00", 130),
        ("2026-01-02T00:00:00+01:00", 131),
    ], unit="m³"))
    result = estimate_historical_costs(h, {"2026": {"EF": {"rate": 4, "status": "approved"}}})
    assert find(result, 2026, "EF")["quantity"] == 1
    assert find(result, 2026, "EF")["estimated_cost"] == 4
    assert find(result, 2026, "EF")["coverage"] == "partial_or_uncertain"
    assert not any(x["evidence_type"] == "accounting_allocation" for x in result["annual"])


def test_accounting_allocations_stay_separate_and_use_chosen_year():
    h = history(row("M", "ECS", times("2026-02-01T00:00:00+01:00", [0, 2]), unit="m3"))
    m = h["__physical_meters__"][("FAKE-A", "ECS", "M")]
    m["accounting_allocations"] = [
        {"at": datetime.fromisoformat("2025-12-31T23:00:00+01:00"),
         "quantity": 5, "source_key": "test-only"},
    ]
    report = estimate_historical_costs(h, {
        "2025": {"ECS": {"rate": 10, "status": "approved"}},
        "2026": {"ECS": {"rate": 2, "status": "provisional"}},
    })
    assert find(report, 2025, "ECS", "accounting_allocation")["estimated_cost"] == 50
    assert find(report, 2026, "ECS")["estimated_cost"] == 4
    assert len(report["annual"]) == 2


def test_corrupt_accounting_source_does_not_partially_price_meter():
    h = history(row("M", "EF", times("2026-02-01T00:00:00+01:00", [0, 2]), unit="m3"))
    meter = h["__physical_meters__"][("FAKE-A", "EF", "M")]
    stamp = datetime(2025, 12, 31, tzinfo=timezone.utc)
    meter["accounting_allocations"] = [
        {"at": stamp, "quantity": 3, "source_key": "repeated"},
        {"at": stamp, "quantity": 8, "source_key": "repeated"},
    ]
    report = estimate_historical_costs(h, {})
    assert report["annual"] == [] and report["withheld_total"] == 1
    assert report["withheld"][0]["reason"] == "invalid_meter_history"


def test_reject_invalid_daily_amount_and_timezone():
    h = history(row("M", "EF", times("2026-02-01T00:00:00+01:00", [0, 2]), unit="m3"))
    meter = h["__physical_meters__"][("FAKE-A", "EF", "M")]
    meter["rows"][-1]["sum"] = float("nan")
    assert estimate_historical_costs(h, {})["withheld_total"] == 1
    meter["rows"][-1]["sum"] = 2
    meter["rows"][-1]["start"] = datetime(2026, 2, 2)
    assert estimate_historical_costs(h, {})["withheld_total"] == 1


def test_diagnostics_classify_gaps_units_and_overlap():
    h = history(
        row("A", "EF", times("2026-01-01T00:00:00+01:00", [10, 15]), unit="m3"),
        row("B", "EF", times("2026-01-01T00:00:00+01:00", [1, 5])),
        start="2026-01-01", end="2026-02-01",
    )
    result = diagnose_history(h)
    assert result["meters_total"] == 2
    assert result["issue_counts"]["unit_unverified_or_conflicting"] == 1
    assert result["issue_counts"]["overlapping_meters_unconfirmed"] == 2
    assert result["severity_counts"]["critical"] == 1
    assert result["details_truncated"] is False
    assert result["counts_by_fluid"]["EF"]["meters"] == 2


def test_diagnostics_obey_detail_limit_and_keep_counts():
    h = history(
        row("A", "EF", times("2026-01-01T00:00:00+01:00", [0, 2]), unit="m3"),
        row("B", "ECS", times("2026-01-01T00:00:00+01:00", [0, 3]), unit="m3"),
    )
    report = diagnose_history(h, max_details=1)
    assert report["meters_total"] == 2
    assert len(report["details"]) == 1
    assert report["details_truncated"]


def test_negative_or_unbounded_rates_refused_even_outside_service():
    h = history(row("W", "EF", times("2026-02-01T00:00:00+01:00", [0, 1]), unit="m3"))
    for bad in (-1, float("nan"), True):
        with pytest.raises(ValueError):
            estimate_historical_costs(h, {"2026": {"EF": {"rate": bad, "status": "approved"}}})


def test_costs_report_each_meters_quantity_and_inherited_rate():
    """Two physical meters, including reused serials, never share cost overrides."""
    h = history(
        row("SAME", "EF", times("2026-02-01T00:00:00+01:00", [10, 12]),
            lot="FAKE-A", unit="m3"),
        row("SAME", "EF", times("2026-02-01T00:00:00+01:00", [1000, 3000]),
            lot="FAKE-B", unit="L"),
    )
    default = {"2026": {"EF": {"rate": 2.0, "status": "approved"}}}
    specific = {"2026": {
        meter_key("FAKE-B", "EF", "SAME"): {"rate": 3.25, "status": "provisional"}
    }}
    item = find(estimate_historical_costs(
        h, default, meter_tariffs=specific,
    ), 2026, "EF")
    meters = {m["lot"]: m for m in item["meter_rates"]}
    assert item["quantity"] == 4.0
    assert item["estimated_cost"] == 10.50
    assert item["rate"] is None  # two rates, not missing or merged as one
    assert item["rate_origin"] == "mixed"
    assert item["tariff_status"] == "mixed"
    assert meters["FAKE-A"]["quantity"] == 2.0
    assert meters["FAKE-A"]["estimated_cost"] == 4.0
    assert meters["FAKE-A"]["rate"] == 2.0
    assert meters["FAKE-A"]["origin"] == "fluid_default"
    assert meters["FAKE-B"]["quantity"] == 2.0
    assert meters["FAKE-B"]["estimated_cost"] == 6.50
    assert meters["FAKE-B"]["rate"] == 3.25
    assert meters["FAKE-B"]["origin"] == "meter_override"
    assert all(m["currency"] == "EUR" for m in item["meter_rates"])
    assert all(m["billing_status"] == "estimate_not_approved_charges"
               for m in item["meter_rates"])


def test_missing_meter_tariff_never_creates_cost():
    h = history(row("M", "ECS", times("2026-02-01T00:00:00+01:00", [0, 2]),
                    lot="FAKE-A", unit="m3"))
    item = find(estimate_historical_costs(h, {}), 2026, "ECS")
    assert item["estimated_cost"] is None
    assert item["meter_rates"][0]["quantity"] == 2.0
    assert item["meter_rates"][0]["rate"] is None
    assert item["meter_rates"][0]["estimated_cost"] is None
    assert item["meter_rates"][0]["currency"] == "EUR"
