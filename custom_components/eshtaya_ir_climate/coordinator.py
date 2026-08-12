"""Data coordinator for Eshtaya IR Climate."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TuyaApiError, TuyaAuthError, TuyaOpenApi
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .model import DeviceCapabilities

_LOGGER = logging.getLogger(__name__)


class EshtayaIrClimateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Tuya status polling for one device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TuyaOpenApi,
        device_id: str,
        device: dict[str, Any],
        capabilities: DeviceCapabilities,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )
        self.api = api
        self.device_id = device_id
        self.device = device
        self.capabilities = capabilities

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_status(self.device_id)
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            raise UpdateFailed(str(err)) from err

    async def async_send(self, code: str, value: Any) -> None:
        """Send a command and request an updated cloud state."""
        try:
            await self.api.send_command(self.device_id, code, value)
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            raise UpdateFailed(str(err)) from err

        await self.async_request_refresh()
