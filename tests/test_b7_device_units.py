"""Synthetic regressions for the actual Trybatec /device?id=UUID metadata.

No actual meter UUID, home identifier, token, email or request header appears
in this suite.
"""
import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from custom_components.trybatec.api import TrybatecClient
from custom_components.trybatec.device_units import (
    candidate_devices, candidates_from_index_line,
    identity_of, merge_device_units, trusted_device_unit, uuid_text,
)
from custom_components.trybatec.parsing import parse_lines, summarize_annual
from custom_components.trybatec.history import build_history, summarize_preview
from custom_components.trybatec.units import portal_index_unit, meter_key

UUID = "11111111-1111-4111-8111-111111111111"
ANOTHER = "22222222-2222-4222-8222-222222222222"
DEAL = "33333333-3333-4333-8333-333333333333"


def line(serial="FAKE-CET", fluid="CET", lot="TEST-LOT", **fields):
    return {
        "compteur": serial, "fluide": fluid, "lot": lot, "conso": 10,
        "indexes": [
            {"date": "2026-01-01T00:00:00+01:00", "value": 100},
            {"date": "2026-01-02T00:00:00+01:00", "value": 110},
        ],
        **fields,
    }


def device(uuid=UUID, *, serial="FAKE-CET", fluid="CET", lot="TEST-LOT",
           unite="KWh", deal=DEAL):
    return {
        "id": uuid, "serialNumber": serial, "fluidCode": fluid,
        "lot": lot, "unite": unite, "dealUid": deal,
        "type": "FAKE thermal meter",
    }


class Reply:
    def __init__(self, status, data):
        self.status, self.data = status, data
        self.content_length = 100
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def json(self, **kwargs):
        return self.data


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.request_opts = []
    def get(self, url, **options):
        self.urls.append(url)
        self.request_opts.append(options)
        return self.responses.pop(0)
    def post(self, url, **kwargs):
        return Reply(200, {"token": "TEST-ONLY"})


def test_actual_metadata_field_KWh_and_explicit_physical_identity():
    result = trusted_device_unit(device(), ("TEST-LOT", "CET", "FAKE-CET"), UUID, deal_id=DEAL)
    assert result == "kWh"
    assert trusted_device_unit(device(), ("TEST-LOT", "EF", "FAKE-CET"), UUID) is None
    assert trusted_device_unit(device(), ("OTHER-LOT", "CET", "FAKE-CET"), UUID) is None
    assert trusted_device_unit(device(unite="watts"), ("TEST-LOT", "CET", "FAKE-CET"), UUID) is None
    assert trusted_device_unit(device(deal=ANOTHER), ("TEST-LOT", "CET", "FAKE-CET"), UUID, DEAL) is None
    assert uuid_text(UUID) == UUID
    assert uuid_text(345321) is None
    assert uuid_text("not a uuid") is None


def test_merge_device_metadata_with_index_line_normalizes_kwh():
    payload = {"lines": [line()]}
    stats = merge_device_units([payload], {UUID: device()}, deal_id=DEAL)
    assert stats["matched_lines"] == 1
    assert portal_index_unit(payload["lines"][0]) == "kWh"
    assert payload["lines"][0]["_device_unit_source"] == "validated_device_metadata"
    parsed = parse_lines(payload)["FAKE-CET"]
    assert parsed["verified_unit"] if "verified_unit" in parsed else parsed["portal_unit"] == "kWh"
    assert parsed["index_unit_origin"] == "validated_device_metadata"
    assert summarize_annual(payload)["CET"]["value"] == 10
    history = build_history([payload], date(2026, 1, 1), date(2026, 1, 3))
    assert summarize_preview(history)["CET"]["unit_status"] == "verified"


def test_never_cross_assign_same_serial_across_lots_or_fluids():
    p = {"lines": [line(lot="OTHER-LOT"), line(serial="DIFFERENT", fluid="EF")]}
    stats = merge_device_units([p], {UUID: device()}, deal_id=DEAL)
    assert stats["matched_lines"] == 0 and stats["unmatched_lines"] == 2
    assert all("indexUnit" not in item for item in p["lines"])


def test_duplicate_device_identity_with_conflicting_ids_fails_closed():
    p = {"lines": [line()]}
    result = merge_device_units([p], {UUID: device(), ANOTHER: device(ANOTHER)}, deal_id=DEAL)
    assert result["ambiguous_lines"] == 1
    assert "indexUnit" not in p["lines"][0]


def test_explicit_index_unit_conflicting_with_detail_blocks_energy():
    p = {"lines": [line(indexUnit="MWh")]}
    merge_device_units([p], {UUID: device()}, deal_id=DEAL)
    assert portal_index_unit(p["lines"][0]) == "conflict"
    assert summarize_annual(p)["CET"]["value"] is None


def test_list_response_shapes_and_strict_identity():
    assert candidate_devices([device()])[0]["serialNumber"] == "FAKE-CET"
    assert candidate_devices({"items": [device()]})[0]["unite"] == "KWh"
    assert candidate_devices({"data": {"results": [device()]}})[0]["id"] == UUID
    assert candidates_from_index_line(line(deviceUuid=UUID)) == {UUID}
    assert candidates_from_index_line(line(deviceId=345321)) == set()
    assert identity_of(device()) == ("TEST-LOT", "CET", "FAKE-CET")
    with pytest.raises(ValueError):
        candidate_devices({"unexpected": []})


def test_directory_lookup_and_detail_used_only_for_matched_meter():
    payload = {"lines": [line()]}
    session = Session([
        Reply(200, {"devices": [device(), device(ANOTHER, serial="NOT-OURS")]}),
        Reply(200, device()),
    ])
    client = TrybatecClient(session, "user", "password")
    async def run():
        stats = await client.enrich_meter_units([payload], DEAL)
        assert stats["matched_lines"] == 1
        assert len(session.urls) == 2
        assert session.urls[0].endswith("/devices")
        assert session.urls[1].endswith("/device")
        assert session.request_opts[1]["params"] == {"id": UUID}
        # Cache both directory and UUID details after first enrichment.
        assert (await client.enrich_meter_units([payload], DEAL))["matched_lines"] == 1
        assert len(session.urls) == 2
    asyncio.run(run())


def test_direct_index_uuid_works_even_when_directory_endpoint_missing():
    payload = {"lines": [line(deviceUuid=UUID)]}
    session = Session([Reply(404, {}), Reply(200, device())])
    client = TrybatecClient(session, "user", "password")
    assert asyncio.run(client.enrich_meter_units([payload], DEAL))["matched_lines"] == 1
    assert session.urls[1].endswith("/device")


def test_scoped_uuid_option_enables_detail_fetch_without_directory():
    payload = {"lines": [line()]}
    session = Session([Reply(404, {}), Reply(200, device())])
    client = TrybatecClient(session, "user", "password")
    option = {meter_key("TEST-LOT", "CET", "FAKE-CET"): UUID}
    result = asyncio.run(client.enrich_meter_units([payload], DEAL, device_uuids=option))
    assert result["matched_lines"] == 1
    assert payload["lines"][0]["indexUnit"] == "kWh"


def test_scoped_uuid_option_never_grants_a_different_meter_unit():
    payload = {"lines": [line()]}
    session = Session([Reply(404, {}), Reply(200, device(serial="OTHER"))])
    client = TrybatecClient(session, "user", "password")
    option = {meter_key("TEST-LOT", "CET", "FAKE-CET"): UUID}
    result = asyncio.run(client.enrich_meter_units([payload], DEAL, device_uuids=option))
    assert result["matched_lines"] == 0
    assert "indexUnit" not in payload["lines"][0]
