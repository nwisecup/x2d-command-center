"""Chamber heater as a thermostat (M141)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


class ChamberClimate(X2DEntity, ClimateEntity):
    _attr_name = "Chamber"
    _attr_icon = "mdi:home-thermometer"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON
                                | ClimateEntityFeature.TURN_OFF)
    _attr_min_temp = 20
    _attr_max_temp = 65
    _attr_target_temperature_step = 1

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "chamber_climate")
        self._last_target = 45.0

    @property
    def current_temperature(self) -> float | None:
        return self.s.chamber_temp

    @property
    def target_temperature(self) -> float | None:
        t = self.s.chamber_target
        return t if t else None

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if (self.s.chamber_target or 0) > 0 else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        tgt, cur = self.s.chamber_target or 0, self.s.chamber_temp or 0
        if tgt <= 0:
            return HVACAction.OFF
        return HVACAction.HEATING if cur < tgt - 0.5 else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._last_target = float(t)
            await self.coordinator.async_chamber_temp(t)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_chamber_temp(self._last_target if hvac_mode == HVACMode.HEAT else 0)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    add([ChamberClimate(entry.runtime_data)])
