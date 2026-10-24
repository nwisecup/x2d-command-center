"""Download diagnostics — redacts secrets."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import X2DConfigEntry
from .const import CONF_ACCESS_CODE, CONF_HOST, CONF_SERIAL

REDACT = {CONF_ACCESS_CODE, CONF_HOST, CONF_SERIAL, "rtsp_url", "url", "ip",
          "cloud", "token", "email", "uid"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: X2DConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    return {
        "entry": {"data": async_redact_data(dict(entry.data), REDACT), "options": dict(entry.options)},
        "connected": c.connected,
        "mode": c.mode,
        "link": c.link,
        "controls_ok": c.controls_ok,
        "firmware": c.firmware,
        "raw_report": async_redact_data(c.raw, REDACT),
        "settings": c.settings,
        "stats": c.stats,
        "soak": {"phase": c.soak.phase.value, "rate": c.soak.rate},
        "timelapse": {"clips": len(c.timelapse.library), "total_mb": c.timelapse.total_mb},
        "history_count": len(c.history),
        "last_command": c.last_command,
    }
