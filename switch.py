"""Switch platform for Eshtaya IR Climate."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import EshtayaIrClimateCoordinator
from .entity import EshtayaIrClimateEntity
from .model import DpMeta
from .runtime import EshtayaAccountRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: EshtayaAccountRuntime = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in runtime.coordinators.values():
        dp = coordinator.capabilities.child_lock
        if dp and dp.writable:
            entities.append(
                EshtayaIRBooleanSwitch(
                    coordinator,
                    dp,
                    "Child lock",
                    "child_lock",
                )
            )
    async_add_entities(entities)


class EshtayaIRBooleanSwitch(EshtayaIrClimateEntity, SwitchEntity):
    """Boolean Tuya datapoint switch."""

    def __init__(
        self,
        coordinator: EshtayaIrClimateCoordinator,
        dp: DpMeta,
        name: str,
        key: str,
    ) -> None:
        super().__init__(coordinator, key)
        self.dp = dp
        self._attr_name = name

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get(self.dp.code, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send(self.dp.code, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send(self.dp.code, False)
