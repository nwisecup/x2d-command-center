"""Cover image of the current job (plate thumbnail from the sliced .3mf)."""
from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C


class CoverImage(CoordinatorEntity[C], ImageEntity):
    _attr_has_entity_name = True
    _attr_name = "Job preview"
    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, coord: C) -> None:
        CoordinatorEntity.__init__(self, coord)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{coord.serial}_cover"
        self._attr_device_info = coord.device_info
        self._attr_image_last_updated = coord.cover_updated

    @property
    def available(self) -> bool:
        return self.coordinator.cover is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.cover_updated != self._attr_image_last_updated:
            self._attr_image_last_updated = self.coordinator.cover_updated
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        return self.coordinator.cover


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    add([CoverImage(hass, entry.runtime_data)])
