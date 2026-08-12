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
    """Coordinate one Tuya IR climate controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TuyaOpenApi,
        device_id: str,
        device: dict[str, Any],
        capabilities: DeviceCapabilities,
        initial_status: dict[str, Any],
        probe_trace: list[str],
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
        self.probe_trace = probe_trace
        self.last_command_route: str | None = None

        # Never block creation just because Tuya's status surface is empty.
        # Keep any known cloud state; otherwise seed conservative UI defaults.
        self.data = dict(initial_status)
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        caps = self.capabilities
        if caps.power and caps.power.code not in self.data:
            self.data[caps.power.code] = False
        if caps.target_temp and caps.target_temp.code not in self.data:
            minimum = caps.target_temp.minimum or 16
            maximum = caps.target_temp.maximum or 30
            self.data[caps.target_temp.code] = caps.target_temp.encode_number(
                min(max(24, minimum), maximum)
            )
        if caps.mode and caps.mode.code not in self.data:
            values = caps.mode.enum_values
            self.data[caps.mode.code] = (
                "auto" if "auto" in values else values[0] if values else "auto"
            )
        if caps.fan and caps.fan.code not in self.data:
            values = caps.fan.enum_values
            self.data[caps.fan.code] = (
                "auto" if "auto" in values else values[0] if values else "auto"
            )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            remote = await self.api.get_status(self.device_id)
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            # A temporary status endpoint problem should not erase a working
            # optimistic state. Report it, but keep the entity usable.
            _LOGGER.warning(
                "Tuya status refresh failed for ...%s: %s",
                self.device_id[-6:],
                err,
            )
            return dict(self.data)

        merged = dict(self.data)
        merged.update(remote)
        return merged

    async def async_send(self, code: str, value: Any) -> None:
        """Send one command with optimistic state retention."""
        try:
            route = await self.api.send_command(
                self.device_id,
                code,
                value,
            )
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            raise UpdateFailed(str(err)) from err

        self.last_command_route = route
        optimistic = dict(self.data)
        optimistic[code] = value
        self.async_set_updated_data(optimistic)
        await self.async_request_refresh()

    async def async_send_many(
        self,
        commands: list[dict[str, Any]],
    ) -> None:
        """Send multiple commands atomically where Tuya supports it."""
        try:
            route = await self.api.send_commands(
                self.device_id,
                commands,
            )
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            raise UpdateFailed(str(err)) from err

        self.last_command_route = route
        optimistic = dict(self.data)
        for command in commands:
            if command.get("code"):
                optimistic[str(command["code"])] = command.get("value")
        self.async_set_updated_data(optimistic)
        await self.async_request_refresh()
