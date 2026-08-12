"""Constants for Eshtaya IR Climate."""

from __future__ import annotations

DOMAIN = "eshtaya_ir_climate"
NAME = "Eshtaya IR Climate"
VERSION = "0.2.0"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DATA_CENTER = "data_center"
CONF_DEVICE_IDS = "device_ids"
CONF_MANUAL_DEVICE_ID = "manual_device_id"

DEFAULT_SCAN_INTERVAL = 30
MAX_DISCOVERY_DEVICES = 100
DISCOVERY_CONCURRENCY = 5

FRONTEND_URL = "/eshtaya_ir_climate/frontend"

DATA_CENTERS: dict[str, str] = {
    "china": "https://openapi.tuyacn.com",
    "western_america": "https://openapi.tuyaus.com",
    "eastern_america": "https://openapi-ueaz.tuyaus.com",
    "central_europe": "https://openapi.tuyaeu.com",
    "western_europe": "https://openapi-weaz.tuyaeu.com",
    "india": "https://openapi.tuyain.com",
    "singapore": "https://openapi-sg.iotbing.com",
}

DATA_CENTER_LABELS: dict[str, str] = {
    "china": "China Data Center",
    "western_america": "Western America Data Center",
    "eastern_america": "Eastern America Data Center",
    "central_europe": "Central Europe Data Center",
    "western_europe": "Western Europe Data Center",
    "india": "India Data Center",
    "singapore": "Singapore Data Center",
}

# Common Tuya datapoint aliases used by IR air-conditioner controllers.
POWER_CODES = ("infrared_switch", "switch", "switch_1", "power")
TARGET_TEMP_CODES = ("target_temp", "temp_set", "temp_set_f", "temperature_set")
CURRENT_TEMP_CODES = ("temp_current", "temp_current_f", "temperature_current")
MODE_CODES = ("mode", "work_mode")
FAN_CODES = ("fan_level", "fan_speed", "windspeed", "wind_speed")
HUMIDITY_CODES = ("humidity_current", "humidity")
FILTER_LIFE_CODES = ("filter_life",)
RUNTIME_CODES = ("runtime", "runtime_total")
FAULT_CODES = ("fault",)
STATUS_CODES = ("status",)
CHILD_LOCK_CODES = ("child_lock",)
FILTER_RESET_CODES = ("filter_reset",)
RUNTIME_RESET_CODES = ("runtime_total_reset",)

TUYA_TO_HVAC = {
    "cold": "cool",
    "cool": "cool",
    "cooling": "cool",
    "warm": "heat",
    "heat": "heat",
    "heating": "heat",
    "auto": "auto",
    "automatic": "auto",
    "air": "fan_only",
    "fan": "fan_only",
    "fan_only": "fan_only",
    "dehumidify": "dry",
    "dehumidification": "dry",
    "dry": "dry",
}

HVAC_TO_TUYA_PREFERENCE = {
    "cool": ("cold", "cool", "cooling"),
    "heat": ("warm", "heat", "heating"),
    "auto": ("auto", "automatic"),
    "fan_only": ("air", "fan", "fan_only"),
    "dry": ("dehumidify", "dehumidification", "dry"),
}

FAN_VALUE_NORMALIZATION = {
    "auto": "auto",
    "automatic": "auto",
    "low": "low",
    "middle": "medium",
    "medium": "medium",
    "mid": "medium",
    "high": "high",
    "quiet": "quiet",
    "silent": "quiet",
    "turbo": "turbo",
    "strong": "turbo",
}

FAN_TO_TUYA_PREFERENCE = {
    "auto": ("auto", "automatic"),
    "low": ("low",),
    "medium": ("middle", "medium", "mid"),
    "high": ("high",),
    "quiet": ("quiet", "silent"),
    "turbo": ("turbo", "strong"),
}
