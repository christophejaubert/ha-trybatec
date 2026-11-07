"""Constants for the unofficial Trybatec Home Assistant integration."""

DOMAIN = "trybatec"
API_ORIGIN = "https://portail.trybatec.fr"
API_BASE = f"{API_ORIGIN}/api/v1"
CONF_DEAL_ID = "deal_id"
CONF_TARIFFS = "annual_tariffs"
CONF_POLL_MINUTES = "poll_minutes"
CONF_HEATING_UNIT = "heating_unit"
HEATING_UNITS = ("unverified", "kWh", "MWh", "GJ")
DEFAULT_POLL_MINUTES = 720
MIN_POLL_MINUTES = 60
FLUIDS = {"EF": "Cold water", "ECS": "Hot water", "CET": "Heating"}
FLUID_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
FLUID_RATE_UNITS = {"EF": "EUR/m³", "ECS": "EUR/m³", "CET": "EUR/kWh"}
TIMEZONE = "Europe/Paris"
