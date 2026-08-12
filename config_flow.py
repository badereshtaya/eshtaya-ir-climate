"""Config flow for Eshtaya IR Climate."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api import TuyaApiError, TuyaAuthError, TuyaOpenApi
from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_DATA_CENTER,
    CONF_DEVICE_IDS,
    CONF_MANUAL_DEVICE_ID,
    DATA_CENTER_LABELS,
    DATA_CENTERS,
    DISCOVERY_CONCURRENCY,
    DOMAIN,
    MAX_DISCOVERY_DEVICES,
)
from .model import DeviceCapabilities


async def _make_api(hass: HomeAssistant, data: dict[str, Any]) -> TuyaOpenApi:
    session = async_get_clientsession(hass)
    api = TuyaOpenApi(
        session,
        DATA_CENTERS[data[CONF_DATA_CENTER]],
        str(data[CONF_ACCESS_ID]).strip(),
        str(data[CONF_ACCESS_SECRET]).strip(),
    )
    await api.ensure_token()
    return api


async def _discover_compatible(
    api: TuyaOpenApi,
) -> list[dict[str, Any]]:
    devices = await api.list_devices(MAX_DISCOVERY_DEVICES)
    semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)

    async def inspect(device: dict[str, Any]) -> dict[str, Any] | None:
        device_id = str(device.get("id") or device.get("device_id") or "").strip()
        if not device_id:
            return None

        async with semaphore:
            try:
                spec = await api.get_specification(device_id)
            except TuyaApiError:
                return None

        caps = DeviceCapabilities.from_specification(spec)
        if not caps.climate_compatible:
            return None

        result = dict(device)
        result["id"] = device_id
        return result

    inspected = await asyncio.gather(*(inspect(d) for d in devices))
    return [d for d in inspected if d is not None]


async def _validate_manual_device(
    api: TuyaOpenApi,
    device_id: str,
) -> dict[str, Any]:
    device = await api.get_device(device_id)
    spec = await api.get_specification(device_id)
    caps = DeviceCapabilities.from_specification(spec)
    if not caps.climate_compatible:
        raise ValueError("not_supported")
    return device


class EshtayaIrClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Eshtaya IR Climate setup."""

    VERSION = 2
    MINOR_VERSION = 0

    def __init__(self) -> None:
        self._credentials: dict[str, Any] = {}
        self._api: TuyaOpenApi | None = None
        self._compatible_devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input=None):
        """Collect Tuya cloud project credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned = dict(user_input)
            cleaned[CONF_ACCESS_ID] = str(cleaned[CONF_ACCESS_ID]).strip()
            cleaned[CONF_ACCESS_SECRET] = str(cleaned[CONF_ACCESS_SECRET]).strip()

            try:
                api = await _make_api(self.hass, cleaned)
            except TuyaAuthError:
                errors["base"] = "invalid_auth"
            except TuyaApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                self._credentials = cleaned
                self._api = api

                unique = (
                    f"{cleaned[CONF_DATA_CENTER]}:"
                    f"{cleaned[CONF_ACCESS_ID].lower()}"
                )
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                try:
                    self._compatible_devices = await _discover_compatible(api)
                except TuyaAuthError:
                    errors["base"] = "invalid_auth"
                except TuyaApiError:
                    # Credentials are valid but listing may not be authorized.
                    return await self.async_step_manual()
                else:
                    if self._compatible_devices:
                        return await self.async_step_devices()
                    return await self.async_step_manual()

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_ID): str,
                vol.Required(CONF_ACCESS_SECRET): str,
                vol.Required(
                    CONF_DATA_CENTER,
                    default="central_europe",
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=value, label=label)
                            for value, label in DATA_CENTER_LABELS.items()
                        ]
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_devices(self, user_input=None):
        """Select one or more compatible IR climate devices."""
        errors: dict[str, str] = {}

        options: list[SelectOptionDict] = []
        valid_ids: set[str] = set()
        for device in self._compatible_devices:
            device_id = str(device["id"])
            valid_ids.add(device_id)
            name = str(
                device.get("name")
                or device.get("product_name")
                or device_id
            )
            category = str(device.get("category") or "IR climate")
            online = "online" if device.get("online") else "offline"
            options.append(
                SelectOptionDict(
                    value=device_id,
                    label=f"{name} · {category} · {online}",
                )
            )

        if user_input is not None:
            selected = [
                str(value)
                for value in user_input.get(CONF_DEVICE_IDS, [])
                if str(value) in valid_ids
            ]
            if not selected:
                errors["base"] = "select_device"
            else:
                data = {
                    **self._credentials,
                    CONF_DEVICE_IDS: selected,
                }
                return self.async_create_entry(
                    title="Eshtaya IR Climate",
                    data=data,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="devices",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_manual(self, user_input=None):
        """Fallback when Tuya does not permit account device discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = str(user_input[CONF_MANUAL_DEVICE_ID]).strip()
            try:
                assert self._api is not None
                await _validate_manual_device(self._api, device_id)
            except TuyaAuthError:
                errors["base"] = "invalid_auth"
            except ValueError:
                errors["base"] = "not_supported"
            except TuyaApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                data = {
                    **self._credentials,
                    CONF_DEVICE_IDS: [device_id],
                }
                return self.async_create_entry(
                    title="Eshtaya IR Climate",
                    data=data,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MANUAL_DEVICE_ID): str,
            }
        )
        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
        )
