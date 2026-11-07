"""No user's account, address, ids or token in test fixtures."""

import json
import pytest

from custom_components.trybatec.parsing import (
    numeric,
    parse_lines,
    parse_timestamp,
    summarize_annual,
    validate_tariffs,
    resolve_tariff,
)


@pytest.fixture
def sample():
    return {
        "lines": [
            {
                "compteur": "TEST-W1",
                "fluide": "EF",
                "lot": "TEST",
                "depose": False,
                "conso": 0.14,
                "indexes": [
                    {"date": "2026-10-30T23:00:00.000+00:00", "value": 10.0},
                    {"date": "2026-10-31T23:00:00.000+00:00", "value": 10.14},
                ],
            },
            {
                "compteur": "TEST-W-OLD",
                "fluide": "EF",
                "depose": True,
                "conso": 0.0,
                "indexes": [None],
            },
        ]
    }


def test_local_datetime_is_converted_from_utc():
    got = parse_timestamp("2026-10-30T23:00:00.000+00:00")
    assert got.isoformat() == "2026-10-31T00:00:00+01:00"


def test_rejects_bad_dates_and_numbers():
    assert parse_timestamp("2026-01-01T00:00:00") is None
    assert parse_timestamp("invalid") is None
    assert numeric(True) is None
    assert numeric(float("nan")) is None
    assert numeric(-1) is None
    assert numeric(0.0) == 0.0


def test_parse_meter_and_deposed(sample):
    out = parse_lines(sample)
    assert out["TEST-W1"]["last"][1] == 10.14
    assert out["TEST-W1"]["last"][0].date().isoformat() == "2026-11-01"
    assert out["TEST-W-OLD"]["deposed"] is True
    assert out["TEST-W-OLD"]["last"] is None


def test_skip_decreasing_last_index():
    data = {"lines": [{
        "compteur": "TEST", "fluide": "ECS", "conso": 0,
        "indexes": [
            {"date": "2026-10-01T22:00:00+00:00", "value": 15.0},
            {"date": "2026-10-02T22:00:00+00:00", "value": 14.9},
        ],
    }]}
    parsed = parse_lines(data)["TEST"]
    assert parsed["last"] is None
    assert parsed["has_decreasing_indexes"]


def test_year_total_uses_portal_period_conso(sample):
    result = summarize_annual(sample)
    assert result["EF"]["value"] == 0.14
    assert result["EF"]["meters"] == 1
    assert result["CET"]["value"] is None


def test_annual_gaps_warn():
    data = {"lines": [{
        "compteur": "TEST", "fluide": "CET", "conso": 23,
        "indexes": [
            {"date": "2026-01-01T00:00:00+00:00", "value": 1},
            {"date": "2026-03-01T00:00:00+00:00", "value": 24},
        ],
    }]}
    assert summarize_annual(data)["CET"]["coverage_warning"]


def test_tariffs_are_per_civil_year():
    tariffs = validate_tariffs('{"2025":{"EF":{"rate":5.17,"status":"provisional"},"ECS":6.0}}')
    assert tariffs["2025"]["EF"] == {"rate": 5.17, "status": "provisional"}
    assert tariffs["2025"]["ECS"]["status"] == "provisional"


@pytest.mark.parametrize("value", [
    "[]", '{"bad":{"EF":1}}', '{"2025":{"ABCD":1}}',
    '{"2025":{"EF":-2}}', '{"2025":{"EF":{"rate":1,"status":"madeup"}}}',
    '{"2025":{"EF":true}}', 'not-json',
])
def test_invalid_tariffs_rejected(value):
    with pytest.raises((ValueError, TypeError, json.JSONDecodeError)):
        validate_tariffs(value)


def test_skip_index_below_prior_maximum():
    data = {"lines": [{"compteur":"TEST", "fluide":"CET", "indexes": [
        {"date":"2026-01-01T00:00:00+00:00", "value":300},
        {"date":"2026-01-02T00:00:00+00:00", "value":295},
        {"date":"2026-01-03T00:00:00+00:00", "value":297},
    ]}]}
    assert parse_lines(data)["TEST"]["last"] is None


def test_rate_fallback_prefers_latest_approved():
    t = validate_tariffs('{"2023":{"EF":{"rate":4,"status":"approved"}},' \
                         '"2024":{"EF":{"rate":5,"status":"approved"}},' \
                         '"2025":{"EF":{"rate":9,"status":"provisional"}}}')
    rate = resolve_tariff(t, 2026, "EF")
    assert rate["rate"] == 5 and rate["source_year"] == 2024
    assert rate["fallback"] is True
    assert resolve_tariff(t, 2025, "EF")["rate"] == 9
    assert resolve_tariff(t, 2024, "CET") is None


def test_b5_same_meter_serial_in_multiple_lots_remains_isolated():
    payload = {"lines":[
        {"compteur":"SHARED-TEST", "lot":"LOT-A", "fluide":"EF",
         "conso":1.0, "indexes":[{"date":"2026-01-01T00:00:00+01:00","value":1.0}]},
        {"compteur":"SHARED-TEST", "lot":"LOT-B", "fluide":"EF",
         "conso":2.0, "indexes":[{"date":"2026-01-01T00:00:00+01:00","value":99.0}]},
    ]}
    meters = parse_lines(payload)
    assert len(meters) == 2
    assert len({x["meter_key"] for x in meters.values()}) == 2
    assert {x["lot"] for x in meters.values()} == {"LOT-A","LOT-B"}
    assert summarize_annual(payload)["EF"]["value"] == 3.0

