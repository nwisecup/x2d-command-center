"""Chamber camera: RTSPS stream (HA serves it over WebRTC via go2rtc) + stills via ffmpeg."""
from __future__ import annotations

import time

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .coordinator import X2DCoordinator as C
from .entity import X2DEntity


class X2DCamera(X2DEntity, Camera):
    _attr_name = "Camera"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coord: C) -> None:
        X2DEntity.__init__(self, coord, "camera")
        Camera.__init__(self)
        self._still: bytes | None = None
        self._still_at = 0.0

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.camera_available

    @property
    def is_streaming(self) -> bool:
        return self.available

    async def stream_source(self) -> str | None:
        return self.coordinator.camera_url

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        if self._still and time.monotonic() - self._still_at < 5:
            return self._still
        img = await self.coordinator.timelapse.grab(width)
        if img:
            self._still, self._still_at = img, time.monotonic()
        return img or self._still


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    add([X2DCamera(entry.runtime_data)])
