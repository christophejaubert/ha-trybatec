"""Trybatec meter, annual consumption and annual estimated cost sensors."""

from __future__ import annotations

from typing import Any
import json

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
    CONF_TARIFFS,
    DOMAIN,
    FLUIDS,
    FLUID_RATE_UNITS,
    FLUID_UNITS,
)
from .coordinator import TrybatecCoordinator
from .parsing import resolve_tariff, validate_tariffs


def _rates(entry: ConfigEntry) -> dict[str, dict[str, dict[str, Any]]]:
    """Only validated data is ever persisted by the options flow."""
    try:
        return validate_tariffs(entry.options.get(CONF_TARIFFS, "{}"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose one index sensor per active physical meter and aggregate values."""
    coordinator: TrybatecCoordinator = hass.data[DOMAIN][entry.entry_id]
    account_key = entry.unique_id or entry.entry_id
    known_serials: set[str] = set()

    def add_new_meters() -> None:
        new: list[SensorEntity] = []
        for serial, meter in coordinator.data["meters"].items():
            if meter["deposed"] or serial in known_serials:
                continue
            known_serials.add(serial)
            new.append(TrybatecMeterSensor(coordinator, account_key, serial))
        if new:
            async_add_entities(new)

    add_new_meters()
    async_add_entities(
        [
            TrybatecAnnualSensor(coordinator, entry, account_key, fluid, "volume")
            for fluid in FLUIDS
        ]
        + [
            TrybatecAnnualSensor(coordinator, entry, account_key, fluid, "cost")
            for fluid in FLUIDS
        ]
        + [
            TrybatecAnnualSensor(coordinator, entry, account_key, fluid, "price")
            for fluid in FLUIDS
        ]
    )
    entry.async_on_unload(coordinator.async_add_listener(add_new_meters))


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
        fluid = meter["fluid"]
        self._attr_unique_id = f"{account_key}_{serial}_index"
        self._attr_name = f"{FLUIDS[fluid]} {serial} index"
        self._attr_native_unit_of_measurement = FLUID_UNITS[fluid]
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = (
            SensorDeviceClass.ENERGY if fluid == "CET" else SensorDeviceClass.WATER
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{account_key}_{serial}")},
            "name": f"Trybatec {FLUIDS[fluid]} ({serial})",
            "manufacturer": "Trybatec",
            "model": "Remote meter",
        }

    @property
    def native_value(self) -> float | None:
        meter = self.coordinator.data["meters"].get(self._serial)
        if not meter or not meter["last"]:
            return None
        return meter["last"][1]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meter = self.coordinator.data["meters"].get(self._serial)
        if not meter:
            return {}
        return {
            "lot": meter["lot"],
            "location": meter["location"],
            "reading_time": meter["last"][0].isoformat() if meter["last"] else None,
            "deposed": meter["deposed"],
            "has_decreasing_indexes": meter["has_decreasing_indexes"],
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
        self._attr_unique_id = f"{account_key}_{fluid}_{metric}"
        display = {"volume": "YTD usage (estimate)", "cost": "YTD cost (estimate)", "price": "Annual unit price"}
        self._attr_name = f"{FLUIDS[fluid]} {display[metric]}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{account_key}_account")},
            "name": "Trybatec account",
            "manufacturer": "Trybatec",
        }
        if metric == "volume":
            self._attr_native_unit_of_measurement = FLUID_UNITS[fluid]
            self._attr_device_class = (
                SensorDeviceClass.ENERGY if fluid == "CET" else SensorDeviceClass.WATER
            )
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif metric == "cost":
            self._attr_native_unit_of_measurement = "EUR"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_native_unit_of_measurement = FLUID_RATE_UNITS[fluid]
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        year = str(self.coordinator.data["year"])
        annual = self.coordinator.data["annual"][self._fluid]["value"]
        tariff = resolve_tariff(_rates(self._entry), int(year), self._fluid)
        if self._metric == "volume":
            return annual
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
            "accounting_status": (
                "fallback_from_prior_year"
                if tariff and tariff["fallback"]
                else tariff["status"] if tariff else "no_tariff"
            ),
            "price_source_year": tariff["source_year"] if tariff else None,
            "note": "Portal period estimates; not approved building charges",
        }
