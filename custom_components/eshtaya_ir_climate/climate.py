"""Climate platform for Eshtaya IR Climate."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    FAN_TO_TUYA_PREFERENCE,
    FAN_VALUE_NORMALIZATION,
    HVAC_TO_TUYA_PREFERENCE,
    TUYA_TO_HVAC,
)
from .coordinator import EshtayaIrClimateCoordinator
from .entity import EshtayaIrClimateEntity
from .runtime import EshtayaAccountRuntime


def _pick_preferred(
    available: list[str],
    preferences: tuple[str, ...],
) -> str | None:
    available_lower = {value.lower(): value for value in available}
    for preferred in preferences:
        if preferred in available_lower:
            return available_lower[preferred]
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: EshtayaAccountRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EshtayaIRClimate(coordinator)
        for coordinator in runtime.coordinators.values()
        if coordinator.capabilities.climate_compatible
    )


class EshtayaIRClimate(EshtayaIrClimateEntity, ClimateEntity):
    """Tuya-backed IR air-conditioner climate entity."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.1

    def __init__(self, coordinator: EshtayaIrClimateCoordinator) -> None:
        super().__init__(coordinator, "climate")
        caps = coordinator.capabilities

        features = ClimateEntityFeature(0)
        if caps.target_temp and caps.target_temp.writable:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if caps.fan and caps.fan.writable:
            features |= ClimateEntityFeature.FAN_MODE
        if caps.power and caps.power.writable:
            features |= (
                ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
            )
        self._attr_supported_features = features

        if caps.target_temp:
            self._attr_min_temp = caps.target_temp.minimum or 16
            self._attr_max_temp = caps.target_temp.maximum or 30
            self._attr_target_temperature_step = caps.target_temp.step or 1

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Mark the entity for the bundled dashboard card."""
        return {
            "eshtaya_ir_climate": True,
            "tuya_device_id": self.coordinator.device_id,
        }

    @property
    def hvac_modes(self) -> list[HVACMode]:
        result: list[HVACMode] = [HVACMode.OFF]
        mode_dp = self.coordinator.capabilities.mode
        if mode_dp:
            for raw in mode_dp.enum_values:
                mapped = TUYA_TO_HVAC.get(raw.lower())
                if mapped is None:
                    continue
                hvac = HVACMode(mapped)
                if hvac not in result:
                    result.append(hvac)
        if len(result) == 1:
            result.append(HVACMode.COOL)
        return result

    @property
    def hvac_mode(self) -> HVACMode:
        caps = self.coordinator.capabilities
        data = self.coordinator.data

        if caps.power and not bool(data.get(caps.power.code, False)):
            return HVACMode.OFF

        if caps.mode:
            raw = data.get(caps.mode.code)
            if raw is not None:
                mapped = TUYA_TO_HVAC.get(str(raw).lower())
                if mapped:
                    return HVACMode(mapped)

        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        dp = self.coordinator.capabilities.current_temp
        if not dp:
            return None
        return dp.decode_number(self.coordinator.data.get(dp.code))

    @property
    def current_humidity(self) -> float | None:
        dp = self.coordinator.capabilities.humidity
        if not dp:
            return None
        return dp.decode_number(self.coordinator.data.get(dp.code))

    @property
    def target_temperature(self) -> float | None:
        dp = self.coordinator.capabilities.target_temp
        if not dp:
            return None
        return dp.decode_number(self.coordinator.data.get(dp.code))

    @property
    def fan_modes(self) -> list[str] | None:
        dp = self.coordinator.capabilities.fan
        if not dp:
            return None
        modes: list[str] = []
        for raw in dp.enum_values:
            normalized = FAN_VALUE_NORMALIZATION.get(raw.lower(), raw)
            if normalized not in modes:
                modes.append(normalized)
        return modes or None

    @property
    def fan_mode(self) -> str | None:
        dp = self.coordinator.capabilities.fan
        if not dp:
            return None
        raw = self.coordinator.data.get(dp.code)
        if raw is None:
            return None
        return FAN_VALUE_NORMALIZATION.get(str(raw).lower(), str(raw))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        caps = self.coordinator.capabilities

        if hvac_mode == HVACMode.OFF:
            if caps.power and caps.power.writable:
                await self.coordinator.async_send(caps.power.code, False)
            return

        commands: list[dict[str, Any]] = []
        if caps.power and caps.power.writable:
            commands.append({"code": caps.power.code, "value": True})

        if caps.mode and caps.mode.writable:
            raw_mode = _pick_preferred(
                caps.mode.enum_values,
                HVAC_TO_TUYA_PREFERENCE.get(
                    hvac_mode.value,
                    (hvac_mode.value,),
                ),
            )
            if raw_mode is not None:
                commands.append(
                    {"code": caps.mode.code, "value": raw_mode}
                )

        if commands:
            await self.coordinator.api.send_commands(
                self.coordinator.device_id,
                commands,
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        caps = self.coordinator.capabilities
        if caps.power and caps.power.writable:
            await self.coordinator.async_send(caps.power.code, True)

    async def async_turn_off(self) -> None:
        caps = self.coordinator.capabilities
        if caps.power and caps.power.writable:
            await self.coordinator.async_send(caps.power.code, False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        value = kwargs.get(ATTR_TEMPERATURE)
        dp = self.coordinator.capabilities.target_temp
        if value is None or not dp or not dp.writable:
            return
        await self.coordinator.async_send(
            dp.code,
            dp.encode_number(float(value)),
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        dp = self.coordinator.capabilities.fan
        if not dp or not dp.writable:
            return

        raw = _pick_preferred(
            dp.enum_values,
            FAN_TO_TUYA_PREFERENCE.get(fan_mode, (fan_mode,)),
        )
        if raw is None and fan_mode in dp.enum_values:
            raw = fan_mode

        if raw is not None:
            await self.coordinator.async_send(dp.code, raw)
