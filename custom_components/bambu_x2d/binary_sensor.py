"""Binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass as D,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .const import OPT_AMBIENT_HUM, OPT_AMBIENT_TEMP
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


@dataclass(frozen=True, kw_only=True)
class X2DBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[C], bool | None]
    attrs_fn: Callable[[C], dict[str, Any]] | None = None
    exists_fn: Callable[[C], bool] = lambda c: True
    always_available: bool = False


BINARIES: tuple[X2DBinaryDescription, ...] = (
    X2DBinaryDescription(key="online", name="Online", device_class=D.CONNECTIVITY, always_available=True,
                         entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda c: c.connected),
    X2DBinaryDescription(key="cloud_link", name="Cloud link", device_class=D.CONNECTIVITY, always_available=True,
                         entity_category=EntityCategory.DIAGNOSTIC,
                         exists_fn=lambda c: bool(c.cloud_cfg.get("token")),
                         value_fn=lambda c: c.cloud_connected),
    X2DBinaryDescription(key="maintenance_due", name="Maintenance due", device_class=D.PROBLEM,
                         always_available=True,
                         value_fn=lambda c: any(m["due"] for m in c.maintenance_status)),
    X2DBinaryDescription(key="printing", name="Printing", device_class=D.RUNNING, value_fn=lambda c: c.state.is_printing),
    X2DBinaryDescription(key="paused", name="Paused", icon="mdi:pause-circle", value_fn=lambda c: c.state.gcode_state == "pause"),
    X2DBinaryDescription(key="error", name="Print error", device_class=D.PROBLEM,
                         value_fn=lambda c: c.state.gcode_state == "failed" and not c.state.is_cancelled or bool(c.state.print_error)),
    X2DBinaryDescription(key="hms_active", name="HMS alert", device_class=D.PROBLEM, value_fn=lambda c: bool(c.state.hms)),
    X2DBinaryDescription(key="door_open", name="Door", device_class=D.DOOR, value_fn=lambda c: c.state.door_open),
    X2DBinaryDescription(key="controls_verified", name="Controls verified", icon="mdi:shield-check",
                         entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda c: c.controls_ok,
                         attrs_fn=lambda c: {"hint": "Turns on after the printer accepts a command. Off means "
                                                     "Developer Mode is probably disabled.",
                                             **(c.last_command or {})}),
    X2DBinaryDescription(key="camera_available", name="Camera stream", device_class=D.CONNECTIVITY,
                         entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda c: c.camera_available),
    X2DBinaryDescription(key="running_behind", name="Running behind", icon="mdi:run-fast",
                         value_fn=lambda c: (c.eta_drift_min or 0) > 10),
    X2DBinaryDescription(key="ams_humid", name="AMS humid", device_class=D.MOISTURE,
                         value_fn=lambda c: any((a.humidity_index or 0) >= 4 for a in c.state.amss)),
    X2DBinaryDescription(key="filament_low", name="Filament low", device_class=D.PROBLEM, icon="mdi:spool",
                         value_fn=lambda c: any(t.present and t.remain is not None and t.remain < 10 for t in c.state.all_trays),
                         attrs_fn=lambda c: {"trays": [t.key for t in c.state.all_trays
                                                       if t.present and t.remain is not None and t.remain < 10]}),
    X2DBinaryDescription(key="timelapse_recording", name="Timelapse recording", icon="mdi:record-rec",
                         always_available=True, value_fn=lambda c: c.timelapse.job is not None),
    X2DBinaryDescription(key="soak_active", name="Heat soak active", device_class=D.HEAT, always_available=True,
                         value_fn=lambda c: c.soak.active),
    X2DBinaryDescription(key="too_cold", name="Too cold to start", device_class=D.COLD, always_available=True,
                         exists_fn=lambda c: bool(c.opts.get(OPT_AMBIENT_TEMP)), value_fn=lambda c: c.too_cold),
    X2DBinaryDescription(key="condensation_risk", name="Condensation risk", device_class=D.MOISTURE,
                         always_available=True,
                         exists_fn=lambda c: bool(c.opts.get(OPT_AMBIENT_TEMP) and c.opts.get(OPT_AMBIENT_HUM)),
                         value_fn=lambda c: c.condensation_risk),
)


class X2DBinary(X2DEntity, BinarySensorEntity):
    entity_description: X2DBinaryDescription

    def __init__(self, coord: C, desc: X2DBinaryDescription) -> None:
        super().__init__(coord, desc.key, always_available=desc.always_available)
        self.entity_description = desc

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator) if fn else None


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    add(X2DBinary(coord, d) for d in BINARIES if d.exists_fn(coord))
