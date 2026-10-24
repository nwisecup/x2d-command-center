"""WebSocket API for the bundled card: one snapshot command + a push subscription."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, SOAK_PRESETS
from .coordinator import X2DCoordinator


def _tray(t) -> dict[str, Any]:
    return {"key": t.key, "ams": t.ams_id, "slot": t.tray_id, "global": t.global_index, "present": t.present,
            "type": t.type, "name": t.sub_brand, "color": t.color, "remain": t.remain,
            "nozzle_min": t.nozzle_min, "nozzle_max": t.nozzle_max}


def snapshot(c: X2DCoordinator) -> dict[str, Any]:
    s = c.state
    return {
        "entry_id": c.config_entry.entry_id,
        "name": c.config_entry.title,
        "serial": c.serial,
        "model": c.model,
        "connected": c.connected,
        "controls_ok": c.controls_ok,
        "state": {
            "gcode_state": s.gcode_state, "stage": s.stage, "percent": s.percent,
            "remaining_min": s.remaining_min, "layer": s.layer, "total_layers": s.total_layers,
            "task": s.task_name, "speed": s.speed_name, "speed_mag": s.speed_mag,
            "nozzles": [{"id": n.id, "temp": n.temp, "target": n.target, "diameter": n.diameter, "type": n.type}
                        for n in s.nozzles],
            "active_nozzle": s.active_nozzle, "bed": s.bed_temp, "bed_target": s.bed_target,
            "chamber": s.chamber_temp, "chamber_target": s.chamber_target, "fans": s.fans,
            "lights": s.lights, "door_open": s.door_open, "wifi": s.wifi_dbm, "sdcard": s.sdcard,
            "hms": [{"code": h.full_code, "wiki": h.wiki, "severity": h.severity,
                     "text": c.hms_lookup.describe(h.full_code)} for h in s.hms],
            "print_error": s.print_error, "skipped": s.skipped_objects,
            "xcam": s.xcam, "flags": s.flags, "tray_now": s.tray_now,
        },
        "amss": [{"id": a.id, "humidity_index": a.humidity_index, "humidity_pct": a.humidity_pct,
                  "temp": a.temp, "drying_min": a.dry_remaining_min, "trays": [_tray(t) for t in a.trays]}
                 for a in s.amss],
        "external": [_tray(t) for t in s.external],
        "job": c.job and {
            "name": c.job.get("name"), "started": c.job.get("started"), "weight_g": c.job.get("weight_g"),
            "cost": c.job_cost, "energy_kwh": c.job.get("energy_kwh"), "plate": c.job.get("plate"),
        },
        "job_meta": c.job_meta and {
            "objects": c.job_meta.get("objects", []), "filaments": c.job_meta.get("filaments", []),
            "bed_type": c.job_meta.get("bed_type"), "prediction_s": c.job_meta.get("prediction_s"),
        },
        "pace": {"spl": c.pace.seconds_per_layer, "lph": c.pace.layers_per_hour,
                 "eta": c.smart_eta and c.smart_eta.isoformat(),
                 "printer_eta": c.printer_eta and c.printer_eta.isoformat(), "drift": c.eta_drift_min,
                 "elapsed": c.elapsed_min},
        "env": {"ambient_f": c.ambient_f, "rh": c.ambient_rh, "dew_f": c.dew_point_f,
                "margin_f": c.startup_margin_f, "too_cold": c.too_cold, "condensation": c.condensation_risk},
        "soak": {"phase": c.soak.phase.value, "active": c.soak.active, "held": round(c.soak.held_min, 1),
                 "required": c.soak_hold_required, "remaining": c.soak_remaining,
                 "progress": c.soak.progress(c.soak_inputs()), "rate": c.soak.rate,
                 "ready_at": c.soak_ready_at and c.soak_ready_at.isoformat(),
                 "start_at": c.soak_start_at and c.soak_start_at.isoformat(),
                 "presets": {k: {"label": v[0], "chamber": v[1], "bed": v[2], "hold": v[3]}
                             for k, v in SOAK_PRESETS.items()}},
        "settings": dict(c.settings),
        "stats": dict(c.stats),
        "history": c.history[:25],
        "connection": {"mode": c.mode, "link": c.link, "local": c.local_connected,
                       "cloud": c.cloud_connected, "cloud_linked": bool(c.cloud_cfg.get("token")),
                       "has_lan": c.has_lan},
        "queue": [{"file": q["file"], "plate": q.get("plate")} for q in c.queue],
        "advisor": c.advisor_warnings,
        "maintenance": c.maintenance_status,
        "pairing": c.job_pairing,
        "timelapse": {"library": c.timelapse.library, "rendering": c.timelapse.rendering,
                      "recording": c.timelapse.job is not None, "frames": c.timelapse.frame_count,
                      "total_mb": c.timelapse.total_mb},
        "sd_files": c.sd_files[:200],
        "sd_timelapses": c.sd_timelapses[:50],
        "entities": {"camera": c.entity_id_for("camera")},
        "firmware": c.firmware.get("ota"),
        "upgrade": s.upgrade,
    }


def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_printers)
    websocket_api.async_register_command(hass, ws_snapshot)
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_frame_sets)
    websocket_api.async_register_command(hass, ws_set_setting)
    websocket_api.async_register_command(hass, ws_filament_db)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/filament_db"})
@callback
def ws_filament_db(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    from . import filament_db as fdb
    connection.send_result(msg["id"], fdb.export())


def _get(hass: HomeAssistant, entry_id: str | None) -> X2DCoordinator | None:
    from . import coordinators
    coords = coordinators(hass)
    if entry_id:
        return next((c for c in coords if c.config_entry.entry_id == entry_id), None)
    return coords[0] if coords else None


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/printers"})
@callback
def ws_printers(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    from . import coordinators
    connection.send_result(msg["id"], [
        {"entry_id": c.config_entry.entry_id, "name": c.config_entry.title, "serial": c.serial,
         "model": c.model, "connected": c.connected} for c in coordinators(hass)])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/snapshot", vol.Optional("entry_id"): str})
@callback
def ws_snapshot(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    c = _get(hass, msg.get("entry_id"))
    if not c:
        connection.send_error(msg["id"], "not_found", "No printer configured")
        return
    connection.send_result(msg["id"], snapshot(c))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe", vol.Optional("entry_id"): str})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    c = _get(hass, msg.get("entry_id"))
    if not c:
        connection.send_error(msg["id"], "not_found", "No printer configured")
        return

    @callback
    def push() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], snapshot(c)))

    connection.subscriptions[msg["id"]] = c.async_add_listener(push)
    connection.send_result(msg["id"])
    push()


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/frame_sets", vol.Optional("entry_id"): str})
@websocket_api.async_response
async def ws_frame_sets(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    c = _get(hass, msg.get("entry_id"))
    if not c:
        connection.send_error(msg["id"], "not_found", "No printer configured")
        return
    connection.send_result(msg["id"], await c.timelapse.frame_sets())


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/set_setting", vol.Optional("entry_id"): str,
    vol.Required("key"): str, vol.Required("value"): vol.Any(str, int, float, bool, None),
})
@websocket_api.async_response
async def ws_set_setting(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    c = _get(hass, msg.get("entry_id"))
    if not c:
        connection.send_error(msg["id"], "not_found", "No printer configured")
        return
    from .coordinator import SETTINGS_DEFAULTS
    if msg["key"] not in SETTINGS_DEFAULTS:
        connection.send_error(msg["id"], "bad_key", f"Unknown setting {msg['key']}")
        return
    await c.async_set_setting(msg["key"], msg["value"])
    connection.send_result(msg["id"])
