"""Switches: printer AI detectors, print options, camera, and integration behaviour."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .const import PRINT_OPTIONS, XCAM_MODULES
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity

CFG = EntityCategory.CONFIG


@dataclass(frozen=True, kw_only=True)
class X2DSwitchDescription(SwitchEntityDescription):
    value_fn: Callable[[C], bool | None]
    set_fn: Callable[[C, bool], Awaitable[Any]]
    assumed: bool = False           # printer doesn't report this one back
    local: bool = False             # integration setting, works while printer offline


def _xcam(module: str, label: str) -> X2DSwitchDescription:
    def val(c: C) -> bool | None:
        v = c.state.xcam.get(module)
        return None if v is None else bool(v)

    return X2DSwitchDescription(
        key=f"xcam_{module}", name=label, icon="mdi:eye-check", entity_category=CFG, value_fn=val,
        set_fn=lambda c, on, m=module: c.async_xcam(m, on, halt=True,
                                                    sensitivity=c.state.xcam.get("halt_print_sensitivity")),
    )


def _option(key: str, label: str) -> X2DSwitchDescription:
    reported = key in ("auto_recovery", "sound_enable", "filament_tangle_detect")
    return X2DSwitchDescription(
        key=f"option_{key}", name=label, icon="mdi:tune", entity_category=CFG, assumed=not reported,
        value_fn=(lambda c, k=key: c.state.flags.get(k)) if reported else (lambda c: None),
        set_fn=lambda c, on, k=key: c.async_print_option(k, on),
    )


def _setting(key: str, label: str, icon: str, cat: EntityCategory | None = CFG, default: bool = False) -> X2DSwitchDescription:
    async def setter(c: C, on: bool) -> None:
        await c.async_set_setting(key, on)

    return X2DSwitchDescription(key=key, name=label, icon=icon, entity_category=cat, local=True,
                                value_fn=lambda c: bool(c.settings.get(key, default)), set_fn=setter)


async def _ha_tl(c: C, on: bool) -> None:
    await c.async_set_setting("ha_timelapse", on)


SWITCHES: list[X2DSwitchDescription] = [
    *[_xcam(m, label) for m, label in XCAM_MODULES.items()],
    *[_option(k, label) for k, label in PRINT_OPTIONS.items()],
    X2DSwitchDescription(key="camera_recording", name="Printer camera recording", icon="mdi:record-rec",
                         entity_category=CFG,
                         value_fn=lambda c: (c.state.ipcam.get("ipcam_record") == "enable") if c.state.ipcam else None,
                         set_fn=lambda c, on: c.async_camera_record(on)),
    X2DSwitchDescription(key="printer_timelapse", name="Printer-side timelapse", icon="mdi:movie-open-outline",
                         entity_category=CFG,
                         value_fn=lambda c: (c.state.ipcam.get("timelapse") == "enable") if c.state.ipcam else None,
                         set_fn=lambda c, on: c.async_camera_timelapse(on)),
    X2DSwitchDescription(key="ha_timelapse", name="Timelapse capture", icon="mdi:movie-open", local=True,
                         value_fn=lambda c: c.ha_timelapse, set_fn=_ha_tl),
    _setting("notifications", "Notifications", "mdi:bell", None, True),
    _setting("queue_auto", "Queue: auto-continue (90 s grace)", "mdi:tray-full"),
    _setting("advisor", "Filament advisor", "mdi:lightbulb-on", default=True),
    _setting("soak_autostart", "Soak: auto-start print", "mdi:play-circle"),
    _setting("soak_cold_scaling", "Soak: longer when cold", "mdi:snowflake-thermometer", default=True),
    _setting("soak_use_heater", "Soak: use ambient heater", "mdi:heat-wave"),
    _setting("soak_armed", "Soak: ready-by armed", "mdi:alarm", None),
    _setting("print_use_ams", "Print option: use AMS", "mdi:tray-full", default=True),
    _setting("print_bed_level", "Print option: bed levelling", "mdi:ruler-square", default=True),
    _setting("print_layer_inspect", "Print option: first-layer inspection", "mdi:layers-search", default=True),
    _setting("print_timelapse", "Print option: printer timelapse", "mdi:movie-outline"),
    _setting("print_flow_cali", "Print option: flow calibration", "mdi:waves"),
    _setting("print_vibration", "Print option: vibration calibration", "mdi:vibrate"),
]


class X2DSwitch(X2DEntity, SwitchEntity):
    entity_description: X2DSwitchDescription

    def __init__(self, coord: C, desc: X2DSwitchDescription) -> None:
        super().__init__(coord, desc.key, always_available=desc.local)
        self.entity_description = desc
        self._attr_assumed_state = desc.assumed
        self._optimistic: bool | None = None

    @property
    def is_on(self) -> bool | None:
        v = self.entity_description.value_fn(self.coordinator)
        return self._optimistic if v is None else v

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator, True)
        self._optimistic = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator, False)
        self._optimistic = False
        self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    add(X2DSwitch(coord, d) for d in SWITCHES)
