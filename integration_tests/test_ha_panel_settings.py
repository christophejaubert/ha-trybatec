"""Shared configuration options: the new panel must not fork native HA storage."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.trybatec.panel_settings import change_panel_settings
from custom_components.trybatec.tariff_validation import tariff_fingerprint

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _setup():
    entry=SimpleNamespace(entry_id="test-shared", options={
        "poll_minutes":720, "sparse_interval_hours":27,
        "zero_index_review_days":1, "log_level":"WARNING",
        "annual_tariffs":'{"2022":{"EF":{"rate":3,"status":"approved"}}}',
        "annual_meter_tariffs":{},
        "meter_units":{"physical-test-key":"m³"},
    })
    def save(target, *, options):
        target.options=deepcopy(options)
    hass=SimpleNamespace(config_entries=SimpleNamespace(
        async_update_entry=Mock(side_effect=save),
    ))
    return hass, SimpleNamespace(entry=entry)


async def _change(hass,coord,**change):
    opts={"poll_minutes":180,"sparse_hours":28,"zero_review_days":0,
          "log_level":"INFO",
          "expected_fingerprint":tariff_fingerprint(coord.entry.options),
          "confirm":True}
    opts.update(change)
    return await change_panel_settings(hass,coord,**opts)


@pytest.mark.asyncio
async def test_shared_settings_save_changes_only_four_options():
    hass,coord=_setup()
    before=deepcopy(coord.entry.options)
    result=await _change(hass,coord)
    assert result["status"]=="saved"
    assert result["config_entry_may_reload"] is True
    assert hass.config_entries.async_update_entry.call_count==1
    assert coord.entry.options["poll_minutes"]==180
    assert coord.entry.options["sparse_interval_hours"]==28
    assert coord.entry.options["zero_index_review_days"]==0
    assert coord.entry.options["log_level"]=="INFO"
    for key in ("annual_tariffs","annual_meter_tariffs","meter_units"):
        assert coord.entry.options[key]==before[key]
    assert result["recorder_writes"] is False
    assert result["energy_writes"] is False


@pytest.mark.asyncio
async def test_shared_settings_reject_unconfirmed_and_stale_without_writes():
    hass,coord=_setup()
    with pytest.raises(ValueError,match="confirmation"):
        await _change(hass,coord,confirm=False)
    with pytest.raises(ValueError,match="Options changed"):
        await _change(hass,coord,expected_fingerprint="0"*64)
    assert hass.config_entries.async_update_entry.call_count==0


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("poll_minutes",59),("poll_minutes",10081),
    ("poll_minutes",True),("sparse_hours",0),
    ("sparse_hours",87601),("zero_review_days",-1),
    ("zero_review_days",36501),("zero_review_days",False),
    ("log_level","PASSWORD"),("sparse_hours",27.5),
])
async def test_invalid_shared_settings_are_rejected_without_side_effects(field,value):
    hass,coord=_setup()
    before=deepcopy(coord.entry.options)
    with pytest.raises(ValueError):
        await _change(hass,coord,**{field:value})
    assert coord.entry.options==before
    assert hass.config_entries.async_update_entry.call_count==0


@pytest.mark.asyncio
async def test_zero_threshold_matches_old_native_options_maximum():
    hass,coord=_setup()
    result=await _change(hass,coord,zero_review_days=36500)
    assert result["status"]=="saved"
    assert coord.entry.options["zero_index_review_days"]==36500


@pytest.mark.asyncio
async def test_unchanged_shared_settings_never_reloads_config_entry():
    hass,coord=_setup()
    result=await _change(
        hass,coord,poll_minutes=720,sparse_hours=27,
        zero_review_days=1,log_level="WARNING",
    )
    assert result["status"]=="unchanged"
    assert hass.config_entries.async_update_entry.call_count==0
