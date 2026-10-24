"""HTTP views: authenticated media (timelapse/snapshots) and .3mf upload → printer."""
from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MAX_UPLOAD = 512 * 1024 * 1024


def _coord(hass: HomeAssistant, entry_id: str):
    from . import coordinators
    return next((c for c in coordinators(hass) if c.config_entry.entry_id == entry_id), None)


class MediaView(HomeAssistantView):
    """Serve clips/thumbnails/snapshots with normal HA auth (signed paths work too)."""

    url = f"/api/{DOMAIN}/{{entry_id}}/media/{{path:.+}}"
    name = f"api:{DOMAIN}:media"

    async def get(self, request: web.Request, entry_id: str, path: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app[KEY_HASS]
        coord = _coord(hass, entry_id)
        if not coord:
            raise web.HTTPNotFound
        resolved = coord.timelapse.resolve(path)
        if not resolved:
            raise web.HTTPNotFound
        return web.FileResponse(resolved, headers={"Cache-Control": "private, max-age=60"})


class UploadView(HomeAssistantView):
    """POST multipart 'file' (+ optional start=1&plate=N) → printer storage via FTPS."""

    url = f"/api/{DOMAIN}/{{entry_id}}/upload"
    name = f"api:{DOMAIN}:upload"

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        coord = _coord(hass, entry_id)
        if not coord:
            raise web.HTTPNotFound
        reader = await request.multipart()
        filename, data, start, plate = None, None, False, None
        while (part := await reader.next()) is not None:
            if part.name == "file":
                filename = (part.filename or "upload.3mf").rsplit("/", 1)[-1]
                chunks, size = [], 0
                while chunk := await part.read_chunk(65536):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        return web.json_response({"error": "File too large"}, status=413)
                    chunks.append(chunk)
                data = b"".join(chunks)
            elif part.name == "start":
                start = (await part.text()).strip() in ("1", "true", "on")
            elif part.name == "plate":
                try:
                    plate = int(await part.text())
                except ValueError:
                    plate = None
        if not data or not filename:
            return web.json_response({"error": "No file"}, status=400)
        if not filename.lower().endswith(".3mf"):
            return web.json_response({"error": "Only .3mf files can be printed"}, status=400)
        try:
            remote = await coord.async_upload_bytes(data, filename)
            if start:
                await coord.async_print_file(remote, plate)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Upload failed: %s", err)
            return web.json_response({"error": str(err)}, status=502)
        return web.json_response({"remote": remote, "started": start})


def async_register(hass: HomeAssistant) -> None:
    hass.http.register_view(MediaView())
    hass.http.register_view(UploadView())
