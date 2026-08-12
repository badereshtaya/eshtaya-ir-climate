"""Sensor platform for Eshtaya IR Climate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import EshtayaIrClimateCoordinator
from .entity import EshtayaIrClimateEntity
from .model import DpMeta
from .runtime import EshtayaAccountRuntime


@dataclass(frozen=True, kw_only=True)
class EshtayaSensorDescription(SensorEntityDescription):
    """Sensor entity description."""

    value_fn: Callable[[DpMeta, Any], Any]


def _number(dp: DpMeta, value: Any) -> Any:
    return dp.decode_number(value)


def _raw(dp: DpMeta, value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return str(value)
    return value


SENSOR_SPECS = (
    (
        "current_temp",
        "Current temperature",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        _number,
    ),
    (
        "humidity",
        "Humidity",
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE,
        _number,
    ),
    (
        "filter_life",
        "Filter life",
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        _number,
    ),
    (
        "runtime",
        "Runtime",
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        _number,
    ),
    (
        "status",
        "Status",
        None,
        None,
        _raw,
    ),
    (
        "fault",
        "Fault",
        None,
        None,
        _raw,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: EshtayaAccountRuntime = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for coordinator in runtime.coordinators.values():
        caps = coordinator.capabilities
        for attr, name, device_class, unit, value_fn in SENSOR_SPECS:
            dp = getattr(caps, attr)
            if dp is None or not dp.readable:
                continue
            desc = EshtayaSensorDescription(
                key=attr,
                name=name,
                device_class=device_class,
                native_unit_of_measurement=unit,
                value_fn=value_fn,
            )
            entities.append(
                EshtayaIRSensor(coordinator, dp, desc)
            )

        entities.append(EshtayaIRLearnedCommandsSensor(coordinator))

    async_add_entities(entities)


class EshtayaIRLearnedCommandsSensor(EshtayaIrClimateEntity, SensorEntity):
    """Number of exact IR commands automatically learned from Tuya logs."""

    _attr_name = "Learned IR commands"
    _attr_icon = "mdi:remote"

    def __init__(self, coordinator: EshtayaIrClimateCoordinator) -> None:
        super().__init__(coordinator, "learned_ir_commands")

    @property
    def native_value(self) -> int:
        return self.coordinator.ir_library.count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        library = self.coordinator.ir_library
        return {
            "last_learned_key": library.last_learned_key,
            "last_missing_request": library.last_missing_request,
        }


class EshtayaIRSensor(EshtayaIrClimateEntity, SensorEntity):
    """One read-only Tuya datapoint sensor."""

    entity_description: EshtayaSensorDescription

    def __init__(
        self,
        coordinator: EshtayaIrClimateCoordinator,
        dp: DpMeta,
        description: EshtayaSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.dp = dp
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(
            self.dp,
            self.coordinator.data.get(self.dp.code),
        )
