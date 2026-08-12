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
from .model import DeviceCapabilities
from .runtime import EshtayaAccountRuntime

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register bundled Lovelace card path."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,
                str(Path(__file__).parent / "frontend"),
                True,
            )
        ]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up all selected IR climate devices."""
    session = async_get_clientsession(hass)
    api = TuyaOpenApi(
        session,
        DATA_CENTERS[entry.data[CONF_DATA_CENTER]],
        entry.data[CONF_ACCESS_ID],
        entry.data[CONF_ACCESS_SECRET],
    )

    coordinators: dict[str, EshtayaIrClimateCoordinator] = {}

    for device_id in entry.data[CONF_DEVICE_IDS]:
        try:
            probe = await api.probe_device(device_id)
        except TuyaApiError as err:
            # Network/auth/device access can genuinely prevent setup.
            raise ConfigEntryNotReady(str(err)) from err

        # A manually selected/stored device is trusted as an IR A/C controller.
        capabilities = DeviceCapabilities.from_probe(
            probe,
            trust_manual=True,
        )

        coordinator = EshtayaIrClimateCoordinator(
            hass,
            entry,
            api,
            device_id,
            probe.device,
            capabilities,
            probe.live_status,
            probe.trace,
        )
        # Do not require Tuya to return a non-empty fresh status here.
        await coordinator.async_refresh()
        coordinators[device_id] = coordinator

    if not coordinators:
        raise ConfigEntryNotReady("No configured devices could be initialized")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = EshtayaAccountRuntime(
        api=api,
        coordinators=coordinators,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
