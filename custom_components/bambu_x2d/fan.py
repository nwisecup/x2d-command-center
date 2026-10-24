"""Fans: part cooling, aux, chamber/exhaust (M106 P1/P2/P3)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity

FANS = {"part": ("Part cooling fan", "mdi:fan"), "aux": ("Aux fan", "mdi:fan-auto"),
        "chamber": ("Chamber fan", "mdi:air-filter")}


class X2DFan(X2DEntity, FanEntity):
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_speed_count = 10

    def __init__(self, coord: C, fan: str) -> None:
        super().__init__(coord, f"fan_{fan}")
        self.fan = fan
        self._attr_name, self._attr_icon = FANS[fan]

    @property
    def percentage(self) -> int | None:
        return self.s.fans.get(self.fan)

    @property
    def is_on(self) -> bool | None:
        p = self.percentage
        return None if p is None else p > 0

    async def async_set_percentage(self, percentage: int) -> None:
        await self.coordinator.async_fan(self.fan, percentage)

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        await self.coordinator.async_fan(self.fan, percentage if percentage is not None else 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_fan(self.fan, 0)


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    add(X2DFan(coord, f) for f in FANS)
