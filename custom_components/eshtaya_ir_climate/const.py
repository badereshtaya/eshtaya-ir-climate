"""Constants for Eshtaya IR Climate."""

from __future__ import annotations

DOMAIN = "eshtaya_ir_climate"
NAME = "Eshtaya IR Climate"
VERSION = "0.5.0"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_DATA_CENTER = "data_center"
CONF_DEVICE_IDS = "device_ids"
CONF_MANUAL_DEVICE_ID = "manual_device_id"

DEFAULT_SCAN_INTERVAL = 15
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

# Common Tuya DP aliases.
POWER_CODES = (
    "infrared_switch", "switch", "switch_1", "power", "power_switch",
    "ac_switch", "switch_ac", "on_off",
)
TARGET_TEMP_CODES = (
    "target_temp", "temp_set", "temp_set_f", "temperature_set",
    "set_temp", "setting_temp", "target_temperature",
)
CURRENT_TEMP_CODES = (
    "temp_current", "temp_current_f", "temperature_current",
    "current_temp", "room_temp", "indoor_temp", "temperature",
)
MODE_CODES = (
    "mode", "work_mode", "ac_mode", "hvac_mode", "workmode",
)
FAN_CODES = (
    "fan_level", "fan_speed", "windspeed", "wind_speed",
    "fan", "wind_level", "windlevel",
)
HUMIDITY_CODES = (
    "humidity_current", "humidity", "current_humidity", "hum_current",
)
FILTER_LIFE_CODES = ("filter_life", "filter_time", "filter_runtime")
RUNTIME_CODES = ("runtime", "runtime_total", "total_runtime")
FAULT_CODES = ("fault", "fault_code", "alarm")
STATUS_CODES = ("status", "work_status", "running_state")
CHILD_LOCK_CODES = ("child_lock", "lock")
FILTER_RESET_CODES = ("filter_reset", "reset_filter")
RUNTIME_RESET_CODES = ("runtime_total_reset", "runtime_reset")

TUYA_TO_HVAC = {
    "cold": "cool",
    "cool": "cool",
    "cooling": "cool",
    "refrigeration": "cool",
    "warm": "heat",
    "heat": "heat",
    "heating": "heat",
    "hot": "heat",
    "auto": "auto",
    "automatic": "auto",
    "air": "fan_only",
    "fan": "fan_only",
    "fan_only": "fan_only",
    "ventilation": "fan_only",
    "dehumidify": "dry",
    "dehumidification": "dry",
    "dry": "dry",
}

HVAC_TO_TUYA_PREFERENCE = {
    "cool": ("cold", "cool", "cooling", "refrigeration"),
    "heat": ("warm", "heat", "heating", "hot"),
    "auto": ("auto", "automatic"),
    "fan_only": ("air", "fan", "fan_only", "ventilation"),
    "dry": ("dehumidify", "dehumidification", "dry"),
}

FAN_VALUE_NORMALIZATION = {
    "auto": "auto",
    "automatic": "auto",
    "low": "low",
    "min": "low",
    "middle": "medium",
    "medium": "medium",
    "mid": "medium",
    "high": "high",
    "max": "high",
    "quiet": "quiet",
    "silent": "quiet",
    "turbo": "turbo",
    "strong": "turbo",
}

FAN_TO_TUYA_PREFERENCE = {
    "auto": ("auto", "automatic"),
    "low": ("low", "min"),
    "medium": ("middle", "medium", "mid"),
    "high": ("high", "max"),
    "quiet": ("quiet", "silent"),
    "turbo": ("turbo", "strong"),
}

# Tuya category confirmed for IR Air Thermostat / smart A/C controller family.
KNOWN_IR_THERMOSTAT_CATEGORIES = {
    "hwktwkq",
}

IR_PRODUCT_HINTS = (
    "ir air",
    "air conditioner",
    "air conditioning",
    "ac controller",
    "a/c controller",
    "thermostat",
    "infrared",
    "红外空调",
    "空调控制",
    "空调温控",
    "温控器",
)


# v0.5: log-driven IR learning. These are IoT Core log APIs, not IR Control Hub.
IR_LEARNING_CODE = "ir_send"
IR_LEARNING_POLL_SECONDS = 60
IR_BOOTSTRAP_HOURS = 24
IR_LOG_WINDOW_SECONDS = 180
REPORT_LOG_WINDOW_SECONDS = 120
