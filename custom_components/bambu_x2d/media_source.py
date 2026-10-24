"""Expose the timelapse library in Home Assistant's media browser (and on Cast targets)."""
from __future__ import annotations

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    return X2DMediaSource(hass)


class X2DMediaSource(MediaSource):
    name = NAME

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    def _coords(self):
        from . import coordinators
        return coordinators(self.hass)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        entry_id, _, clip = (item.identifier or "").partition("/")
        coord = next((c for c in self._coords() if c.config_entry.entry_id == entry_id), None)
        if not coord or not coord.timelapse.resolve(f"timelapse/{clip}"):
            raise Unresolvable("Clip not found")
        mime = "image/gif" if clip.endswith(".gif") else "video/mp4"
        return PlayMedia(coord.timelapse.media_url(f"timelapse/{clip}"), mime)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        if not item.identifier:
            coords = self._coords()
            if len(coords) == 1:
                return await self._browse_printer(coords[0])
            return BrowseMediaSource(
                domain=DOMAIN, identifier="", media_class=MediaClass.DIRECTORY, media_content_type="",
                title=NAME, can_play=False, can_expand=True,
                children=[BrowseMediaSource(
                    domain=DOMAIN, identifier=c.config_entry.entry_id, media_class=MediaClass.DIRECTORY,
                    media_content_type="", title=c.config_entry.title, can_play=False, can_expand=True,
                ) for c in coords])
        entry_id = item.identifier.split("/")[0]
        coord = next((c for c in self._coords() if c.config_entry.entry_id == entry_id), None)
        if not coord:
            raise Unresolvable("Printer not found")
        return await self._browse_printer(coord)

    async def _browse_printer(self, coord) -> BrowseMediaSource:
        children = [BrowseMediaSource(
            domain=DOMAIN, identifier=f"{coord.config_entry.entry_id}/{c['name']}",
            media_class=MediaClass.VIDEO if c["name"].endswith((".mp4", ".avi")) else MediaClass.IMAGE,
            media_content_type="image/gif" if c["name"].endswith(".gif") else "video/mp4",
            title=c["name"], can_play=True, can_expand=False,
            thumbnail=c["thumb"],
        ) for c in coord.timelapse.library]
        return BrowseMediaSource(
            domain=DOMAIN, identifier=coord.config_entry.entry_id, media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO, title=f"{coord.config_entry.title} timelapses",
            can_play=False, can_expand=True, children=children)
