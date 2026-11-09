"""Trybatec meter, annual consumption and annual estimated cost sensors."""

from __future__ import annotations

from typing import Any
from hashlib import sha256
import json
import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEAL_ID,
    CONF_HEATING_UNIT,
    CONF_TARIFFS,
    DOMAIN,
    FLUIDS,
    FLUID_RATE_UNITS,
    FLUID_UNITS,
)
from .coordinator import TrybatecCoordinator
from .history_devices_b15 import load_historical_inventory
from .parsing import resolve_tariff, validate_tariffs
from .units import normalized_unit, unit_factor


def _rates(entry: ConfigEntry) -> dict[str, dict[str, dict[str, Any]]]:
    """Only validated data is ever persisted by the options flow."""
    try:
        return validate_tariffs(entry.options.get(CONF_TARIFFS, "{}"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose active and API-visible retired physical meters independently."""
    coordinator: TrybatecCoordinator = hass.data[DOMAIN][entry.entry_id]
    account_key = entry.unique_id or entry.entry_id
    known_meter_versions: set[tuple[str, str | None]] = set()
    known_metrics: set[tuple[str, str]] = set()

    def add_new_meters_and_metrics() -> None:
        """Add newly verified meter versions without reloading or re-polling."""
        new: list[SensorEntity] = []
        active_fluids: set[str] = set()
        for serial, meter in coordinator.data["meters"].items():
            if not meter["deposed"]:
                active_fluids.add(meter["fluid"])
            identity = (serial, meter.get("verified_unit"))
            if identity not in known_meter_versions:
                known_meter_versions.add(identity)
                new.append(TrybatecMeterSensor(coordinator, account_key, serial))
        for fluid in active_fluids:
            allowed_metrics = ("volume", "cost", "price")
            if not coordinator.data["annual"][fluid]["unit_verified"]:
                allowed_metrics = ("volume",)
            for metric in allowed_metrics:
                identity = (fluid, metric)
                if identity not in known_metrics:
                    known_metrics.add(identity)
                    new.append(TrybatecAnnualSensor(coordinator, entry, account_key, fluid, metric))
        if new:
            async_add_entities(new)

    add_new_meters_and_metrics()
    # Retired physical counters discovered in earlier *approved* historical
    # inventories remain independently visible even if the portal stops
    # including them in its current index response. They are historical-only,
    # not active totals or extra entries in the Energy dashboard.
    try:
        archived = await load_historical_inventory(hass, entry.entry_id)
    except ValueError:
        # Preserve active sensors when the historical archive is corrupt;
        # do not overwrite the damaged archive or invent retired indexes.
        _LOGGER.error("Trybatec retired meter inventory needs manual recovery")
        archived = {}
    current_identities = {
        (m["lot"], m["fluid"], m["serial"])
        for m in coordinator.data.get("meters", {}).values()
    }
    retired_entities = [
        TrybatecArchivedMeterSensor(account_key, item)
        for item in archived.values()
        if (item["lot"], item["fluid"], item["serial"]) not in current_identities
    ]
    if retired_entities:
        async_add_entities(retired_entities)
    entry.async_on_unload(coordinator.async_add_listener(add_new_meters_and_metrics))


class TrybatecBaseSensor(CoordinatorEntity[TrybatecCoordinator], SensorEntity):
    """Common functionality and account-level device for estimates."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TrybatecCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_should_poll = False


class TrybatecMeterSensor(TrybatecBaseSensor):
    """Cumulative index of a single physical meter (never merged across resets)."""

    def __init__(
        self, coordinator: TrybatecCoordinator, account_key: str, serial: str
    ) -> None:
        super().__init__(coordinator)
        self._serial = serial
        meter = coordinator.data["meters"][serial]
        physical_serial = meter["serial"]
        self._source_unit = meter.get("verified_unit")
        suffix = ("_" + sha256(json.dumps([meter["lot"], meter["fluid"], physical_serial], separators=(",", ":")).encode()).hexdigest()[:16]) if meter.get("identity_collision") else ""
        fluid = meter["fluid"]
        # A new ID prevents old assumed-unit statistics from being silently reused.
        tag = self._source_unit or "unverified"
        self._attr_unique_id = f"{account_key}_{physical_serial}{suffix}_b6_{tag}_index"
        self._attr_name = f"{FLUIDS[fluid]} {physical_serial} index" + (" (unit unverified)" if not self._source_unit else "")
        self._attr_native_unit_of_measurement = normalized_unit(fluid) if self._source_unit else None
        # Preserve the historical active-meter state-class declaration.
        # The property below dynamically disables statistics for retired
        # devices, even when an active meter later becomes deposed.
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING if self._source_unit else None
        self._attr_device_class = (SensorDeviceClass.ENERGY if fluid == "CET" else SensorDeviceClass.WATER) if self._source_unit else None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{account_key}_{physical_serial}{suffix}")},
            "name": f"Trybatec {FLUIDS[fluid]} ({physical_serial})",
            "manufacturer": "Trybatec",
            "model": "Remote meter",
        }

    @property
    def state_class(self) -> SensorStateClass | None:
        meter = self.coordinator.data["meters"].get(self._serial)
        if meter is None or meter.get("deposed") or not self._source_unit:
            return None
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        meter = self.coordinator.data["meters"].get(self._serial)
        if not meter or not meter["last"] or meter.get("verified_unit") != self._source_unit or not self._source_unit:
            return None
        return round(meter["last"][1] * unit_factor(meter["fluid"], self._source_unit), 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meter = self.coordinator.data["meters"].get(self._serial)
        if not meter:
            return {}
        return {
            "lot": meter["lot"],
            "portal_unit": meter.get("portal_unit"),
            "portal_display_unit": meter.get("portal_display_unit"),
            "source_index_unit_origin": meter.get("index_unit_origin"),
            "device_unit_source": meter.get("device_unit_source"),
            "source_index_unit_field_paths": meter.get("index_unit_field_paths", []),
            "source_unit": self._source_unit,
            "unit_verified": self._source_unit is not None and meter.get("verified_unit") == self._source_unit,
            "location": meter["location"],
            "reading_time": meter["last"][0].isoformat() if meter["last"] else None,
            "deposed": meter["deposed"],
            "service_status": "depose" if meter["deposed"] else "en_service",
            "historical_reading_only": bool(meter["deposed"]),
            "last_observed_time": meter["last"][0].isoformat() if meter["last"] else None,
            "has_decreasing_indexes": meter["has_decreasing_indexes"],
        }


class TrybatecArchivedMeterSensor(SensorEntity):
    """Last verified historical reading of a removed physical meter.

    This is an archival snapshot, not a live meter, a reconstructed index,
    or a consumption statistic. No TOTAL_INCREASING state class is assigned.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, account_key: str, snapshot: dict[str, Any]) -> None:
        super().__init__()
        lot, fluid, serial = (
            snapshot["lot"], snapshot["fluid"], snapshot["serial"]
        )
        self._record = dict(snapshot)
        self._attr_unique_id = (
            f"{account_key}_b15_retired_"
            + sha256(
                json.dumps([lot, fluid, serial], separators=(",", ":")).encode()
            ).hexdigest()[:24]
        )
        self._attr_name = f"{FLUIDS[fluid]} {serial} archived index"
        self._attr_native_value = snapshot.get("canonical_index")
        self._attr_native_unit_of_measurement = snapshot.get("normalized_unit")
        self._attr_device_class = (
            SensorDeviceClass.ENERGY if fluid == "CET"
            else SensorDeviceClass.WATER
        ) if self._attr_native_unit_of_measurement else None
        self._attr_state_class = None
        self._attr_device_info = {
            "identifiers": {(
                DOMAIN, f"{account_key}_b15_historical_"
                + sha256(
                    json.dumps([lot, fluid, serial], separators=(",", ":")).encode()
                ).hexdigest()[:24]
            )},
            "name": f"Trybatec historical {FLUIDS[fluid]} ({serial})",
            "manufacturer": "Trybatec",
            "model": "Retired physical meter",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "lot": self._record["lot"], "deposed": True,
            "service_status": "depose",
            "historical_reading_only": True,
            "last_observed_time": self._record["last_reading_at"],
            "source_unit": self._record.get("source_unit"),
            "unit_verified": self._record.get("source_unit") is not None,
            "data_origin": "explicitly_archived_physical_meter",
            "historical_source_fingerprint": self._record["source_fingerprint"],
        }


class TrybatecAnnualSensor(TrybatecBaseSensor):
    """Year-to-date portal estimates and user-configured accounting unit tariffs."""

    def __init__(
        self,
        coordinator: TrybatecCoordinator,
        entry: ConfigEntry,
        account_key: str,
        fluid: str,
        metric: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._fluid = fluid
        self._metric = metric
        self._attr_unique_id = f"{account_key}_{fluid}_{metric}_b6_verified"
        display = {"volume": "YTD usage (estimate)", "cost": "YTD cost (estimate)", "price": "Annual unit price"}
        self._attr_name = f"{FLUIDS[fluid]} {display[metric]}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{account_key}_account")},
            "name": "Trybatec account",
            "manufacturer": "Trybatec",
        }
        if metric == "volume":
            self._attr_native_unit_of_measurement = normalized_unit(fluid)
            self._attr_device_class = SensorDeviceClass.ENERGY if fluid == "CET" else SensorDeviceClass.WATER
            # YTD estimates can be revised and reset each calendar year. Do
            # not register misleading long-term recorder statistics, and avoid
            # the invalid MEASUREMENT state class for energy/water sensors.
            self._attr_state_class = None
        elif metric == "cost":
            self._attr_native_unit_of_measurement = "EUR"
            self._attr_device_class = SensorDeviceClass.MONETARY
            # Monetary year-to-date estimates are revisable; HA disallows
            # MEASUREMENT for the MONETARY device class.
            self._attr_state_class = None
        else:
            self._attr_native_unit_of_measurement = FLUID_RATE_UNITS[fluid]
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        year = str(self.coordinator.data["year"])
        annual = self.coordinator.data["annual"][self._fluid]["value"]
        tariff = resolve_tariff(_rates(self._entry), int(year), self._fluid)
        if not self.coordinator.data["annual"][self._fluid]["unit_verified"]:
            return None
        if self._metric == "volume":
            return annual  # Already converted to canonical unit in parsing.
        if tariff is None:
            return None
        if self._metric == "price":
            return tariff["rate"]
        return round(annual * tariff["rate"], 4) if annual is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = self.coordinator.data["annual"][self._fluid]
        tariff = resolve_tariff(
            _rates(self._entry), self.coordinator.data["year"], self._fluid
        )
        return {
            "year": self.coordinator.data["year"],
            "estimate_only": True,
            "meter_count": summary["meters"],
            "coverage_warning": summary["coverage_warning"],
            "unit_verified": summary["unit_verified"],
            "accounting_status": (
                "fallback_from_prior_year"
                if tariff and tariff["fallback"]
                else tariff["status"] if tariff else "no_tariff"
            ),
            "price_source_year": tariff["source_year"] if tariff else None,
            "note": "Portal period estimates; not approved building charges",
        }
