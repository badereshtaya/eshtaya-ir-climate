"""Diagnostics support for Eshtaya IR Climate."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_ACCESS_SECRET, DOMAIN
from .runtime import EshtayaAccountRuntime

TO_REDACT = {
    CONF_ACCESS_SECRET,
    "local_key",
    "ip",
    "lat",
    "lon",
    "uuid",
    "owner_id",
    "uid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return safe diagnostics for future device compatibility work."""
    runtime: EshtayaAccountRuntime = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, Any] = {}

    for device_id, coordinator in runtime.coordinators.items():
        devices[device_id] = {
            "device": async_redact_data(
                dict(coordinator.device),
                TO_REDACT,
            ),
            "profile": coordinator.capabilities.profile,
            "confidence": coordinator.capabilities.confidence,
            "last_command_route": coordinator.last_command_route,
            "probe_trace": list(coordinator.probe_trace),
            "datapoints": {
                code: {
                    "type": dp.type,
                    "values": dp.values,
                    "writable": dp.writable,
                    "readable": dp.readable,
                }
                for code, dp in coordinator.capabilities.dps.items()
            },
            "status": dict(coordinator.data),
        }

    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": devices,
    }
