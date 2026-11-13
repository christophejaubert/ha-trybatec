"""Synthetic annual Trybatec tariff editing, no JSON input or database writes."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.trybatec.panel_tariffs import (
    change_tariff, effective_rate, tariff_fingerprint, validate_meter_tariffs,
)
from custom_components.trybatec.units import meter_key
from custom_components.trybatec.tariff_validation import validate_edit_rate
from custom_components.trybatec.parsing import validate_tariffs

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _case():
    key=meter_key("LOT-1","EF","METER-1")
    entry=SimpleNamespace(
        entry_id="ci-tariffs", options={
            "annual_tariffs": '{"2022":{"EF":{"rate":2.5,"status":"approved"}}}',
            "poll_minutes": 180,
            "meter_units": {},
        },
    )
    coord=SimpleNamespace(
        entry=entry,
        data={"meters":{
            "METER-1":{"lot":"LOT-1","fluid":"EF","serial":"METER-1"},
        }},
    )
    def update(target, *, options):
        target.options=deepcopy(options)
    hass=SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=Mock(side_effect=update)))
    return hass,coord,key


def test_tariff_validator_fails_closed_on_invalid_amount_or_identity():
    key=meter_key("LOT-1","EF","METER-1")
    valid={"2022":{key:{"rate":3.5,"status":"approved"}}}
    assert validate_meter_tariffs(valid)==valid
    for wrong in [
        {"2022":{key:{"rate":-1,"status":"approved"}}},
        {"2022":{key:{"rate":float("nan"),"status":"approved"}}},
        {"2022":{key:{"rate":2,"status":"unverified"}}},
        {"2022":{key:{"rate":True,"status":"approved"}}},
        {"2022":{key:{"rate":2,"status":"approved","extra":1}}},
        {"2022":{"wrong-key":{"rate":1,"status":"approved"}}},
        {"1899":{key:{"rate":1,"status":"approved"}}},
    ]:
        with pytest.raises(ValueError):
            validate_meter_tariffs(wrong)


def test_tariff_resolution_requires_same_year_and_prefers_meter_override():
    key=meter_key("LOT-1","EF","METER-1")
    table={"2022":{"EF":{"rate":2.5,"status":"approved"}}}
    overrides={"2022":{key:{"rate":3.1,"status":"provisional"}}}
    assert effective_rate(table,overrides,2022,"EF",key)=={
        "rate":3.1,"status":"provisional","origin":"meter_override","source_year":2022,
    }
    assert effective_rate(table,overrides,2022,"EF")["origin"]=="fluid_default"
    assert effective_rate(table,overrides,2023,"EF",key) is None


@pytest.mark.asyncio
async def test_tariff_set_remove_preserves_existing_years_and_options():
    hass,coord,key=_case()
    prior=deepcopy(coord.entry.options)
    sha=tariff_fingerprint(prior)
    with pytest.raises(ValueError,match="confirmation"):
        await change_tariff(hass,coord,year=2023,fluid="EF",rate=4.2,
            status="provisional",physical_key=None,remove=False,
            expected_fingerprint=sha,confirmed=False)
    assert coord.entry.options==prior
    changed=await change_tariff(hass,coord,year=2023,fluid="EF",rate=4.2,
        status="provisional",physical_key=None,remove=False,
        expected_fingerprint=sha,confirmed=True)
    assert changed["status"]=="saved" and changed["recorder_unchanged"]
    assert coord.entry.options["poll_minutes"]==180
    assert '"2022"' in coord.entry.options["annual_tariffs"]
    assert '"2023"' in coord.entry.options["annual_tariffs"]
    assert hass.config_entries.async_update_entry.call_count==1
    with pytest.raises(ValueError,match="Stale"):
        await change_tariff(hass,coord,year=2023,fluid="EF",rate=10,
            status="approved",physical_key=None,remove=False,
            expected_fingerprint=sha,confirmed=True)
    assert hass.config_entries.async_update_entry.call_count==1
    sha2=changed["options_fingerprint"]
    await change_tariff(hass,coord,year=2023,fluid="EF",rate=None,
        status="provisional",physical_key=None,remove=True,
        expected_fingerprint=sha2,confirmed=True)
    assert '"2023"' not in coord.entry.options["annual_tariffs"]


@pytest.mark.asyncio
async def test_meter_override_requires_exact_physical_identity_and_reverts_on_delete():
    hass,coord,key=_case()
    sha=tariff_fingerprint(coord.entry.options)
    with pytest.raises(ValueError,match="Meter does not belong"):
        await change_tariff(hass,coord,year=2022,fluid="CET",rate=5,
            status="approved",physical_key=key,remove=False,
            expected_fingerprint=sha,confirmed=True)
    assert hass.config_entries.async_update_entry.call_count==0
    result=await change_tariff(hass,coord,year=2022,fluid="EF",rate=3.75,
        status="approved",physical_key=key,remove=False,
        expected_fingerprint=sha,confirmed=True)
    assert coord.entry.options["annual_meter_tariffs"]["2022"][key]["rate"]==3.75
    assert '"rate":2.5' in coord.entry.options["annual_tariffs"]
    assert effective_rate(
        __import__("json").loads(coord.entry.options["annual_tariffs"]),
        coord.entry.options["annual_meter_tariffs"],2022,"EF",key
    )["rate"]==3.75
    await change_tariff(hass,coord,year=2022,fluid="EF",rate=None,
        status="approved",physical_key=key,remove=True,
        expected_fingerprint=result["options_fingerprint"],confirmed=True)
    assert coord.entry.options["annual_meter_tariffs"]=={}


@pytest.mark.asyncio
async def test_rate_validation_never_persists_bad_values():
    hass,coord,key=_case()
    sha=tariff_fingerprint(coord.entry.options)
    for bad in (-2,float("nan"),float("inf"),True,"20",1e8):
        with pytest.raises(ValueError):
            await change_tariff(hass,coord,year=2022,fluid="EF",
                rate=bad,status="approved",physical_key=None,remove=False,
                expected_fingerprint=sha,confirmed=True)
    assert hass.config_entries.async_update_entry.call_count==0



def test_new_tariff_precision_contract_does_not_change_legacy_data() -> None:
    assert validate_edit_rate(0) == 0.0
    assert validate_edit_rate(1.234567) == 1.234567
    assert validate_edit_rate(1000000) == 1000000.0
    # Old stored rates are loaded by the legacy parser, not silently truncated.
    legacy = '{"2022":{"EF":{"rate":1.23456789,"status":"approved"}}}'
    assert validate_tariffs(legacy)["2022"]["EF"]["rate"] == 1.23456789
    for invalid in (-1, 1000000.000001, float("inf"), float("nan"),
                    True, "1.2", 0.1234567, 1e-7):
        with pytest.raises(ValueError):
            validate_edit_rate(invalid)


@pytest.mark.asyncio
async def test_new_rate_precision_rejected_without_persisting() -> None:
    hass, coord, _key = _case()
    fingerprint = tariff_fingerprint(coord.entry.options)
    original = deepcopy(coord.entry.options)
    for rate in (0.1234567, 1.23456789, 1e-7, 1000000.000001):
        with pytest.raises(ValueError):
            await change_tariff(
                hass, coord, year=2024, fluid="EF", rate=rate,
                status="approved", physical_key=None, remove=False,
                expected_fingerprint=fingerprint, confirmed=True,
            )
    assert coord.entry.options == original
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_new_year_rate_and_specific_override_preserve_legacy_and_scope() -> None:
    hass, coord, key = _case()
    baseline = deepcopy(coord.entry.options)
    fingerprint = tariff_fingerprint(baseline)
    result = await change_tariff(
        hass, coord, year=2040, fluid="EF", rate=1.234567,
        status="provisional", physical_key=None, remove=False,
        expected_fingerprint=fingerprint, confirmed=True,
    )
    assert result["recorder_unchanged"] is True
    assert result["energy_unchanged"] is True
    stored = validate_tariffs(coord.entry.options["annual_tariffs"])
    assert stored["2022"]["EF"]["rate"] == 2.5
    assert stored["2040"]["EF"]["rate"] == 1.234567
    assert coord.entry.options["poll_minutes"] == baseline["poll_minutes"]
    result = await change_tariff(
        hass, coord, year=2040, fluid="EF", rate=3.333333,
        status="approved", physical_key=key, remove=False,
        expected_fingerprint=result["options_fingerprint"], confirmed=True,
    )
    assert effective_rate(
        stored, coord.entry.options["annual_meter_tariffs"], 2040, "EF", key
    )["rate"] == 3.333333
    assert effective_rate(
        stored, coord.entry.options["annual_meter_tariffs"], 2040, "EF"
    )["rate"] == 1.234567
    assert effective_rate(
        stored, coord.entry.options["annual_meter_tariffs"], 2039, "EF", key
    ) is None
    await change_tariff(
        hass, coord, year=2040, fluid="EF", rate=None, status="provisional",
        physical_key=key, remove=True,
        expected_fingerprint=result["options_fingerprint"], confirmed=True,
    )
    assert coord.entry.options["annual_meter_tariffs"] == {}
    assert coord.entry.options["annual_tariffs"] == (
        '{"2022":{"EF":{"rate":2.5,"status":"approved"}},'
        '"2040":{"EF":{"rate":1.234567,"status":"provisional"}}}'
    )


def test_tariff_websocket_commands_retain_server_side_admin_guards() -> None:
    """AST tests protect the decorator contract without using production HA."""
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "custom_components/trybatec"
    for filename, function in (
        ("panel_tariffs.py", "ws_panel_tariff_change"),
        ("panel_tariff_years.py", "ws_panel_tariff_years"),
    ):
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        target = next(
            n for n in tree.body
            if isinstance(n, ast.AsyncFunctionDef) and n.name == function
        )
        decorators = [
            ast.unparse(decorator) for decorator in target.decorator_list
        ]
        assert "websocket_api.require_admin" in decorators
        assert any("websocket_api.websocket_command" in d for d in decorators)


@pytest.mark.asyncio
async def test_legacy_structures_unchanged_on_unrelated_common_rate_edit() -> None:
    """Unmodified bare numbers and legacy metadata survive a new year."""
    import json

    hass, coord, key = _case()
    coord.entry.options["annual_tariffs"] = (
        '{"2020":{"ECS":1.23456789,'
        '"CET":{"rate":0.04,"status":"approved","legacy_note":"retained"}},'
        '"2022":{"EF":{"rate":2.5,"status":"approved"}}}'
    )
    previous = json.loads(coord.entry.options["annual_tariffs"])
    result = await change_tariff(
        hass, coord, year=2040, fluid="EF", rate=3.0,
        status="approved", physical_key=None, remove=False,
        expected_fingerprint=tariff_fingerprint(coord.entry.options),
        confirmed=True,
    )
    stored = json.loads(coord.entry.options["annual_tariffs"])
    assert stored["2020"] == previous["2020"]
    assert type(stored["2020"]["ECS"]) is float
    assert stored["2020"]["CET"]["legacy_note"] == "retained"
    assert stored["2022"] == previous["2022"]
    assert stored["2040"]["EF"]["rate"] == 3.0
    assert result["status"] == "saved"
    assert hass.config_entries.async_update_entry.call_count == 1


@pytest.mark.asyncio
async def test_meter_override_never_reserializes_legacy_json_tariffs() -> None:
    """Override-only changes must retain the exact original option text."""
    hass, coord, key = _case()
    raw = '{ "2022" : { "EF" : 2.5 }, "2021":{"ECS":3.125} }'
    coord.entry.options["annual_tariffs"] = raw
    fingerprint = tariff_fingerprint(coord.entry.options)
    result = await change_tariff(
        hass, coord, year=2022, fluid="EF", rate=4.123456,
        status="provisional", physical_key=key, remove=False,
        expected_fingerprint=fingerprint, confirmed=True,
    )
    assert coord.entry.options["annual_tariffs"] == raw
    assert coord.entry.options["annual_meter_tariffs"]["2022"][key]["rate"] == 4.123456
    await change_tariff(
        hass, coord, year=2022, fluid="EF", rate=None,
        status="provisional", physical_key=key, remove=True,
        expected_fingerprint=result["options_fingerprint"], confirmed=True,
    )
    assert coord.entry.options["annual_tariffs"] == raw
    assert coord.entry.options["annual_meter_tariffs"] == {}
    assert hass.config_entries.async_update_entry.call_count == 2


@pytest.mark.asyncio
async def test_edit_legacy_record_preserves_its_existing_auxiliary_fields() -> None:
    """An explicitly edited rate must not silently erase legacy metadata."""
    import json

    hass, coord, _key = _case()
    coord.entry.options["annual_tariffs"] = (
        '{"2022":{"EF":{"rate":2.5,"status":"approved",'
        '"legacy_note":"keep"}}}'
    )
    await change_tariff(
        hass, coord, year=2022, fluid="EF", rate=2.75,
        status="provisional", physical_key=None, remove=False,
        expected_fingerprint=tariff_fingerprint(coord.entry.options),
        confirmed=True,
    )
    saved = json.loads(coord.entry.options["annual_tariffs"])["2022"]["EF"]
    assert saved == {
        "rate": 2.75, "status": "provisional", "legacy_note": "keep",
    }
    assert hass.config_entries.async_update_entry.call_count == 1
