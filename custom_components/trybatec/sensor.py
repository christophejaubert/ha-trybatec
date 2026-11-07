"""Trybatec meter, annual consumption and annual estimated cost sensors."""

from __future__ import annotations

from typing import Any
import json
from hashlib import sha256

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
from .units import selected_heat_unit, to_kwh


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
    known_serials: set[tuple[str, str, str]] = set()
    known_fluids: set[str] = set()

    def add_new_meters_and_metrics() -> None:
        """Publish only fluids actually observed; supports water-only accounts."""
        new: list[SensorEntity] = []
        active_fluids: set[str] = set()
        for meter_key, meter in coordinator.data["meters"].items():
            if meter["deposed"]:
                continue
            active_fluids.add(meter["fluid"])
            if meter_key not in known_serials:
                known_serials.add(meter_key)
                new.append(TrybatecMeterSensor(coordinator, entry, account_key, meter_key))
        for fluid in FLUIDS:
            if fluid in active_fluids and fluid not in known_fluids:
                known_fluids.add(fluid)
                new.extend(
                    TrybatecAnnualSensor(coordinator, entry, account_key, fluid, metric)
                    for metric in ("volume", "cost", "price")
                )
        if new:
            async_add_entities(new)

    add_new_meters_and_metrics()
    entry.async_on_unload(coordinator.async_add_listener(add_new_meters_and_metrics))


class TrybatecBaseSensor(CoordinatorEntity[TrybatecCoordinator], SensorEntity):
    """Common functionality and account-level device for estimates."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TrybatecCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_should_poll = False


class TrybatecMeterSensor(TrybatecBaseSensor):
    """One physical meter, scoped by account + lot + fluid + serial."""

    def __init__(
        self, coordinator: TrybatecCoordinator, entry: ConfigEntry,
        account_key: str, meter_key: tuple[str, str, str],
    ) -> None:
        super().__init__(coordinator)
        self._key = meter_key
        meter = coordinator.data["meters"][meter_key]
        lot, fluid, serial = meter_key
        self._source_unit = selected_heat_unit(entry.options, lot, serial) if fluid == "CET" else None
        # Composite identity prevents future collisions between different lots.
        opaque = sha256(f"{account_key}\0{lot}\0{fluid}\0{serial}".encode()).hexdigest()[:24]
        self._attr_unique_id = f"{account_key}_{opaque}_{self._source_unit or 'raw'}_index"
        self._attr_name = f"{FLUIDS[fluid]} {serial} index" + (
            " (unverified unit)" if fluid == "CET" and not self._source_unit else ""
        )
        self._attr_native_unit_of_measurement = (
            "kWh" if fluid == "CET" and self._source_unit else FLUID_UNITS[fluid]
        )
        self._attr_state_class = (
            SensorStateClass.TOTAL_INCREASING if fluid != "CET" or self._source_unit else None
        )
        self._attr_device_class = (
            SensorDeviceClass.ENERGY if fluid == "CET" and self._source_unit
            else SensorDeviceClass.WATER if fluid != "CET" else None
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{account_key}_{opaque}")},
            "name": f"Trybatec {FLUIDS[fluid]} ({serial})",
            "manufacturer": "Trybatec",
            "model": "Remote meter",
        }

    @property
    def native_value(self) -> float | None:
        meter = self.coordinator.data["meters"].get(self._key)
        if not meter or not meter["last"]:
            return None
        value = meter["last"][1]
        return to_kwh(value, self._source_unit) if self._key[1] == "CET" and self._source_unit else value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meter = self.coordinator.data["meters"].get(self._key)
        if not meter:
            return {}
        return {
            "lot": meter["lot"],
            "location": meter["location"],
            "reading_time": meter["last"][0].isoformat() if meter["last"] else None,
            "deposed": meter["deposed"],
            "has_decreasing_indexes": meter["has_decreasing_indexes"],
            "source_unit_verified": self._source_unit if self._key[1] == "CET" else None,
            "unit_confirmation_required": self._key[1] == "CET" and not self._source_unit,
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
        if self._fluid == "CET":
            # Each serial may use a different unit; no account-level guess.
            meters = [m for m in self.coordinator.data["meters"].values()
                      if m["fluid"] == "CET" and m["indexes"] and
                      m["period_consumption"] is not None]
            if not meters:
                return None
            amounts = []
            for m in meters:
                unit = selected_heat_unit(self._entry.options, m["lot"], m["serial"])
                if unit is None:
                    return None
                amounts.append(to_kwh(m["period_consumption"], unit))
            annual = round(sum(amounts), 6)
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
            "heating_units_require_per_meter_confirmation": self._fluid == "CET",
        }
