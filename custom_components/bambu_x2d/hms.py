"""HMS error descriptions.

Codes and wiki links are computed locally. Human-readable descriptions come from
Bambu's public lookup table, fetched once and cached on disk. This is optional
(Options → Advanced) — with it off you get codes + wiki links only.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN, HMS_LOOKUP_URL

_LOGGER = logging.getLogger(__name__)
REFRESH_S = 14 * 86400


def _flatten(payload: Any) -> dict[str, str]:
    """Accept the couple of shapes the endpoint has used."""
    out: dict[str, str] = {}
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    for section in ("device_hms", "device_error"):
        block = data.get(section) if isinstance(data, dict) else None
        if isinstance(block, dict):
            for _lang, items in block.items():
                if isinstance(items, list):
                    for it in items:
                        code, text = it.get("ecode"), it.get("intro")
                        if code and text:
                            out[str(code).upper()] = str(text)
    return out


class HmsLookup:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, 1, f"{DOMAIN}.hms_cache")
        self._table: dict[str, str] = {}
        self._fetched = 0.0

    async def async_load(self, allow_fetch: bool) -> None:
        cached = await self._store.async_load() or {}
        self._table = cached.get("table", {})
        self._fetched = cached.get("fetched", 0.0)
        if allow_fetch and (not self._table or time.time() - self._fetched > REFRESH_S):
            self.hass.async_create_background_task(self._async_fetch(), "bambu_x2d_hms_fetch")

    async def _async_fetch(self) -> None:
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(HMS_LOOKUP_URL, timeout=20) as resp:
                payload = await resp.json(content_type=None)
            table = _flatten(payload)
            if table:
                self._table, self._fetched = table, time.time()
                await self._store.async_save({"table": table, "fetched": self._fetched})
                _LOGGER.debug("Loaded %d HMS descriptions", len(table))
        except Exception as err:  # noqa: BLE001 — optional nicety, never fatal
            _LOGGER.debug("HMS description fetch failed: %s", err)

    def describe(self, full_code: str) -> str | None:
        key = full_code.replace("_", "").upper()
        return self._table.get(key) or self._table.get(full_code.upper())

    def describe_error(self, print_error: int) -> str | None:
        if not print_error:
            return None
        hexcode = f"{print_error:08X}"
        return self._table.get(hexcode) or self._table.get(f"{hexcode[:4]}_{hexcode[4:]}")
