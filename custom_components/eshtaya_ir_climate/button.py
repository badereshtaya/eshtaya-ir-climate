"""Button platform for Eshtaya IR Climate."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
        if (
            coordinator.capabilities.filter_reset
            and coordinator.capabilities.filter_reset.writable
        ):
            entities.append(
                EshtayaIRResetButton(
                    coordinator,
                    coordinator.capabilities.filter_reset,
                    "Reset filter life",
                    "filter_reset",
                )
            )
        if (
            coordinator.capabilities.runtime_reset
            and coordinator.capabilities.runtime_reset.writable
        ):
            entities.append(
                EshtayaIRResetButton(
                    coordinator,
                    coordinator.capabilities.runtime_reset,
                    "Reset runtime",
                    "runtime_reset",
                )
            )

        entities.append(EshtayaIRSyncLibraryButton(coordinator))

    async_add_entities(entities)


class EshtayaIRSyncLibraryButton(EshtayaIrClimateEntity, ButtonEntity):
    """Force a 24-hour import of recent Smart Life IR commands."""

    _attr_name = "Sync IR library"
    _attr_icon = "mdi:remote-tv"

    def __init__(self, coordinator: EshtayaIrClimateCoordinator) -> None:
        super().__init__(coordinator, "sync_ir_library")

    async def async_press(self) -> None:
        await self.coordinator.async_sync_ir_library()


class EshtayaIRResetButton(EshtayaIrClimateEntity, ButtonEntity):
    """Momentary reset datapoint button."""

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

    async def async_press(self) -> None:
        await self.coordinator.async_send(self.dp.code, True)
