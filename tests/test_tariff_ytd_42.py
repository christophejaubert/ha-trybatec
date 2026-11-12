"""Synthetic, read-only YTD tariff calculator tests (#42 / PR #120 dependency).

No installation, vendor account, Recorder/energy service or real meter identifiers.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from custom_components.trybatec.tariff_ytd import preview_ytd_tariff_costs
from custom_components.trybatec.units import meter_key


def _state() -> dict:
    return {
        "year": 2026,
        "meters": {
            "METER-A": {
                "lot": "FAKE-LOT", "fluid": "EF", "serial": "METER-A",
                "period_consumption": 2.0, "portal_unit": "m³",
                "indexes": [("2026-01-02", 8.0)],
            },
            "METER-B": {
                "lot": "FAKE-LOT", "fluid": "EF", "serial": "METER-B",
                "period_consumption": 3.0, "portal_unit": "m³",
                "indexes": [("2026-01-02", 12.0)],
            },
            "METER-C": {
                "lot": "FAKE-LOT", "fluid": "CET", "serial": "METER-C",
                "period_consumption": 0.5, "portal_unit": "MWh",
                "indexes": [("2026-01-02", 4.0)],
            },
        },
        "annual": {
            "EF": {"value": 5.0, "meters": 2, "unit_verified": True,
                   "coverage_warning": False},
            "ECS": {"value": None, "meters": 0, "unit_verified": True,
                    "coverage_warning": False},
            "CET": {"value": 500.0, "meters": 1, "unit_verified": True,
                    "coverage_warning": True},
        },
    }


def _tariffs() -> dict:
    return {"2026": {
        "EF": {"rate": 2.0, "status": "approved"},
        "CET": {"rate": 0.125, "status": "provisional"},
    }}


def test_ytd_applies_physical_exception_without_spreading_default_rate() -> None:
    state = _state()
    key = meter_key("FAKE-LOT", "EF", "METER-B")
    report = preview_ytd_tariff_costs(
        state, _tariffs(), {"2026": {key: {"rate": 4.0, "status": "provisional"}}},
    )
    cold = report["EF"]
    assert cold["estimated_cost"] == 16.0  # 2 m³ × 2 + 3 m³ × 4
    assert cold["effective_unit_price"] is None  # mixed price must be unavailable
    assert cold["price_status"] == "mixed"
    assert cold["fallback_from_prior_year"] is False
    assert cold["unit"] == "m³" and cold["rate_unit"] == "EUR/m³"
    assert cold["currency"] == "EUR"
    assert cold["billing_status"] == "estimate_not_approved_charges"
    assert {r["origin"] for r in cold["meter_rates"]} == {
        "meter_override", "fluid_default",
    }
    assert report["CET"]["estimated_cost"] == 62.5
    assert report["CET"]["coverage_warning"] is True
    assert report["CET"]["unit"] == "kWh"
    assert report["CET"]["rate_unit"] == "EUR/kWh"
    assert report["ECS"]["estimated_cost"] is None


def test_ytd_defaults_only_when_no_physical_exception() -> None:
    value = preview_ytd_tariff_costs(_state(), _tariffs())["EF"]
    assert value["estimated_cost"] == 10.0
    assert value["effective_unit_price"] == 2.0
    assert value["price_status"] == "approved"
    assert value["source_year"] == 2026
    assert not value["fallback_from_prior_year"]


def test_ytd_missing_tariff_or_meter_never_invents_partial_total() -> None:
    key = meter_key("FAKE-LOT", "EF", "METER-B")
    only_one_override = {"2026": {
        key: {"rate": 4.0, "status": "approved"},
    }}
    result = preview_ytd_tariff_costs(_state(), {}, only_one_override)["EF"]
    assert result["status"] == "missing_tariff"
    assert result["estimated_cost"] is None
    assert result["effective_unit_price"] is None
    assert len(result["meter_rates"]) == 2
    assert sum(r["rate"] is None for r in result["meter_rates"]) == 1


def test_ytd_prior_year_fallback_is_explicit_and_not_historical() -> None:
    prior = {"2025": {"EF": {"rate": 3.0, "status": "approved"}}}
    report = preview_ytd_tariff_costs(_state(), prior)["EF"]
    assert report["estimated_cost"] == 15.0
    assert report["fallback_from_prior_year"] is True
    assert report["source_year"] == 2025
    assert {r["source_year"] for r in report["meter_rates"]} == {2025}
    assert all(r["fallback"] for r in report["meter_rates"])


def test_ytd_missing_or_conflicting_source_units_fail_closed() -> None:
    base = _state()
    wrong = deepcopy(base)
    wrong["meters"]["METER-B"]["portal_unit"] = "kWh"
    failed = preview_ytd_tariff_costs(wrong, _tariffs())["EF"]
    assert failed["status"] == "unit_or_meter_unverified"
    assert failed["estimated_cost"] is None
    bad_total = deepcopy(base)
    bad_total["annual"]["EF"]["value"] = 6
    assert preview_ytd_tariff_costs(bad_total, _tariffs())["EF"]["status"] == "source_total_mismatch"
    bad_count = deepcopy(base)
    bad_count["annual"]["EF"]["meters"] = 1
    assert preview_ytd_tariff_costs(bad_count, _tariffs())["EF"]["estimated_cost"] is None
    incomplete = deepcopy(base)
    incomplete["annual"]["EF"]["unit_verified"] = False
    assert preview_ytd_tariff_costs(incomplete, _tariffs())["EF"]["estimated_cost"] is None
    repeated = deepcopy(base)
    repeated["meters"]["duplicate"] = deepcopy(repeated["meters"]["METER-B"])
    assert preview_ytd_tariff_costs(repeated, _tariffs())["EF"]["estimated_cost"] is None


def test_ytd_values_are_validated_and_source_options_are_unchanged() -> None:
    state, prices = _state(), _tariffs()
    prior_state, prior_prices = deepcopy(state), deepcopy(prices)
    preview_ytd_tariff_costs(state, prices)
    assert state == prior_state and prices == prior_prices
    for invalid in [True, -1, float("nan"), float("inf")]:
        broken = deepcopy(prices)
        broken["2026"]["EF"]["rate"] = invalid
        with pytest.raises((ValueError, TypeError)):
            preview_ytd_tariff_costs(state, broken)
    override_key = meter_key("FAKE-LOT", "EF", "METER-B")
    with pytest.raises(ValueError):
        preview_ytd_tariff_costs(
            state, prices,
            {"2026": {override_key: {"rate": -1, "status": "approved"}}},
        )


def test_ytd_mismatched_year_and_fluids_are_not_silently_reused() -> None:
    state = _state()
    key = meter_key("FAKE-LOT", "EF", "METER-B")
    ignored = {"2025": {key: {"rate": 200.0, "status": "approved"}}}
    result = preview_ytd_tariff_costs(state, _tariffs(), ignored)
    assert result["EF"]["estimated_cost"] == 10.0
    with pytest.raises(ValueError):
        preview_ytd_tariff_costs({**state, "year": True}, _tariffs())
