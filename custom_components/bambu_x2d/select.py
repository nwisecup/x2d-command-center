"""Selects: speed profile, AI sensitivity, soak preset, SD file, plate, AMS tray."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .const import HALT_SENSITIVITIES, MODE_CLOUD, MODE_HYBRID, MODE_LAN, SOAK_PRESETS, SPEED_BY_NAME, SPEED_LEVELS
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity

NONE = "—"


class ConnectionModeSelect(X2DEntity, SelectEntity):
    _attr_name = "Connection mode"
    _attr_icon = "mdi:lan-connect"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "connection_mode"

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "connection_mode", always_available=True)

    @property
    def options(self) -> list[str]:
        opts = []
        if self.coordinator.host:
            opts.append(MODE_LAN)
        if self.coordinator.cloud_cfg.get("token"):
            opts += ([MODE_HYBRID] if self.coordinator.host else []) + [MODE_CLOUD]
        return opts or [self.coordinator.mode]

    @property
    def current_option(self) -> str:
        return self.coordinator.mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode(option)


class SpeedSelect(X2DEntity, SelectEntity):
    _attr_name = "Speed profile"
    _attr_icon = "mdi:speedometer"
    _attr_options = list(SPEED_LEVELS.values())

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "speed")

    @property
    def current_option(self) -> str | None:
        return self.s.speed_name

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_speed(SPEED_BY_NAME[option])


class HaltSensitivitySelect(X2DEntity, SelectEntity):
    _attr_name = "AI halt sensitivity"
    _attr_icon = "mdi:tune-variant"
    _attr_options = HALT_SENSITIVITIES
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "halt_sensitivity")

    @property
    def current_option(self) -> str | None:
        v = self.s.xcam.get("halt_print_sensitivity")
        return v if v in HALT_SENSITIVITIES else None

    async def async_select_option(self, option: str) -> None:
        on = bool(self.s.xcam.get("spaghetti_detector", True))
        await self.coordinator.async_xcam("spaghetti_detector", on, True, option)


class SoakPresetSelect(X2DEntity, SelectEntity):
    _attr_name = "Soak preset"
    _attr_icon = "mdi:spool"

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "soak_preset", always_available=True)
        self._labels = {k: v[0] for k, v in SOAK_PRESETS.items()}
        self._attr_options = list(self._labels.values())

    @property
    def current_option(self) -> str | None:
        return self._labels.get(self.coordinator.settings.get("soak_preset", "custom"))

    async def async_select_option(self, option: str) -> None:
        key = next(k for k, v in self._labels.items() if v == option)
        await self.coordinator.async_set_setting("soak_preset", key)


class SdFileSelect(X2DEntity, SelectEntity):
    _attr_name = "SD file"
    _attr_icon = "mdi:file-cad"

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "sd_file", always_available=True)

    @property
    def options(self) -> list[str]:
        paths = [f["path"] for f in self.coordinator.sd_files]
        sel = self.coordinator.settings.get("sd_selected")
        if sel and sel not in paths:
            paths.insert(0, sel)
        return [NONE, *paths]

    @property
    def current_option(self) -> str | None:
        return self.coordinator.settings.get("sd_selected") or NONE

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_setting("sd_selected", None if option == NONE else option)


class PlateSelect(X2DEntity, SelectEntity):
    _attr_name = "Print plate"
    _attr_icon = "mdi:numeric"
    _attr_options = [str(i) for i in range(1, 17)]

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "print_plate", always_available=True)

    @property
    def current_option(self) -> str | None:
        return str(self.coordinator.settings.get("print_plate", 1))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_setting("print_plate", int(option))


class TraySelect(X2DEntity, SelectEntity):
    _attr_name = "Filament slot"
    _attr_icon = "mdi:tray"

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "ams_slot")

    def _map(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.s.all_trays:
            where = (f"Ext {t.tray_id + 1}" if t.ams_id == 254 else
                     f"AMS{t.ams_id + 1}·{t.tray_id + 1}" if t.ams_id < 128 else f"HT{t.ams_id - 127}")
            out[f"{where} {t.label}"] = t.global_index
        return out or {NONE: -1}

    @property
    def options(self) -> list[str]:
        return list(self._map())

    @property
    def current_option(self) -> str | None:
        sel = self.coordinator.settings.get("ams_selected")
        return next((k for k, v in self._map().items() if v == sel), None)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_setting("ams_selected", self._map().get(option, -1))


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    add([SpeedSelect(c), HaltSensitivitySelect(c), SoakPresetSelect(c), SdFileSelect(c),
         PlateSelect(c), TraySelect(c), ConnectionModeSelect(c)])
