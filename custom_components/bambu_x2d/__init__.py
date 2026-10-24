"""X2D Command Center — local-only Home Assistant integration for Bambu Lab X2D (and kin)."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, VERSION
from .coordinator import X2DCoordinator

_LOGGER = logging.getLogger(__name__)

type X2DConfigEntry = ConfigEntry[X2DCoordinator]

PLATFORMS = [
    Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT,
    Platform.BUTTON, Platform.LIGHT, Platform.FAN, Platform.CLIMATE, Platform.CAMERA, Platform.IMAGE,
    Platform.UPDATE, Platform.EVENT, Platform.DATETIME,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_URL = f"/{DOMAIN}_static"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled card, services, websocket API, HTTP views and media source once."""
    from . import http, services, websocket

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend"), True)]
    )
    add_extra_js_url(hass, f"{CARD_URL}/x2d-command-card.js?v={VERSION}")
    services.async_register(hass)
    websocket.async_register(hass)
    http.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry) -> bool:
    coord = X2DCoordinator(hass, entry)
    entry.runtime_data = coord
    await coord.async_start()

    if not await coord.async_wait_first_report(20):
        auth, cloud_auth = coord.auth_failed, coord.cloud_auth_failed
        await coord.async_shutdown()
        if auth:
            raise ConfigEntryAuthFailed("The printer rejected the access code")
        if cloud_auth:
            raise ConfigEntryAuthFailed("Bambu cloud rejected the stored token")
        where = coord.host or "the Bambu cloud"
        raise ConfigEntryNotReady(f"No status from {where} — is the printer powered on?")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    hass.async_create_background_task(coord.async_refresh_sd(), f"{DOMAIN}_initial_sd")
    return True


async def _options_updated(hass: HomeAssistant, entry: X2DConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: X2DConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.async_shutdown()
    return ok


def coordinators(hass: HomeAssistant) -> list[X2DCoordinator]:
    return [e.runtime_data for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED]


def coordinator_for(hass: HomeAssistant, entry_id: str | None = None, device_id: str | None = None) -> X2DCoordinator:
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.helpers import device_registry as dr

    if device_id:
        dev = dr.async_get(hass).async_get(device_id)
        entry_ids = dev.config_entries if dev else set()
    elif entry_id:
        entry_ids = {entry_id}
    else:
        coords = coordinators(hass)
        if len(coords) == 1:
            return coords[0]
        raise ServiceValidationError("Pick which printer (device_id)")
    for c in coordinators(hass):
        if c.config_entry.entry_id in entry_ids:
            return c
    raise ServiceValidationError("That printer isn't loaded")
