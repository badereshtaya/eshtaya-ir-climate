"""Base entities for Eshtaya IR Climate."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EshtayaIrClimateCoordinator


class EshtayaIrClimateEntity(CoordinatorEntity[EshtayaIrClimateCoordinator]):
    """Base coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EshtayaIrClimateCoordinator,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        dev = self.coordinator.device
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            name=str(
                dev.get("name")
                or dev.get("product_name")
                or f"Tuya IR Climate {self.coordinator.device_id[-6:]}"
            ),
            manufacturer="Tuya",
            model=str(
                dev.get("product_name")
                or dev.get("model")
                or dev.get("category")
                or "IR Air Conditioner Controller"
            ),
            serial_number=self.coordinator.device_id,
        )
