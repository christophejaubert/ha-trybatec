"""Constants for the unofficial Trybatec Home Assistant integration."""

DOMAIN = "trybatec"
# Only newly created entries opt into stable physical IDs. Legacy entries
# remain unchanged until an explicitly reviewed migration is implemented.
CONF_STABLE_METER_IDENTITIES = "stable_meter_identities"
API_ORIGIN = "https://portail.trybatec.fr"
API_BASE = f"{API_ORIGIN}/api/v1"
CONF_DEAL_ID = "deal_id"
CONF_TARIFFS = "annual_tariffs"
CONF_METER_TARIFFS = "annual_meter_tariffs"  # Optional year-by-physical-meter override.
CONF_POLL_MINUTES = "poll_minutes"
CONF_HEATING_UNIT = "heating_unit"  # Legacy global setting; not trusted for new meter identities.
CONF_METER_UNITS = "meter_units"
CONF_DEVICE_UUIDS = "device_uuids"
CONF_LOG_LEVEL = "log_level"
CONF_SPARSE_HOURS = "sparse_interval_hours"
DEFAULT_SPARSE_HOURS = 27
CONF_ZERO_REVIEW_DAYS = "zero_index_review_days"
DEFAULT_ZERO_REVIEW_DAYS = 1
DEFAULT_LOG_LEVEL = "WARNING"
LOG_LEVELS = ("ERROR", "WARNING", "INFO", "DEBUG")
HEATING_UNITS = ("unverified", "kWh", "MWh", "GJ")
DEFAULT_POLL_MINUTES = 720
MIN_POLL_MINUTES = 60
FLUIDS = {"EF": "Cold water", "ECS": "Hot water", "CET": "Heating"}
FLUID_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
FLUID_RATE_UNITS = {"EF": "EUR/m³", "ECS": "EUR/m³", "CET": "EUR/kWh"}
TIMEZONE = "Europe/Paris"
