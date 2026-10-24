"""Buttons."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .const import CAL_BED_LEVEL, CAL_MOTOR_NOISE, CAL_VIBRATION
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


@dataclass(frozen=True, kw_only=True)
class X2DButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[C], Awaitable[object]]
    local: bool = False


async def _load_selected(c: C) -> None:
    idx = c.settings.get("ams_selected")
    if idx is None or idx < 0:
        raise HomeAssistantError("Pick a filament slot first")
    await c.async_load_tray(int(idx))


async def _snapshot(c: C) -> None:
    if not await c.timelapse.snapshot("manual"):
        raise HomeAssistantError("Camera did not return a frame")


DIAG = EntityCategory.DIAGNOSTIC
BUTTONS: tuple[X2DButtonDescription, ...] = (
    X2DButtonDescription(key="pause", name="Pause", icon="mdi:pause", press_fn=lambda c: c.async_pause()),
    X2DButtonDescription(key="resume", name="Resume", icon="mdi:play", press_fn=lambda c: c.async_resume()),
    X2DButtonDescription(key="stop", name="Stop", icon="mdi:stop", press_fn=lambda c: c.async_stop()),
    X2DButtonDescription(key="refresh", name="Refresh status", icon="mdi:refresh", entity_category=DIAG,
                         press_fn=lambda c: c.async_pushall()),
    X2DButtonDescription(key="home", name="Home axes", icon="mdi:home", press_fn=lambda c: c.async_home()),
    X2DButtonDescription(key="motors_off", name="Disable motors", icon="mdi:engine-off", press_fn=lambda c: c.async_motors_off()),
    X2DButtonDescription(key="unload", name="Unload filament", icon="mdi:tray-arrow-up", press_fn=lambda c: c.async_unload()),
    X2DButtonDescription(key="load_selected", name="Load selected slot", icon="mdi:tray-arrow-down", press_fn=_load_selected),
    X2DButtonDescription(key="ams_resume", name="AMS resume", icon="mdi:play-pause", press_fn=lambda c: c.async_ams_control("resume")),
    X2DButtonDescription(key="soak_start", name="Start heat soak", icon="mdi:fire", press_fn=lambda c: c.async_soak_start()),
    X2DButtonDescription(key="soak_cancel", name="Cancel heat soak", icon="mdi:radiator-off", local=True,
                         press_fn=lambda c: c.async_soak_cancel()),
    X2DButtonDescription(key="print_selected", name="Print selected file", icon="mdi:printer-3d",
                         press_fn=lambda c: c.async_print_selected()),
    X2DButtonDescription(key="queue_next", name="Start next queued print", icon="mdi:skip-next",
                         press_fn=lambda c: c.async_queue_start_next()),
    X2DButtonDescription(key="snapshot", name="Snapshot", icon="mdi:camera", press_fn=_snapshot),
    X2DButtonDescription(key="cal_bed", name="Calibrate: bed levelling", icon="mdi:ruler-square", entity_category=DIAG,
                         press_fn=lambda c: c.async_calibrate(CAL_BED_LEVEL)),
    X2DButtonDescription(key="cal_vibration", name="Calibrate: vibration", icon="mdi:vibrate", entity_category=DIAG,
                         press_fn=lambda c: c.async_calibrate(CAL_VIBRATION)),
    X2DButtonDescription(key="cal_motor_noise", name="Calibrate: motor noise", icon="mdi:engine", entity_category=DIAG,
                         press_fn=lambda c: c.async_calibrate(CAL_MOTOR_NOISE)),
    X2DButtonDescription(key="cal_full", name="Calibrate: full", icon="mdi:tune-vertical", entity_category=DIAG,
                         press_fn=lambda c: c.async_calibrate(CAL_BED_LEVEL | CAL_VIBRATION | CAL_MOTOR_NOISE)),
    X2DButtonDescription(key="refresh_sd", name="Refresh printer storage", icon="mdi:sd", entity_category=DIAG,
                         press_fn=lambda c: c.async_refresh_sd()),
    X2DButtonDescription(key="pull_timelapses", name="Pull printer timelapses", icon="mdi:download",
                         press_fn=lambda c: c.timelapse.pull_from_printer()),
)


class X2DButton(X2DEntity, ButtonEntity):
    entity_description: X2DButtonDescription

    def __init__(self, coord: C, desc: X2DButtonDescription) -> None:
        super().__init__(coord, desc.key, always_available=desc.local)
        self.entity_description = desc

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    add(X2DButton(coord, d) for d in BUTTONS)
