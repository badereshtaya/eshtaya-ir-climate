"""Known and inferred Tuya IR climate profiles."""

from __future__ import annotations

from typing import Any

from .const import (
    IR_PRODUCT_HINTS,
    KNOWN_IR_THERMOSTAT_CATEGORIES,
)

# Exact profile verified from Tuya Developer Platform for hwktwkq
# IR Air Thermostat / Smart Air Conditioner Controller family.
HWKTWKQ_PROFILE: dict[str, tuple[str, dict[str, Any], bool, bool]] = {
    "infrared_switch": ("Boolean", {}, True, True),
    "target_temp": (
        "Integer",
        {"unit": "℃", "min": 16, "max": 30, "scale": 0, "step": 1},
        True,
        True,
    ),
    "temp_current": (
        "Integer",
        {"unit": "℃", "min": -200, "max": 1000, "scale": 1, "step": 1},
        False,
        True,
    ),
    "mode": (
        "Enum",
        {"range": ["cold", "warm", "auto", "air", "dehumidify"]},
        True,
        True,
    ),
    "fan_level": (
        "Enum",
        {"range": ["auto", "low", "middle", "high"]},
        True,
        True,
    ),
    "humidity_current": (
        "Integer",
        {"unit": "%", "min": 0, "max": 100, "scale": 0, "step": 1},
        False,
        True,
    ),
    "filter_reset": ("Boolean", {}, True, True),
    "filter_life": (
        "Integer",
        {"unit": "h", "min": 0, "max": 720, "scale": 0, "step": 1},
        False,
        True,
    ),
    "upper_temp": (
        "Integer",
        {"unit": "℃", "min": 16, "max": 30, "scale": 0, "step": 1},
        True,
        True,
    ),
    "lower_temp": (
        "Integer",
        {"unit": "℃", "min": 16, "max": 30, "scale": 0, "step": 1},
        True,
        True,
    ),
    "temp_unit_convert": (
        "Enum",
        {"range": ["c", "f"]},
        True,
        True,
    ),
    "work_type": (
        "Enum",
        {"range": ["scene_1", "scene_2", "scene_3"]},
        True,
        True,
    ),
    "status": (
        "Enum",
        {"range": ["done", "run", "idle"]},
        False,
        True,
    ),
    "first_enter": ("Boolean", {}, True, True),
    "runtime": (
        "Integer",
        {"unit": "h", "min": 0, "max": 999999, "scale": 0, "step": 1},
        False,
        True,
    ),
    "internet_disc_switch": ("Boolean", {}, True, True),
    "runtime_total_reset": ("Boolean", {}, True, True),
    "child_lock": ("Boolean", {}, True, True),
    "ir_send": ("String", {"maxlen": 3072}, True, True),
    "ir_study_code": ("Raw", {"maxlen": 128}, False, True),
}


def product_looks_like_ir_climate(device: dict[str, Any]) -> bool:
    """Detect obvious IR A/C products from metadata in multiple languages."""
    text = " ".join(
        str(device.get(key) or "")
        for key in (
            "name", "product_name", "model",
            "category_name", "sub_type",
        )
    ).lower()
    return any(hint.lower() in text for hint in IR_PRODUCT_HINTS)


def is_known_ir_thermostat(device: dict[str, Any], category: str) -> bool:
    """Return True for exact known category or strong product metadata."""
    return (
        category in KNOWN_IR_THERMOSTAT_CATEGORIES
        or product_looks_like_ir_climate(device)
    )
