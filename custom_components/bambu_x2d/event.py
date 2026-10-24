"""Event entity — trigger automations on print lifecycle, HMS, soak and timelapse events."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .const import EVENT_TYPES
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


class PrinterEvents(X2DEntity, EventEntity):
    _attr_name = "Printer event"
    _attr_icon = "mdi:bell-ring"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "events", always_available=True)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.add_event_listener(self._on_event))

    @callback
    def _on_event(self, kind: str, data: dict) -> None:
        if kind in EVENT_TYPES:
            self._trigger_event(kind, {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool, type(None)))})
            self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    add([PrinterEvents(entry.runtime_data)])
