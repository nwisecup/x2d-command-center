"""Base entity."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import X2DCoordinator
from .models import PrinterState


class X2DEntity(CoordinatorEntity[X2DCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coord: X2DCoordinator, key: str, *, always_available: bool = False) -> None:
        super().__init__(coord)
        self.key = key
        self._always = always_available
        self._attr_unique_id = f"{coord.serial}_{key}"
        self._attr_device_info = coord.device_info

    @property
    def available(self) -> bool:
        if self._always:
            return True
        return self.coordinator.connected and self.coordinator.data is not None

    @property
    def s(self) -> PrinterState:
        return self.coordinator.state
