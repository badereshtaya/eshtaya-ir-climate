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
    )


class EshtayaIRClimate(EshtayaIrClimateEntity, ClimateEntity):
    """Tuya IR A/C climate entity."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.1

    def __init__(self, coordinator: EshtayaIrClimateCoordinator) -> None:
        super().__init__(coordinator, "climate")
        caps = coordinator.capabilities

        features = ClimateEntityFeature(0)
        if caps.target_temp:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if caps.fan:
            features |= ClimateEntityFeature.FAN_MODE
        if caps.power:
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
        return {
            "eshtaya_ir_climate": True,
            "tuya_device_id": self.coordinator.device_id,
            "capability_profile": self.coordinator.capabilities.profile,
            "capability_confidence": self.coordinator.capabilities.confidence,
            "last_command_route": self.coordinator.last_command_route,
        }

    @property
    def hvac_modes(self) -> list[HVACMode]:
        result: list[HVACMode] = [HVACMode.OFF]
        dp = self.coordinator.capabilities.mode
        if dp:
            for raw in dp.enum_values:
                mapped = TUYA_TO_HVAC.get(raw.lower())
                if mapped:
                    mode = HVACMode(mapped)
                    if mode not in result:
                        result.append(mode)
        if len(result) == 1:
            result.extend(
                [
                    HVACMode.COOL,
                    HVACMode.HEAT,
                    HVACMode.AUTO,
                    HVACMode.FAN_ONLY,
                    HVACMode.DRY,
                ]
            )
        return result

    @property
    def hvac_mode(self) -> HVACMode:
        caps = self.coordinator.capabilities
        data = self.coordinator.data

        if caps.power and not bool(data.get(caps.power.code, False)):
            return HVACMode.OFF

        if caps.mode:
            raw = data.get(caps.mode.code)
            mapped = TUYA_TO_HVAC.get(str(raw).lower()) if raw is not None else None
            if mapped:
                return HVACMode(mapped)
        return HVACMode.AUTO

    @property
    def current_temperature(self) -> float | None:
        dp = self.coordinator.capabilities.current_temp
        return (
            dp.decode_number(self.coordinator.data.get(dp.code))
            if dp else None
        )

    @property
    def current_humidity(self) -> float | None:
        dp = self.coordinator.capabilities.humidity
        return (
            dp.decode_number(self.coordinator.data.get(dp.code))
            if dp else None
        )

    @property
    def target_temperature(self) -> float | None:
        dp = self.coordinator.capabilities.target_temp
        return (
            dp.decode_number(self.coordinator.data.get(dp.code))
            if dp else None
        )

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
        return modes or ["auto", "low", "medium", "high"]

    @property
    def fan_mode(self) -> str | None:
        dp = self.coordinator.capabilities.fan
        if not dp:
            return None
        raw = self.coordinator.data.get(dp.code)
        if raw is None:
            return "auto"
        return FAN_VALUE_NORMALIZATION.get(str(raw).lower(), str(raw))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        caps = self.coordinator.capabilities

        if hvac_mode == HVACMode.OFF:
            if caps.power:
                await self.coordinator.async_send(
                    caps.power.code,
                    False,
                )
            return

        commands: list[dict[str, Any]] = []
        if caps.power:
            commands.append(
                {"code": caps.power.code, "value": True}
            )

        if caps.mode:
            raw_mode = _pick_preferred(
                caps.mode.enum_values,
                HVAC_TO_TUYA_PREFERENCE.get(
                    hvac_mode.value,
                    (hvac_mode.value,),
                ),
            )
            if raw_mode is None:
                # Known profile fallback.
                raw_mode = {
                    "cool": "cold",
                    "heat": "warm",
                    "auto": "auto",
                    "fan_only": "air",
                    "dry": "dehumidify",
                }.get(hvac_mode.value)
            if raw_mode:
                commands.append(
                    {"code": caps.mode.code, "value": raw_mode}
                )

        if commands:
            await self.coordinator.async_send_many(commands)

    async def async_turn_on(self) -> None:
        caps = self.coordinator.capabilities
        if caps.power:
            await self.coordinator.async_send(caps.power.code, True)

    async def async_turn_off(self) -> None:
        caps = self.coordinator.capabilities
        if caps.power:
            await self.coordinator.async_send(caps.power.code, False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        value = kwargs.get(ATTR_TEMPERATURE)
        dp = self.coordinator.capabilities.target_temp
        if value is None or not dp:
            return
        await self.coordinator.async_send(
            dp.code,
            dp.encode_number(float(value)),
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        dp = self.coordinator.capabilities.fan
        if not dp:
            return

        raw = _pick_preferred(
            dp.enum_values,
            FAN_TO_TUYA_PREFERENCE.get(fan_mode, (fan_mode,)),
        )
        if raw is None:
            raw = {
                "auto": "auto",
                "low": "low",
                "medium": "middle",
                "high": "high",
            }.get(fan_mode, fan_mode)

        await self.coordinator.async_send(dp.code, raw)
