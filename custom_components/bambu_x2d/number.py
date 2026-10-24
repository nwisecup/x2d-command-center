"""Numbers: heater targets and heat-soak setpoints."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


@dataclass(frozen=True, kw_only=True)
class X2DNumberDescription(NumberEntityDescription):
    value_fn: Callable[[C], float | None]
    set_fn: Callable[[C, float], Awaitable[None]]
    local: bool = False


def _target(desc_key: str, name: str, icon: str, maxv: float, value_fn, set_fn) -> X2DNumberDescription:
    return X2DNumberDescription(
        key=desc_key, name=name, icon=icon, native_min_value=0, native_max_value=maxv, native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX, value_fn=value_fn, set_fn=set_fn,
    )


def _setting(key: str, name: str, icon: str, lo: float, hi: float, step: float, unit: str) -> X2DNumberDescription:
    async def setter(c: C, v: float) -> None:
        await c.async_set_setting(key, v)

    return X2DNumberDescription(
        key=key, name=name, icon=icon, native_min_value=lo, native_max_value=hi, native_step=step,
        native_unit_of_measurement=unit, mode=NumberMode.BOX, entity_category=EntityCategory.CONFIG,
        local=True, value_fn=lambda c: c.settings.get(key), set_fn=setter,
    )


NUMBERS: list[X2DNumberDescription] = [
    _target("nozzle_target_set", "Nozzle target", "mdi:printer-3d-nozzle-heat", 320,
            lambda c: c.state.nozzle.target if c.state.nozzle else None, lambda c, v: c.async_nozzle_temp(v)),
    _target("bed_target_set", "Bed target", "mdi:radiator", 120,
            lambda c: c.state.bed_target, lambda c, v: c.async_bed_temp(v)),
    _target("chamber_target_set", "Chamber target", "mdi:home-thermometer", 65,
            lambda c: c.state.chamber_target, lambda c, v: c.async_chamber_temp(v)),
    _setting("soak_chamber", "Soak chamber target", "mdi:home-thermometer", 0, 65, 1, UnitOfTemperature.CELSIUS),
    _setting("soak_bed", "Soak bed target", "mdi:radiator", 0, 120, 5, UnitOfTemperature.CELSIUS),
    _setting("soak_hold", "Soak hold (base)", "mdi:timer-sand", 0, 120, 1, UnitOfTime.MINUTES),
]


def _nozzle_n(nid: int) -> X2DNumberDescription:
    def val(c: C):
        n = next((x for x in c.state.nozzles if x.id == nid), None)
        return n.target if n else None
    return _target(f"nozzle{nid + 1}_target_set", f"Nozzle {nid + 1} target", "mdi:printer-3d-nozzle-heat", 320,
                   val, lambda c, v, i=nid: c.async_nozzle_temp(v, i))


class X2DNumber(X2DEntity, NumberEntity):
    entity_description: X2DNumberDescription

    def __init__(self, coord: C, desc: X2DNumberDescription) -> None:
        super().__init__(coord, desc.key, always_available=desc.local)
        self.entity_description = desc

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.coordinator, value)
        self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    descs = list(NUMBERS)
    if coord.state.is_dual:
        descs += [_nozzle_n(n.id) for n in coord.state.nozzles]
    add(X2DNumber(coord, d) for d in descs)
