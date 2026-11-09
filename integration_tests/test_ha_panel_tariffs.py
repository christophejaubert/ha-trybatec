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
