"""Firmware update indicator (read-only — installs happen on the printer or in Bambu Studio)."""
from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


class FirmwareUpdate(X2DEntity, UpdateEntity):
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_release_url = "https://wiki.bambulab.com/en/x2d/manual/release-notes"

    def __init__(self, coord: C) -> None:
        super().__init__(coord, "firmware_update")

    @property
    def installed_version(self) -> str | None:
        return self.coordinator.firmware.get("ota")

    @property
    def latest_version(self) -> str | None:
        return self.s.upgrade.get("new_version") or self.installed_version


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    add([FirmwareUpdate(entry.runtime_data)])
