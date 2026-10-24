"""Domain services — the power lane (G-code, raw MQTT, jog, print file, soak, timelapse…)."""
from __future__ import annotations

import json
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

DEVICE = {vol.Optional("device_id"): cv.string, vol.Optional("entry_id"): cv.string}


def _coord(hass: HomeAssistant, call: ServiceCall):
    from . import coordinator_for
    return coordinator_for(hass, call.data.get("entry_id"), call.data.get("device_id"))


def async_register(hass: HomeAssistant) -> None:
    def register(name: str, schema: dict, handler, response: SupportsResponse = SupportsResponse.NONE) -> None:
        hass.services.async_register(DOMAIN, name, handler, vol.Schema({**DEVICE, **schema}),
                                     supports_response=response)

    async def send_gcode(call: ServiceCall) -> None:
        await _coord(hass, call).async_gcode(call.data["gcode"])

    async def send_command(call: ServiceCall) -> None:
        payload = call.data["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError as err:
                raise ServiceValidationError(f"Payload is not valid JSON: {err}") from err
        await _coord(hass, call).async_publish(payload)

    async def jog(call: ServiceCall) -> None:
        await _coord(hass, call).async_jog(call.data["axis"], call.data["distance"])

    async def home(call: ServiceCall) -> None:
        await _coord(hass, call).async_home()

    async def extrude(call: ServiceCall) -> None:
        mm = call.data["distance"] * (-1 if call.data.get("direction") == "retract" else 1)
        await _coord(hass, call).async_extrude(mm, call.data.get("nozzle"))

    async def load_filament(call: ServiceCall) -> None:
        await _coord(hass, call).async_load_tray(call.data["tray"])

    async def unload_filament(call: ServiceCall) -> None:
        await _coord(hass, call).async_unload()

    async def set_tray(call: ServiceCall) -> None:
        await _coord(hass, call).async_set_tray(
            call.data["ams"] - 1, call.data["slot"] - 1, tray_type=call.data["type"],
            color=call.data["color"], temp_min=call.data.get("temp_min", 190),
            temp_max=call.data.get("temp_max", 250), info_idx=call.data.get("info_idx", ""))

    async def dry_filament(call: ServiceCall) -> None:
        await _coord(hass, call).async_ams_dry(call.data["ams"] - 1, call.data["temperature"], call.data["minutes"])

    async def print_file(call: ServiceCall) -> None:
        await _coord(hass, call).async_print_file(
            call.data["file"], call.data.get("plate"),
            **{k: call.data[k] for k in ("use_ams", "timelapse", "bed_leveling", "flow_cali",
                                         "vibration_cali", "layer_inspect", "ams_mapping") if k in call.data})

    async def skip_objects(call: ServiceCall) -> None:
        ids = call.data["objects"]
        if isinstance(ids, str):
            ids = [int(x) for x in ids.replace(";", ",").split(",") if x.strip()]
        await _coord(hass, call).async_skip_objects(ids)

    async def soak_start(call: ServiceCall) -> None:
        c = _coord(hass, call)
        if preset := call.data.get("preset"):
            c.apply_soak_preset(preset)
        await c.async_soak_start(chamber=call.data.get("chamber"), bed=call.data.get("bed"),
                                 hold=call.data.get("hold"), autostart=call.data.get("autostart"))

    async def soak_cancel(call: ServiceCall) -> None:
        await _coord(hass, call).async_soak_cancel()

    async def tl_render(call: ServiceCall) -> dict:
        c = _coord(hass, call)
        clip = await c.timelapse.render(call.data["frame_set"], call.data.get("fps"), call.data.get("width"))
        if not clip:
            raise ServiceValidationError("Render failed — check the logs")
        return {"clip": clip, "url": c.timelapse.media_url(f"timelapse/{clip}")}

    async def tl_speed(call: ServiceCall) -> dict:
        c = _coord(hass, call)
        clip = await c.timelapse.speed_up(call.data["clip"], call.data.get("factor", 4))
        if not clip:
            raise ServiceValidationError("ffmpeg failed — check the logs")
        return {"clip": clip, "url": c.timelapse.media_url(f"timelapse/{clip}")}

    async def tl_gif(call: ServiceCall) -> dict:
        c = _coord(hass, call)
        clip = await c.timelapse.make_gif(call.data["clip"], call.data.get("width", 480))
        if not clip:
            raise ServiceValidationError("ffmpeg failed — check the logs")
        return {"clip": clip, "url": c.timelapse.media_url(f"timelapse/{clip}")}

    async def tl_delete(call: ServiceCall) -> None:
        await _coord(hass, call).timelapse.delete(call.data["clip"])

    async def tl_rename(call: ServiceCall) -> dict:
        clip = await _coord(hass, call).timelapse.rename(call.data["clip"], call.data["name"])
        return {"clip": clip}

    async def delete_sd_file(call: ServiceCall) -> None:
        await _coord(hass, call).async_delete_sd(call.data["file"])

    async def tl_pull(call: ServiceCall) -> dict:
        pulled = await _coord(hass, call).timelapse.pull_from_printer(call.data.get("count", 5))
        return {"pulled": pulled}

    async def upload_file(call: ServiceCall) -> dict:
        from pathlib import Path
        c = _coord(hass, call)
        base = Path(hass.config.path()).resolve()
        path = (base / call.data["path"]).resolve()
        try:
            path.relative_to(base)
        except ValueError as err:
            raise ServiceValidationError("Path must be inside the Home Assistant config folder") from err
        path = str(path)
        remote = await c.async_upload(path, call.data.get("name") or path.rsplit("/", 1)[-1])
        if call.data.get("start_print"):
            await c.async_print_file(remote, call.data.get("plate"))
        return {"remote": remote}

    async def refresh(call: ServiceCall) -> None:
        c = _coord(hass, call)
        await c.async_pushall()
        await c.async_refresh_sd()

    async def queue_add(call: ServiceCall) -> None:
        await _coord(hass, call).async_queue_add(
            call.data["file"], call.data.get("plate"),
            **{k: call.data.get(k) for k in ("use_ams", "timelapse", "bed_leveling", "layer_inspect")})

    async def queue_remove(call: ServiceCall) -> None:
        await _coord(hass, call).async_queue_remove(int(call.data["index"]))

    async def queue_clear(call: ServiceCall) -> None:
        await _coord(hass, call).async_queue_clear()

    async def queue_start_next(call: ServiceCall) -> None:
        await _coord(hass, call).async_queue_start_next()

    async def maintenance_done(call: ServiceCall) -> None:
        await _coord(hass, call).async_maintenance_done(call.data["item"])

    async def filament_info(call: ServiceCall) -> dict:
        from . import filament_db as fdb
        rec = fdb.lookup(call.data.get("type"), call.data.get("info_idx"))
        if not rec:
            raise ServiceValidationError(f"Unknown filament: {call.data.get('type')}")
        out = dict(rec)
        other = call.data.get("pair_with")
        if other:
            out["pairing"] = fdb.compatibility(rec, other)
        return out

    register("send_gcode", {vol.Required("gcode"): cv.string}, send_gcode)
    register("send_command", {vol.Required("payload"): vol.Any(dict, cv.string)}, send_command)
    register("jog", {vol.Required("axis"): vol.In(["X", "Y", "Z", "x", "y", "z"]),
                     vol.Required("distance"): vol.Coerce(float)}, jog)
    register("home", {}, home)
    register("extrude", {vol.Required("distance"): vol.All(vol.Coerce(float), vol.Range(min=1, max=200)),
                         vol.Optional("direction", default="extrude"): vol.In(["extrude", "retract"]),
                         vol.Optional("nozzle"): vol.Coerce(int)}, extrude)
    register("load_filament", {vol.Required("tray"): vol.Coerce(int)}, load_filament)
    register("unload_filament", {}, unload_filament)
    register("set_filament", {vol.Required("ams"): vol.Coerce(int), vol.Required("slot"): vol.Coerce(int),
                              vol.Required("type"): cv.string, vol.Required("color"): cv.string,
                              vol.Optional("temp_min"): vol.Coerce(int), vol.Optional("temp_max"): vol.Coerce(int),
                              vol.Optional("info_idx"): cv.string}, set_tray)
    register("dry_filament", {vol.Required("ams"): vol.Coerce(int),
                              vol.Required("temperature"): vol.All(vol.Coerce(int), vol.Range(min=0, max=85)),
                              vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1440))}, dry_filament)
    register("print_file", {vol.Required("file"): cv.string, vol.Optional("plate"): vol.Coerce(int),
                            vol.Optional("use_ams"): cv.boolean, vol.Optional("timelapse"): cv.boolean,
                            vol.Optional("bed_leveling"): cv.boolean, vol.Optional("flow_cali"): cv.boolean,
                            vol.Optional("vibration_cali"): cv.boolean, vol.Optional("layer_inspect"): cv.boolean,
                            vol.Optional("ams_mapping"): [vol.Coerce(int)]}, print_file)
    register("skip_objects", {vol.Required("objects"): vol.Any(cv.string, [vol.Coerce(int)])}, skip_objects)
    register("start_heat_soak", {vol.Optional("preset"): cv.string, vol.Optional("chamber"): vol.Coerce(float),
                                 vol.Optional("bed"): vol.Coerce(float), vol.Optional("hold"): vol.Coerce(float),
                                 vol.Optional("autostart"): cv.boolean}, soak_start)
    register("cancel_heat_soak", {}, soak_cancel)
    register("render_timelapse", {vol.Required("frame_set"): cv.string, vol.Optional("fps"): vol.Coerce(int),
                                  vol.Optional("width"): vol.Coerce(int)}, tl_render, SupportsResponse.OPTIONAL)
    register("speed_up_timelapse", {vol.Required("clip"): cv.string,
                                    vol.Optional("factor", default=4): vol.In([2, 4, 8])}, tl_speed, SupportsResponse.OPTIONAL)
    register("make_gif", {vol.Required("clip"): cv.string, vol.Optional("width", default=480): vol.Coerce(int)},
             tl_gif, SupportsResponse.OPTIONAL)
    register("delete_timelapse", {vol.Required("clip"): cv.string}, tl_delete)
    register("rename_timelapse", {vol.Required("clip"): cv.string, vol.Required("name"): cv.string},
             tl_rename, SupportsResponse.OPTIONAL)
    register("delete_sd_file", {vol.Required("file"): cv.string}, delete_sd_file)
    register("pull_printer_timelapses", {vol.Optional("count", default=5): vol.Coerce(int)}, tl_pull,
             SupportsResponse.OPTIONAL)
    register("upload_file", {vol.Required("path"): cv.string, vol.Optional("name"): cv.string,
                             vol.Optional("start_print", default=False): cv.boolean,
                             vol.Optional("plate"): vol.Coerce(int)}, upload_file, SupportsResponse.OPTIONAL)
    register("refresh", {}, refresh)
    register("queue_add", {vol.Required("file"): cv.string, vol.Optional("plate"): vol.Coerce(int),
                           vol.Optional("use_ams"): cv.boolean, vol.Optional("timelapse"): cv.boolean,
                           vol.Optional("bed_leveling"): cv.boolean, vol.Optional("layer_inspect"): cv.boolean},
             queue_add)
    register("queue_remove", {vol.Required("index"): vol.Coerce(int)}, queue_remove)
    register("queue_clear", {}, queue_clear)
    register("queue_start_next", {}, queue_start_next)
    register("maintenance_done", {vol.Required("item"): cv.string}, maintenance_done)
    register("filament_info", {vol.Optional("type"): cv.string, vol.Optional("info_idx"): cv.string,
                               vol.Optional("pair_with"): cv.string}, filament_info, SupportsResponse.ONLY)
