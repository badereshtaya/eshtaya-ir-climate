"""Eshtaya IR Climate integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TuyaApiError, TuyaOpenApi
from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DATA_CENTER,
    CONF_DEVICE_IDS,
    DATA_CENTERS,
    DOMAIN,
    FRONTEND_URL,
)
from .coordinator import EshtayaIrClimateCoordinator
from .model import DeviceCapabilities, merge_verified_ir_thermostat_profile
from .runtime import EshtayaAccountRuntime

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the bundled animated Lovelace card resource path."""
    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,
                str(frontend_dir),
                True,
            )
        ]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Tuya cloud project and all selected IR A/C devices."""
    session = async_get_clientsession(hass)
    api = TuyaOpenApi(
        session,
        DATA_CENTERS[entry.data[CONF_DATA_CENTER]],
        entry.data[CONF_ACCESS_ID],
        entry.data[CONF_ACCESS_SECRET],
    )

    coordinators: dict[str, EshtayaIrClimateCoordinator] = {}
    try:
        for device_id in entry.data[CONF_DEVICE_IDS]:
            device = await api.get_device(device_id)
            spec = await api.get_specification(device_id)
            live_status = await api.get_status(device_id)

            functions = spec.get("functions")
            if not isinstance(functions, list) or not functions:
                category = str(
                    spec.get("category")
                    or device.get("category")
                    or ""
                ).strip()
                if category:
                    try:
                        category_spec = await api.get_category_functions(category)
                    except TuyaApiError:
                        category_spec = {}
                    category_functions = category_spec.get("functions")
                    if isinstance(category_functions, list) and category_functions:
                        spec = dict(spec)
                        spec["functions"] = category_functions

            spec = merge_verified_ir_thermostat_profile(spec, live_status)
            capabilities = DeviceCapabilities.from_specification(spec)
            if not capabilities.climate_compatible:
                continue

            coordinator = EshtayaIrClimateCoordinator(
                hass,
                entry,
                api,
                device_id,
                device,
                capabilities,
            )
            await coordinator.async_config_entry_first_refresh()
            coordinators[device_id] = coordinator
    except TuyaApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    if not coordinators:
        raise ConfigEntryNotReady(
            "No selected device currently exposes a compatible IR climate schema"
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = EshtayaAccountRuntime(
        api=api,
        coordinators=coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
