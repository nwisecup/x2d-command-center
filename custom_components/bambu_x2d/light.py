"""Lights — one per node the printer reports in lights_report."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_EFFECT, ColorMode, LightEntity, LightEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity

FLASHING = "flashing"


class X2DLight(X2DEntity, LightEntity):
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = [FLASHING]

    def __init__(self, coord: C, node: str) -> None:
        super().__init__(coord, f"light_{node}")
        self.node = node
        self._attr_name = node.replace("_", " ").capitalize()
        self._attr_icon = "mdi:lightbulb"

    @property
    def is_on(self) -> bool | None:
        mode = self.s.lights.get(self.node)
        return None if mode is None else mode in ("on", FLASHING)

    @property
    def effect(self) -> str | None:
        return FLASHING if self.s.lights.get(self.node) == FLASHING else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_light(self.node, True, flashing=kwargs.get(ATTR_EFFECT) == FLASHING)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_light(self.node, False)


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    known: set[str] = set()

    @callback
    def _sync() -> None:
        nodes = set(coord.state.lights) or {"chamber_light"}
        new = nodes - known
        if new:
            known.update(new)
            add(X2DLight(coord, n) for n in sorted(new))

    _sync()
    entry.async_on_unload(coord.async_add_listener(_sync))
