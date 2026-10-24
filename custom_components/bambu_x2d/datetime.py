"""'Soak ready by' — set a time and the soak starts early enough to be done by then."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


class SoakReadyBy(X2DEntity, DateTimeEntity):
    _attr_name = "Soak ready by"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "soak_ready_by", always_available=True)

    @property
    def native_value(self) -> datetime | None:
        v = self.coordinator.settings.get("soak_ready_by")
        return dt_util.parse_datetime(v) if v else None

    async def async_set_value(self, value: datetime) -> None:
        await self.coordinator.async_set_setting("soak_ready_by", dt_util.as_utc(value).isoformat())


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    add([SoakReadyBy(entry.runtime_data)])
