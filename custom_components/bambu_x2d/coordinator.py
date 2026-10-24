"""The hub: one per printer. Owns the MQTT link, state, job tracking, engines and commands."""
from __future__ import annotations

import asyncio
import io
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import commands as cmd
from . import filament_db as fdb
from . import maintenance as maint
from .advisor import AdvisorInputs, evaluate
from .client import RC_NOT_AUTHORIZED, BambuMqttClient, make_ssl_context
from .cloud import HOSTS as CLOUD_HOSTS
from .cloud import uid_from_token
from .const import (
    CAL_BED_LEVEL,
    CONF_ACCESS_CODE,
    CONF_CLOUD,
    CONF_HOST,
    CONF_MODE,
    CONF_MODEL,
    CONF_SERIAL,
    FIRST_LAYER_CHECK_LAYER,
    MODE_CLOUD,
    MODE_LAN,
    QUEUE_LIMIT,
    DEFAULT_OPTIONS,
    DOMAIN,
    ENERGY_TICK_S,
    HISTORY_LIMIT,
    MANUFACTURER,
    OPT_AMBIENT_HUM,
    OPT_AMBIENT_TEMP,
    OPT_CAMERA_URL,
    OPT_DUAL_NOZZLE_T,
    OPT_ENERGY_PRICE,
    OPT_FILAMENT_PRICE,
    OPT_FILAMENT_PRICES,
    OPT_HEATER,
    OPT_HMS_LOOKUP,
    OPT_MIN_START_F,
    OPT_POWER,
    OPT_SD_URL_PREFIX,
    OPT_SOAK_BAND,
    OPT_SOAK_COLD_MAX,
    OPT_SOAK_COLD_PER_F,
    OPT_SOAK_COLD_REF_F,
    OPT_SOAK_KEEP_WARM,
    OPT_SOAK_MAX_HEAT,
    OPT_TL_ENABLED,
    PUSHALL_INTERVAL_S,
    RTSP_PORT,
    RUNOUT_STAGES,
    SD_REFRESH_S,
    SOAK_PRESETS,
    SOAK_TICK_S,
    STORE_VERSION,
    TRAY_EXTERNAL,
)
from .derived import PaceTracker, c_to_f, dew_point_c, f_to_c, filament_cost, parse_price_map
from .ftp import BambuFtp
from .hms import HmsLookup
from .models import PrinterState, deep_merge, parse_firmware, parse_state
from .notifications import Notifier
from .soak import Inputs, Phase, SoakConfig, SoakEngine
from .threemf import parse_3mf
from .timelapse import TimelapseManager

_LOGGER = logging.getLogger(__name__)

SETTINGS_DEFAULTS: dict[str, Any] = {
    "soak_preset": "abs_asa", "soak_chamber": 60, "soak_bed": 100, "soak_hold": 25,
    "soak_autostart": False, "soak_use_heater": False, "soak_cold_scaling": True,
    "soak_armed": False, "soak_ready_by": None, "soak_rate": 0.8,
    "sd_selected": None, "print_plate": 1, "print_use_ams": True, "print_bed_level": True,
    "print_layer_inspect": True, "print_timelapse": False, "print_flow_cali": False,
    "print_vibration": False, "ha_timelapse": None, "notifications": True, "ams_selected": 0,
    "queue_auto": False, "maint": {}, "advisor": True,
}

STATS_DEFAULTS: dict[str, Any] = {
    "finished": 0, "failed": 0, "cancelled": 0, "print_seconds": 0, "filament_g": 0.0,
    "filament_cost": 0.0, "energy_kwh": 0.0, "energy_cost": 0.0, "by_type": {}, "abrasive_g": 0.0,
}


class X2DCoordinator(DataUpdateCoordinator[PrinterState]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN} {entry.title}", config_entry=entry,
                         update_interval=None, always_update=False)
        self.host: str = entry.data.get(CONF_HOST) or ""
        self.serial: str = entry.data[CONF_SERIAL]
        self.access_code: str = entry.data[CONF_ACCESS_CODE]
        self.model: str = entry.data.get(CONF_MODEL) or "X2D"
        self.mode: str = entry.data.get(CONF_MODE) or MODE_LAN
        self.cloud_cfg: dict[str, Any] = dict(entry.data.get(CONF_CLOUD) or {})

        self.raw: dict = {}
        self.firmware: dict[str, str] = {}
        self.local_connected = False
        self.cloud_connected = False
        self.auth_failed = False
        self.cloud_auth_failed = False
        self.first_report = asyncio.Event()
        self.controls_ok: bool | None = None
        self.last_command: dict[str, Any] | None = None

        self.client: BambuMqttClient | None = None
        self.cloud_client: BambuMqttClient | None = None
        if self.host and self.mode != MODE_CLOUD:
            self.client = BambuMqttClient(
                self.host, self.serial, self.access_code,
                self._mqtt_message, lambda ok, rc: self._mqtt_connection("local", ok, rc))
        if self.mode != MODE_LAN and self.cloud_cfg.get("token"):
            uid = self.cloud_cfg.get("uid") or uid_from_token(self.cloud_cfg["token"]) or ""
            region = self.cloud_cfg.get("region", "global")
            self.cloud_client = BambuMqttClient(
                CLOUD_HOSTS.get(region, CLOUD_HOSTS["global"])["mqtt"], self.serial,
                self.cloud_cfg["token"], self._mqtt_message,
                lambda ok, rc: self._mqtt_connection("cloud", ok, rc),
                client_id=f"ha-x2d-cloud-{self.serial[-6:]}", username=str(uid))
        self.ftp = BambuFtp(self.host, self.access_code)
        self.hms_lookup = HmsLookup(hass)
        self.pace = PaceTracker()
        self.store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.settings: dict[str, Any] = dict(SETTINGS_DEFAULTS)
        self.stats: dict[str, Any] = dict(STATS_DEFAULTS)
        self.history: list[dict[str, Any]] = []
        self.queue: list[dict[str, Any]] = []
        self.job: dict[str, Any] | None = None
        self.job_meta: dict[str, Any] | None = None
        self.cover: bytes | None = None
        self.cover_updated: datetime | None = None
        self.sd_files: list[dict[str, Any]] = []
        self.sd_timelapses: list[dict[str, Any]] = []
        self.soak = SoakEngine()
        self.timelapse = TimelapseManager(hass, self)
        self.notifier = Notifier(hass, self)

        self._event_listeners: list[Callable[[str, dict], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._last_push = 0.0
        self._push_handle: Callable[[], None] | None = None
        self._pending: PrinterState | None = None
        self._known_hms: set[str] = set()
        self._milestones: set[int] = set()
        self._energy_last: float | None = None
        self._device_id: str | None = None
        self._meta_task: asyncio.Task | None = None
        self._first_layer_sent = False
        self._advisor_alerted: set[str] = set()

    # ================================================================ props
    @property
    def opts(self) -> dict[str, Any]:
        return {**DEFAULT_OPTIONS, **self.config_entry.options}

    @property
    def connected(self) -> bool:
        return self.local_connected or self.cloud_connected

    @property
    def link(self) -> str:
        if self.local_connected and self.cloud_connected:
            return "both"
        if self.local_connected:
            return "local"
        if self.cloud_connected:
            return "cloud"
        return "offline"

    @property
    def has_lan(self) -> bool:
        return bool(self.host) and self.mode != MODE_CLOUD

    @property
    def state(self) -> PrinterState:
        return self.data or PrinterState()

    @property
    def device_info(self) -> DeviceInfo:
        fw = self.firmware.get("ota")
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=self.config_entry.title,
            manufacturer=MANUFACTURER,
            model=self.model,
            serial_number=self.serial,
            sw_version=fw,
        )

    @property
    def device_id(self) -> str | None:
        if self._device_id is None:
            dev = dr.async_get(self.hass).async_get_device(identifiers={(DOMAIN, self.serial)})
            self._device_id = dev.id if dev else None
        return self._device_id

    @property
    def camera_url(self) -> str | None:
        override = (self.opts.get(OPT_CAMERA_URL) or "").strip()
        if override:
            return override
        if not self.has_lan:
            return None
        reported = self.state.camera_url_reported
        if reported:
            if "@" not in reported:  # printer reports it without credentials
                reported = reported.replace("://", f"://bblp:{self.access_code}@", 1)
            return reported
        return f"rtsps://bblp:{self.access_code}@{self.host}:{RTSP_PORT}/streaming/live/1"

    @property
    def camera_available(self) -> bool:
        return self.camera_url is not None and str(self.state.ipcam.get("rtsp_url", "")).lower() != "disable"

    @property
    def primary_light(self) -> str:
        lights = list(self.state.lights)
        return "chamber_light" if "chamber_light" in lights or not lights else lights[0]

    @property
    def job_name(self) -> str | None:
        return (self.job or {}).get("name") or self.state.task_name

    @property
    def ha_timelapse(self) -> bool:
        v = self.settings.get("ha_timelapse")
        return bool(self.opts[OPT_TL_ENABLED] if v is None else v)

    # ---- environment
    def _read_temp_f(self, entity_id: str | None) -> float | None:
        if not entity_id or not (st := self.hass.states.get(entity_id)):
            return None
        try:
            v = float(st.state)
        except (TypeError, ValueError):
            return None
        unit = st.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        return c_to_f(v) if unit == UnitOfTemperature.CELSIUS else v

    @property
    def ambient_f(self) -> float | None:
        return self._read_temp_f(self.opts.get(OPT_AMBIENT_TEMP))

    @property
    def ambient_rh(self) -> float | None:
        ent = self.opts.get(OPT_AMBIENT_HUM)
        if not ent or not (st := self.hass.states.get(ent)):
            return None
        try:
            return float(st.state)
        except (TypeError, ValueError):
            return None

    @property
    def dew_point_f(self) -> float | None:
        return c_to_f(dew_point_c(f_to_c(self.ambient_f), self.ambient_rh))

    @property
    def startup_margin_f(self) -> float | None:
        a = self.ambient_f
        return None if a is None else round(a - float(self.opts[OPT_MIN_START_F]), 1)

    @property
    def too_cold(self) -> bool | None:
        m = self.startup_margin_f
        return None if m is None else m < 0

    @property
    def condensation_risk(self) -> bool | None:
        a, d = self.ambient_f, self.dew_point_f
        return None if a is None or d is None else (a - d) < 4

    # ---- job-derived
    @property
    def layers_remaining(self) -> int:
        s = self.state
        return max(s.total_layers - s.layer, 0)

    @property
    def smart_eta(self) -> datetime | None:
        if not self.state.is_active:
            return None
        secs = self.pace.eta_seconds(self.layers_remaining)
        return dt_util.utcnow() + timedelta(seconds=secs) if secs is not None else None

    @property
    def printer_eta(self) -> datetime | None:
        s = self.state
        if not s.is_active or s.remaining_min is None:
            return None
        return dt_util.utcnow() + timedelta(minutes=s.remaining_min)

    @property
    def eta_drift_min(self) -> int | None:
        if not self.job or not self.job.get("initial_eta") or not (eta := self.printer_eta):
            return None
        return round((eta.timestamp() - self.job["initial_eta"]) / 60)

    @property
    def elapsed_min(self) -> int | None:
        if not self.job or not self.state.is_active:
            return None
        return round((time.time() - self.job["started"]) / 60)

    @property
    def job_cost(self) -> dict[str, float | None]:
        j = self.job or (self.history[0] if self.history else None)
        if not j:
            return {"filament": None, "energy": None, "total": None}
        fil, en = j.get("filament_cost"), j.get("energy_cost")
        total = round((fil or 0) + (en or 0), 2) if fil is not None or en is not None else None
        return {"filament": fil, "energy": en, "total": total}

    # ---- advisor / maintenance
    @property
    def advisor_warnings(self) -> list[dict[str, Any]]:
        if not self.settings.get("advisor", True):
            return []
        s = self.state
        job_types = [f["type"] for f in ((self.job or {}).get("filaments") or []) if f.get("type")]
        if not job_types and s.is_active and s.active_tray and s.active_tray.type:
            job_types = [s.active_tray.type]
        loaded = [{"type": t.type, "name": t.sub_brand, "info_idx": t.info_idx, "remain": t.remain,
                   "active": s.tray_now == t.global_index}
                  for t in s.all_trays if t.present]
        noz = s.nozzle
        return evaluate(AdvisorInputs(
            printing=s.is_active,
            job_filament_types=job_types,
            loaded=loaded,
            nozzle_type=noz.type if noz else None,
            nozzle_diameter=noz.diameter if noz else None,
            chamber_c=s.chamber_temp,
            ams_humidity=[(a.id, a.humidity_index) for a in s.amss],
            ambient_f=self.ambient_f,
            min_start_f=float(self.opts[OPT_MIN_START_F]),
            door_open=s.door_open,
            active_type=s.active_tray.type if s.active_tray else None,
        ))

    @property
    def maintenance_status(self) -> list[dict[str, Any]]:
        noz = self.state.nozzle
        return maint.status(self.stats.get("print_seconds", 0) / 3600,
                            self.settings.get("maint") or {},
                            self.stats.get("abrasive_g", 0.0),
                            noz.type if noz else None)

    async def async_maintenance_done(self, item: str) -> None:
        done = dict(self.settings.get("maint") or {})
        done[item] = round(self.stats.get("print_seconds", 0) / 3600, 1)
        if item == "nozzle_wear":
            self.stats["abrasive_g"] = 0.0
        await self.async_set_setting("maint", done)

    @property
    def job_pairing(self) -> dict[str, Any] | None:
        types = [f["type"] for f in ((self.job_meta or {}).get("filaments") or []) if f.get("type")]
        return fdb.classify_pairing(types) if len(types) > 1 else None

    # ---- queue
    async def async_queue_add(self, file: str, plate: int | None = None, **opts: Any) -> None:
        if len(self.queue) >= QUEUE_LIMIT:
            raise HomeAssistantError("Queue is full")
        self.queue.append({"file": file, "plate": int(plate or self.settings["print_plate"]),
                           "added": time.time(), **{k: v for k, v in opts.items() if v is not None}})
        await self._async_save()
        self.async_update_listeners()

    async def async_queue_remove(self, index: int) -> None:
        if 0 <= index < len(self.queue):
            self.queue.pop(index)
            await self._async_save()
            self.async_update_listeners()

    async def async_queue_clear(self) -> None:
        self.queue.clear()
        await self._async_save()
        self.async_update_listeners()

    async def async_queue_start_next(self) -> None:
        if not self.queue:
            raise HomeAssistantError("The queue is empty")
        nxt = self.queue[0]
        await self.async_print_file(nxt["file"], nxt.get("plate"),
                                    **{k: nxt[k] for k in ("use_ams", "timelapse", "bed_leveling",
                                                            "layer_inspect") if k in nxt})
        self.queue.pop(0)
        self._fire("queue_next", {"file": nxt["file"], "remaining": len(self.queue)})
        await self._async_save()
        self.async_update_listeners()

    async def async_set_mode(self, mode: str) -> None:
        """Switch lan/hybrid/cloud — updates the entry and reloads."""
        if mode == self.mode:
            return
        if mode != MODE_CLOUD and not self.host:
            raise HomeAssistantError("No LAN address known — reconfigure the printer's IP first")
        if mode != MODE_LAN and not self.cloud_cfg.get("token"):
            raise HomeAssistantError("No Bambu account linked — link it in the integration options")
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_MODE: mode})
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    # ---- soak
    def soak_config(self) -> SoakConfig:
        o, s = self.opts, self.settings
        return SoakConfig(
            chamber_c=float(s["soak_chamber"]), bed_c=float(s["soak_bed"]), hold_base_min=float(s["soak_hold"]),
            band_c=float(o[OPT_SOAK_BAND]), max_heat_min=float(o[OPT_SOAK_MAX_HEAT]),
            keep_warm_min=float(o[OPT_SOAK_KEEP_WARM]), cold_scaling=bool(s["soak_cold_scaling"]),
            cold_ref_f=float(o[OPT_SOAK_COLD_REF_F]), cold_min_per_f=float(o[OPT_SOAK_COLD_PER_F]),
            cold_max_min=float(o[OPT_SOAK_COLD_MAX]), min_start_f=float(o[OPT_MIN_START_F]),
            use_ambient_heater=bool(s["soak_use_heater"] and o.get(OPT_HEATER)),
        )

    def soak_inputs(self) -> Inputs:
        s = self.state
        return Inputs(now=time.time(), chamber=s.chamber_temp, bed=s.bed_temp,
                      ambient_f=self.ambient_f, printing=s.is_active)

    @property
    def soak_hold_required(self) -> float:
        if self.soak.active:
            return self.soak.hold_required
        return self.soak_config().hold_required(self.ambient_f)

    @property
    def soak_remaining(self) -> float:
        if not self.soak.active:
            self.soak.cfg = self.soak_config()
        return self.soak.remaining_min(self.soak_inputs())

    @property
    def soak_ready_at(self) -> datetime | None:
        if self.soak.phase not in (Phase.WARMING_AMBIENT, Phase.HEATING, Phase.SOAKING):
            return None
        return dt_util.utcnow() + timedelta(minutes=self.soak_remaining)

    @property
    def soak_start_at(self) -> datetime | None:
        rb = self.settings.get("soak_ready_by")
        if not rb:
            return None
        ready = dt_util.parse_datetime(rb)
        if ready is None:
            return None
        self.soak.cfg = self.soak.cfg if self.soak.active else self.soak_config()
        lead = self.soak.heatup_estimate_min(self.state.chamber_temp) + self.soak_hold_required + 5
        return ready - timedelta(minutes=lead)

    # ================================================================ lifecycle
    async def async_start(self) -> None:
        stored = await self.store.async_load() or {}
        self.settings.update(stored.get("settings", {}))
        self.stats.update(stored.get("stats", {}))
        self.history = stored.get("history", [])
        self.queue = stored.get("queue", [])
        self.soak.rate = float(self.settings.get("soak_rate") or 0.8)

        await self.hms_lookup.async_load(bool(self.opts[OPT_HMS_LOOKUP]))
        await self.timelapse.async_setup()
        if self.client:
            ctx = await self.hass.async_add_executor_job(make_ssl_context)
            self.client.start(ctx)
        if self.cloud_client:
            cloud_ctx = await self.hass.async_add_executor_job(make_ssl_context, True)
            self.cloud_client.start(cloud_ctx)

        hass = self.hass
        self._unsubs += [
            async_track_time_interval(hass, self._tick_pushall, timedelta(seconds=PUSHALL_INTERVAL_S)),
            async_track_time_interval(hass, self._tick_soak, timedelta(seconds=SOAK_TICK_S)),
            async_track_time_interval(hass, self._tick_energy, timedelta(seconds=ENERGY_TICK_S)),
            async_track_time_interval(hass, self._tick_sd, timedelta(seconds=SD_REFRESH_S)),
            hass.bus.async_listen("mobile_app_notification_action", self.notifier.handle_action),
        ]

    async def async_wait_first_report(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self.first_report.wait(), timeout)
            return True
        except (TimeoutError, asyncio.TimeoutError):
            return False

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._push_handle:
            self._push_handle()
        for client in (self.client, self.cloud_client):
            if client:
                await self.hass.async_add_executor_job(client.stop)
        await self._async_save(now=True)

    async def _async_save(self, now: bool = False) -> None:
        self.settings["soak_rate"] = self.soak.rate

        def _data() -> dict:
            return {"settings": self.settings, "stats": self.stats,
                    "history": self.history[:HISTORY_LIMIT], "queue": self.queue[:QUEUE_LIMIT]}
        if now:
            await self.store.async_save(_data())
        else:
            self.store.async_delay_save(_data, 10)

    # ================================================================ MQTT in
    def _mqtt_message(self, data: dict) -> None:  # paho thread
        self.hass.loop.call_soon_threadsafe(self._handle_message, data)

    def _mqtt_connection(self, link: str, ok: bool, rc: int) -> None:  # paho thread
        self.hass.loop.call_soon_threadsafe(self._handle_connection, link, ok, rc)

    @callback
    def _handle_connection(self, link: str, ok: bool, rc: int) -> None:
        if link == "local":
            self.local_connected = ok
            if ok:
                self.auth_failed = False
            elif rc in RC_NOT_AUTHORIZED and not self.auth_failed:
                self.auth_failed = True
                _LOGGER.warning("Printer rejected the access code — starting re-authentication")
                self.config_entry.async_start_reauth(self.hass)
        else:
            self.cloud_connected = ok
            if ok:
                self.cloud_auth_failed = False
            elif rc in RC_NOT_AUTHORIZED and not self.cloud_auth_failed:
                self.cloud_auth_failed = True
                _LOGGER.warning("Bambu cloud rejected the token — starting re-authentication")
                self.config_entry.async_start_reauth(self.hass)
        if self.data is not None:
            self.async_set_updated_data(parse_state(self.raw, self.firmware, self.connected))
        self.async_update_listeners()

    @callback
    def _handle_message(self, data: dict) -> None:
        p = data.get("print")
        if isinstance(p, dict):
            command = p.get("command")
            if command == "push_status":
                deep_merge(self.raw.setdefault("print", {}), p)
            elif "result" in p:
                self._command_result("print", p)
        for block in ("system", "xcam", "camera"):
            if isinstance(data.get(block), dict) and "result" in data[block]:
                self._command_result(block, data[block])
        info = data.get("info")
        if isinstance(info, dict) and info.get("command") == "get_version":
            self.firmware = parse_firmware(info)
            self._update_device_firmware()
        if "print" not in self.raw:
            return
        state = parse_state(self.raw, self.firmware, self.connected)
        prev = self.data
        self._process_transitions(prev, state)
        if not self.first_report.is_set():
            self.first_report.set()
            self.async_set_updated_data(state)
            self._last_push = time.monotonic()
            return
        self._throttled_push(state)

    def _command_result(self, block: str, body: dict) -> None:
        result = str(body.get("result", "")).lower()
        command = body.get("command")
        if command in (None, "push_status"):
            return
        self.last_command = {"block": block, "command": command, "result": result,
                             "reason": body.get("reason") or body.get("err_code"), "at": time.time()}
        issue = f"controls_rejected_{self.config_entry.entry_id}"
        if result == "success":
            if self.controls_ok is not True:
                ir.async_delete_issue(self.hass, DOMAIN, issue)
            self.controls_ok = True
        elif result == "fail":
            self.controls_ok = False
            ir.async_create_issue(
                self.hass, DOMAIN, issue, is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="controls_rejected",
                translation_placeholders={"name": self.config_entry.title, "command": str(command),
                                          "reason": str(self.last_command["reason"] or "unknown")},
            )
        self.async_update_listeners()

    def _update_device_firmware(self) -> None:
        if (fw := self.firmware.get("ota")) and self.device_id:
            dr.async_get(self.hass).async_update_device(self.device_id, sw_version=fw)

    @callback
    def _throttled_push(self, state: PrinterState) -> None:
        self._pending = state
        wait = 1.0 - (time.monotonic() - self._last_push)
        if wait <= 0:
            self._flush_push()
        elif self._push_handle is None:
            self._push_handle = async_call_later(self.hass, wait, self._flush_push_cb)

    @callback
    def _flush_push_cb(self, _now: datetime) -> None:
        self._push_handle = None
        self._flush_push()

    @callback
    def _flush_push(self) -> None:
        if self._pending is not None:
            self._last_push = time.monotonic()
            state, self._pending = self._pending, None
            self.async_set_updated_data(state)

    # ================================================================ transitions
    def _process_transitions(self, prev: PrinterState | None, new: PrinterState) -> None:
        old_state = prev.gcode_state if prev else None

        if new.is_active and self.job is None:
            self._start_job(new, recovered=prev is None)
        elif self.job and old_state in ("prepare", "running", "pause") and new.gcode_state in ("finish", "failed", "idle"):
            result = "finished" if new.gcode_state == "finish" else ("cancelled" if new.is_cancelled or new.gcode_state == "idle" else "failed")
            self.hass.async_create_task(self._finish_job(new, result))
        elif prev and old_state == "running" and new.gcode_state == "pause":
            self._fire("print_paused", {"stage": new.stage})
            self.hass.async_create_task(self.notifier.send(
                "paused", f"Paused: {self.job_name}", new.stage.replace("_", " "),
                image=self._cam_proxy(), actions=[("RESUME", "Resume"), ("STOP", "Stop")]))
        elif prev and old_state == "pause" and new.gcode_state == "running":
            self._fire("print_resumed", {})

        if self.job and new.gcode_state == "running":
            if prev is None or new.layer != prev.layer:
                self.pace.on_layer(time.time(), new.layer)
                if self.ha_timelapse and new.layer > 0:
                    self.hass.async_create_task(self.timelapse.capture_frame(new.layer))
                if (not self._first_layer_sent and new.layer >= FIRST_LAYER_CHECK_LAYER
                        and prev is not None):
                    self._first_layer_sent = True
                    self._fire("first_layer", {"layer": new.layer})
                    self.hass.async_create_task(self.notifier.send(
                        "first_layer", f"First layers down — {self.job_name}",
                        "Quick look: squished and even? Catching it now saves the whole print.",
                        image=self._cam_proxy(),
                        actions=[("PAUSE", "Pause"), ("STOP", "Stop")]))
            if not self.job.get("initial_eta") and new.remaining_min and time.time() - self.job["started"] > 30:
                self.job["initial_eta"] = time.time() + new.remaining_min * 60
            for mark in (25, 50, 75, 90):
                if new.percent >= mark and mark not in self._milestones:
                    self._milestones.add(mark)
                    if prev is not None:
                        self._fire("milestone", {"percent": mark})
                        if mark in (50, 90):
                            self.hass.async_create_task(self.notifier.send(
                                "milestone", f"{mark}% — {self.job_name}",
                                f"Layer {new.layer}/{new.total_layers} · {new.remaining_min} min left",
                                image=self._cam_proxy()))

        if prev and new.stage_id in RUNOUT_STAGES and prev.stage_id not in RUNOUT_STAGES:
            self._fire("filament_runout", {"tray": new.tray_now})
            self.hass.async_create_task(self.notifier.send(
                "filament_runout", "Filament ran out", f"{self.job_name} is paused — load filament to continue.",
                image=self._cam_proxy(), actions=[("RESUME", "Resume"), ("STOP", "Stop")]))

        codes = {h.full_code for h in new.hms}
        fresh = codes - self._known_hms
        if fresh and prev is not None:
            for code in sorted(fresh):
                text = self.hms_lookup.describe(code) or "See the Bambu wiki for this code."
                self._fire("hms_error", {"code": code, "description": text})
                self.hass.async_create_task(self.notifier.send(
                    "hms_error", f"{self.config_entry.title}: HMS {code}", text, image=self._cam_proxy(),
                    actions=[("PAUSE", "Pause"), ("STOP", "Stop"), ("LIGHT", "Light on")]))
        self._known_hms = codes

    def _cam_proxy(self) -> str | None:
        ent = self.entity_id_for("camera")
        return f"/api/camera_proxy/{ent}" if ent else None

    def entity_id_for(self, key: str) -> str | None:
        from homeassistant.helpers import entity_registry as er
        reg = er.async_get(self.hass)
        for domain in ("camera", "sensor", "binary_sensor", "image", "switch", "button", "event"):
            eid = reg.async_get_entity_id(domain, DOMAIN, f"{self.serial}_{key}")
            if eid:
                return eid
        return None

    def _start_job(self, state: PrinterState, recovered: bool) -> None:
        started = time.time()
        if recovered and state.gcode_start_time:
            started = float(state.gcode_start_time)
        self.job = {
            "id": f"{int(started)}_{state.subtask_id or ''}", "name": state.task_name or "Untitled",
            "file": state.gcode_file, "started": started, "initial_eta": None, "layers": state.total_layers,
            "weight_g": None, "filaments": [], "filament_cost": None, "energy_kwh": 0.0, "energy_cost": None,
            "plate": None, "recovered": recovered, "type": state.print_type,
        }
        self.pace.reset()
        self._milestones = {m for m in (25, 50, 75, 90) if state.percent >= m} if recovered else set()
        self._energy_last = None
        self._first_layer_sent = recovered
        self._advisor_alerted = set()
        self.cover, self.cover_updated, self.job_meta = None, None, None
        if not recovered:
            self._fire("print_started", {"name": self.job["name"]})
            self.hass.async_create_task(self.notifier.send(
                "started", f"Started: {self.job['name']}", f"{state.total_layers} layers", image=self._cam_proxy()))
            if self.too_cold:
                self._fire("too_cold", {"ambient_f": self.ambient_f})
                self.hass.async_create_task(self.notifier.send(
                    "too_cold", f"Ambient is {round(self.ambient_f or 0)} °F",
                    f"Below your {self.opts[OPT_MIN_START_F]} °F floor — expect slow heat-up.",
                    actions=[("PAUSE", "Pause"), ("HEATER_ON", "Heater on")] if self.opts.get(OPT_HEATER) else [("PAUSE", "Pause")]))
        if self.ha_timelapse:
            self.hass.async_create_task(self.timelapse.start_job(self.job["name"]))
        if self._meta_task is None or self._meta_task.done():
            self._meta_task = self.hass.async_create_background_task(self._fetch_job_meta(state), "bambu_x2d_job_meta")

    async def _fetch_job_meta(self, state: PrinterState) -> None:
        name = state.task_name
        if not name or not self.has_lan:
            return
        try:
            path = await self.hass.async_add_executor_job(self.ftp.find_job_file, name)
            if not path:
                _LOGGER.debug("Job file for %s not found on printer storage", name)
                return
            data = await self.hass.async_add_executor_job(self.ftp.download, path)
            plate = None
            if state.gcode_file and "plate_" in state.gcode_file:
                try:
                    plate = int(state.gcode_file.rsplit("plate_", 1)[1].split(".")[0])
                except ValueError:
                    plate = None
            meta = await self.hass.async_add_executor_job(parse_3mf, data, plate)
        except Exception as err:  # noqa: BLE001 — metadata is a nicety
            _LOGGER.debug("Job metadata fetch failed: %s", err)
            return
        self.cover = meta.pop("cover", None)
        self.cover_updated = dt_util.utcnow()
        meta["path"] = path
        self.job_meta = meta
        if self.job:
            self.job["weight_g"] = meta.get("weight_g")
            self.job["filaments"] = meta.get("filaments", [])
            self.job["plate"] = meta.get("plate")
            self.job["prediction_s"] = meta.get("prediction_s")
            self.job["filament_cost"] = filament_cost(
                meta.get("filaments", []), float(self.opts[OPT_FILAMENT_PRICE]),
                parse_price_map(self.opts.get(OPT_FILAMENT_PRICES)))
        self._check_advisor_alerts()
        self.async_update_listeners()

    def _check_advisor_alerts(self) -> None:
        """Push-notify genuinely dangerous advisor findings, once each per job."""
        for w in self.advisor_warnings:
            if w["severity"] != "alert" or w["key"] in self._advisor_alerted:
                continue
            self._advisor_alerted.add(w["key"])
            self._fire("advisor_warning", {"key": w["key"], "title": w["title"], "severity": w["severity"]})
            self.hass.async_create_task(self.notifier.send(
                "advisor", f"⚠ {w['title']}", w["detail"],
                actions=[("PAUSE", "Pause"), ("STOP", "Stop")] if self.state.is_active else None))

    async def _finish_job(self, state: PrinterState, result: str) -> None:
        job, self.job = self.job, None
        if not job:
            return
        ended = time.time()
        job.update(ended=ended, duration_s=int(ended - job["started"]), result=result,
                   error=state.print_error or None, layers_done=state.layer)
        if job.get("energy_kwh"):
            job["energy_cost"] = round(job["energy_kwh"] * float(self.opts[OPT_ENERGY_PRICE]), 2)
        if result != "finished" and job.get("filament_cost") and job.get("layers"):
            frac = min(state.layer / max(job["layers"], 1), 1.0)  # charge for what was printed
            job["filament_cost"] = round(job["filament_cost"] * frac, 2)
            job["weight_g"] = round((job.get("weight_g") or 0) * frac, 1) or None

        snap_name = "last_finished" if result == "finished" else "last_error"
        snap = await self.timelapse.snapshot(snap_name)
        clip = None
        if self.ha_timelapse:
            clip = await self.timelapse.finish_job()
        job["timelapse"] = clip

        st = self.stats
        st[result] = st.get(result, 0) + 1
        st["print_seconds"] += job["duration_s"]
        st["filament_g"] = round(st["filament_g"] + (job.get("weight_g") or 0), 1)
        st["filament_cost"] = round(st["filament_cost"] + (job.get("filament_cost") or 0), 2)
        st["energy_kwh"] = round(st["energy_kwh"] + (job.get("energy_kwh") or 0), 3)
        st["energy_cost"] = round(st["energy_cost"] + (job.get("energy_cost") or 0), 2)
        frac = min(state.layer / max(job.get("layers") or 1, 1), 1.0) if result != "finished" else 1.0
        for f in job.get("filaments") or []:
            t = str(f.get("type") or "?")
            used = (f.get("used_g") or 0) * frac
            st["by_type"][t] = round(st["by_type"].get(t, 0) + used, 1)
            if fdb.abrasive(t, f.get("tray_info_idx")):
                st["abrasive_g"] = round(st.get("abrasive_g", 0.0) + used, 1)
        self.history.insert(0, job)
        del self.history[HISTORY_LIMIT:]
        await self._async_save()

        due = [m for m in self.maintenance_status if m["due"]]
        if due:
            self._fire("maintenance_due", {"items": [m["key"] for m in due]})
            await self.notifier.send(
                "maintenance", f"🔧 {self.config_entry.title}: maintenance due",
                " · ".join(m["label"] for m in due[:3]) + (" …" if len(due) > 3 else ""))

        event = {"finished": "print_finished", "failed": "print_failed", "cancelled": "print_cancelled"}[result]
        self._fire(event, {"name": job["name"], "duration_s": job["duration_s"], "timelapse": clip})
        mins = job["duration_s"] // 60
        cost = self.job_cost_text(job)
        if result == "finished":
            queued = len(self.queue)
            q_note = f" · {queued} queued — clear the bed first" if queued else ""
            actions = [("QUEUE_NEXT", f"Start next ({queued})")] if queued else None
            await self.notifier.send(
                "finished", f"✅ {job['name']} finished", f"{mins // 60}h {mins % 60}m{cost}{q_note}",
                image=snap, video=self.timelapse.media_url(f"timelapse/{clip}") if clip else None,
                actions=actions)
            if queued and self.settings.get("queue_auto"):
                async def _auto_next() -> None:
                    await asyncio.sleep(90)  # grace period to grab the part
                    if self.queue and not self.state.is_active:
                        try:
                            await self.async_queue_start_next()
                        except HomeAssistantError as err:
                            _LOGGER.warning("Queue auto-continue failed: %s", err)
                self.hass.async_create_background_task(_auto_next(), "bambu_x2d_queue_auto")
        else:
            err = self.hms_lookup.describe_error(state.print_error) or (f"Error {state.print_error:08X}" if state.print_error else "")
            await self.notifier.send(result, f"{'❌' if result == 'failed' else '⏹'} {job['name']} {result}",
                                     f"{err} after {mins} min".strip(), image=snap)
        if clip:
            self._fire("timelapse_ready", {"name": clip})
        self.async_update_listeners()

    def job_cost_text(self, job: dict) -> str:
        parts = []
        if job.get("weight_g"):
            parts.append(f"{job['weight_g']:.0f} g")
        total = (job.get("filament_cost") or 0) + (job.get("energy_cost") or 0)
        if total:
            parts.append(f"{self.opts.get('currency', 'USD')} {total:.2f}")
        return (" · " + " · ".join(parts)) if parts else ""

    # ================================================================ events
    def add_event_listener(self, cb: Callable[[str, dict], None]) -> Callable[[], None]:
        self._event_listeners.append(cb)
        return lambda: self._event_listeners.remove(cb)

    @callback
    def _fire(self, kind: str, data: dict) -> None:
        for cb in list(self._event_listeners):
            cb(kind, data)
        self.hass.bus.async_fire(f"{DOMAIN}_event", {"type": kind, "device_id": self.device_id,
                                                     "serial": self.serial, **data})

    # ================================================================ ticks
    async def _tick_pushall(self, _now: datetime) -> None:
        for client, up in ((self.client, self.local_connected), (self.cloud_client, self.cloud_connected)):
            if client and up:
                client.publish(cmd.pushall())
                break

    async def _tick_energy(self, _now: datetime) -> None:
        ent = self.opts.get(OPT_POWER)
        if not self.job or not ent or not (st := self.hass.states.get(ent)):
            self._energy_last = None
            return
        try:
            watts = float(st.state)
        except (TypeError, ValueError):
            return
        if st.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "kW":
            watts *= 1000
        now = time.monotonic()
        if self._energy_last is not None:
            self.job["energy_kwh"] = round(self.job.get("energy_kwh", 0) + watts * (now - self._energy_last) / 3.6e6, 4)
            self.job["energy_cost"] = round(self.job["energy_kwh"] * float(self.opts[OPT_ENERGY_PRICE]), 2)
        self._energy_last = now

    async def _tick_sd(self, _now: datetime | None = None) -> None:
        if self.local_connected and self.has_lan:
            await self.async_refresh_sd()

    async def _tick_soak(self, _now: datetime) -> None:
        if not self.soak.active and self.settings.get("soak_armed") and (start_at := self.soak_start_at):
            ready_by = dt_util.parse_datetime(self.settings.get("soak_ready_by") or "")
            if ready_by and dt_util.utcnow() >= start_at and dt_util.utcnow() < ready_by and not self.state.is_active:
                await self.async_set_setting("soak_armed", False)
                await self.async_soak_start()
                return
        if not self.soak.active:
            return
        await self._apply_soak(self.soak.tick(self.soak_inputs()))
        self.async_update_listeners()

    # ================================================================ soak control
    async def async_soak_start(self, **overrides: Any) -> None:
        for k, v in overrides.items():
            if v is not None:
                self.settings[f"soak_{k}"] = v
        if self.state.is_active:
            raise HomeAssistantError("The printer is busy — heat soak only runs while idle")
        await self._apply_soak(self.soak.start(self.soak_config(), self.soak_inputs()))
        if self.primary_light in self.state.lights:
            await self.async_light(self.primary_light, True)
        self.async_update_listeners()

    async def async_soak_cancel(self) -> None:
        await self._apply_soak(self.soak.cancel())
        self.async_update_listeners()

    async def _apply_soak(self, act) -> None:
        if act.heat:
            bed, chamber = act.heat
            await self.async_gcode([f"M140 S{bed}", f"M141 S{chamber}", "M104 S0", "M106 P2 S0", "M106 P3 S0"])
        if act.heaters_off:
            await self.async_gcode(["M140 S0", "M141 S0", "M104 S0"])
        if act.ambient_heater is not None and (heater := self.opts.get(OPT_HEATER)):
            await self.hass.services.async_call(
                "homeassistant", "turn_on" if act.ambient_heater else "turn_off", {"entity_id": heater}, blocking=False)
        for ev in act.events:
            if ev == "soak_ready":
                self._fire("soak_ready", {"held_min": round(self.soak.held_min, 1)})
                autostart = self.settings.get("soak_autostart") and self.settings.get("sd_selected")
                await self.notifier.send(
                    "soak_ready", "🔥 Heat-soaked",
                    f"Chamber {round(self.state.chamber_temp or 0)} °C, bed {round(self.state.bed_temp or 0)} °C. "
                    + (f"Starting {self.settings['sd_selected']}." if autostart else
                       f"Keeping warm {self.opts[OPT_SOAK_KEEP_WARM]} min."),
                    actions=None if autostart else [("SOAK_START_PRINT", "Start print"), ("SOAK_CANCEL", "Cancel & cool")])
                if autostart:
                    try:
                        await self.async_print_selected()
                    except HomeAssistantError as err:
                        _LOGGER.warning("Auto-start after soak failed: %s", err)
            elif ev == "soak_aborted":
                self._fire("soak_aborted", {"chamber": self.state.chamber_temp})
                await self.notifier.send("soak_aborted", "Heat soak aborted",
                                         f"Chamber stalled at {round(self.state.chamber_temp or 0)} °C.")
            elif ev == "soak_expired":
                self._fire("soak_expired", {})
        if act.events:
            await self._async_save()

    async def async_ambient_heater_on(self) -> None:
        if heater := self.opts.get(OPT_HEATER):
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": heater})

    def apply_soak_preset(self, key: str) -> None:
        self.settings["soak_preset"] = key
        _label, ch, bed, hold = SOAK_PRESETS.get(key, SOAK_PRESETS["custom"])
        if ch is not None:
            self.settings.update(soak_chamber=ch, soak_bed=bed, soak_hold=hold)

    async def async_set_setting(self, key: str, value: Any) -> None:
        if key == "soak_preset":
            self.apply_soak_preset(value)
        else:
            self.settings[key] = value
            if key in ("soak_chamber", "soak_bed", "soak_hold") and self.settings.get("soak_preset") != "custom":
                self.settings["soak_preset"] = "custom"
        await self._async_save()
        self.async_update_listeners()

    # ================================================================ commands
    async def async_publish(self, payload: dict) -> None:
        """Send a command — local link preferred, cloud as fallback (hybrid)."""
        if self.client and self.local_connected:
            if await self.hass.async_add_executor_job(self.client.publish, payload):
                return
        if self.cloud_client and self.cloud_connected:
            if await self.hass.async_add_executor_job(self.cloud_client.publish, payload):
                return
        raise HomeAssistantError(f"{self.config_entry.title} is not reachable on any link")

    async def async_gcode(self, lines: str | list[str]) -> None:
        await self.async_publish(cmd.gcode(lines))

    def _nozzle_arg(self, nozzle: int | None) -> int | None:
        if not self.state.is_dual or not self.opts[OPT_DUAL_NOZZLE_T]:
            return None
        return self.state.active_nozzle if nozzle is None else nozzle

    async def async_pause(self) -> None:
        await self.async_publish(cmd.pause())

    async def async_resume(self) -> None:
        await self.async_publish(cmd.resume())

    async def async_stop(self) -> None:
        await self.async_publish(cmd.stop())

    async def async_pushall(self) -> None:
        await self.async_publish(cmd.pushall())

    async def _async_update_data(self) -> PrinterState:
        """Called by homeassistant.update_entity — ask the printer for a full push."""
        if self.connected:
            try:
                await self.async_publish(cmd.pushall())
            except HomeAssistantError:
                pass
        return self.data or parse_state(self.raw, self.firmware, self.connected)

    async def async_speed(self, level: int) -> None:
        await self.async_publish(cmd.speed(level))

    async def async_nozzle_temp(self, temp: float, nozzle: int | None = None) -> None:
        await self.async_gcode(cmd.nozzle_temp_lines(int(temp), self._nozzle_arg(nozzle)))

    async def async_bed_temp(self, temp: float) -> None:
        await self.async_gcode(cmd.bed_temp_lines(int(temp)))

    async def async_chamber_temp(self, temp: float) -> None:
        await self.async_gcode(cmd.chamber_temp_lines(int(temp)))

    async def async_fan(self, fan: str, pct: int) -> None:
        await self.async_gcode(cmd.fan_lines(fan, pct))

    async def async_light(self, node: str, on: bool, flashing: bool = False) -> None:
        await self.async_publish(cmd.light(node, on, flashing))

    async def async_home(self) -> None:
        self._require_idle("home")
        await self.async_gcode(["G28"])

    async def async_jog(self, axis: str, distance: float) -> None:
        self._require_idle("jog")
        await self.async_gcode(cmd.jog_lines(axis, distance))

    async def async_motors_off(self) -> None:
        self._require_idle("disable motors")
        await self.async_gcode(["M84"])

    async def async_extrude(self, mm: float, nozzle: int | None = None) -> None:
        n = self.state.nozzle if nozzle is None else next((x for x in self.state.nozzles if x.id == nozzle), None)
        if not n or (n.temp or 0) < 170:
            raise HomeAssistantError("Heat the nozzle above 170 °C before extruding")
        await self.async_gcode(cmd.extrude_lines(mm, nozzle=self._nozzle_arg(nozzle) if nozzle is not None else None))

    async def async_load_tray(self, global_index: int) -> None:
        s = self.state
        tray = next((t for t in s.all_trays if t.global_index == global_index), None)
        tgt = max(int(tray.nozzle_max or 0) if tray else 0, 220)
        cur = int((s.nozzle.temp if s.nozzle else 0) or 0)
        ams_id = tray.ams_id if tray and tray.ams_id != TRAY_EXTERNAL else None
        await self.async_publish(cmd.ams_change(global_index, cur, tgt, ams_id=ams_id, slot_id=tray.tray_id if tray else None))

    async def async_unload(self) -> None:
        cur = int((self.state.nozzle.temp if self.state.nozzle else 0) or 0)
        await self.async_publish(cmd.unload(cur))

    async def async_set_tray(self, ams_id: int, tray_id: int, tray_type: str, color: str,
                             temp_min: int, temp_max: int, info_idx: str = "") -> None:
        await self.async_publish(cmd.ams_filament_setting(ams_id, tray_id, tray_type=tray_type, color=color,
                                                          temp_min=temp_min, temp_max=temp_max, info_idx=info_idx))

    async def async_ams_control(self, action: str) -> None:
        await self.async_publish(cmd.ams_control(action))

    async def async_ams_dry(self, ams_id: int, temp: int, minutes: int) -> None:
        await self.async_publish(cmd.ams_drying(ams_id, temp, minutes))

    async def async_xcam(self, module: str, enable: bool, halt: bool = True, sensitivity: str | None = None) -> None:
        await self.async_publish(cmd.xcam(module, enable, halt, sensitivity))

    async def async_print_option(self, key: str, value: bool) -> None:
        await self.async_publish(cmd.print_option(key, value))

    async def async_camera_record(self, enable: bool) -> None:
        await self.async_publish(cmd.camera_record(enable))

    async def async_camera_timelapse(self, enable: bool) -> None:
        await self.async_publish(cmd.camera_timelapse(enable))

    async def async_calibrate(self, option: int = CAL_BED_LEVEL) -> None:
        self._require_idle("calibrate")
        await self.async_publish(cmd.calibrate(option))

    async def async_skip_objects(self, ids: list[int]) -> None:
        if not self.state.is_active:
            raise HomeAssistantError("No print is running")
        await self.async_publish(cmd.skip_objects(ids))

    async def async_print_file(self, path: str, plate: int | None = None, **opts: Any) -> None:
        self._require_idle("start a print")
        s = self.settings
        await self.async_publish(cmd.project_file(
            path, plate=int(plate or s["print_plate"]), url_prefix=self.opts[OPT_SD_URL_PREFIX],
            use_ams=opts.get("use_ams", s["print_use_ams"]),
            ams_mapping=opts.get("ams_mapping"),
            timelapse=opts.get("timelapse", s["print_timelapse"]),
            bed_leveling=opts.get("bed_leveling", s["print_bed_level"]),
            flow_cali=opts.get("flow_cali", s["print_flow_cali"]),
            vibration_cali=opts.get("vibration_cali", s["print_vibration"]),
            layer_inspect=opts.get("layer_inspect", s["print_layer_inspect"]),
        ))

    async def async_print_selected(self) -> None:
        path = self.settings.get("sd_selected")
        if not path:
            raise HomeAssistantError("No SD-card file selected")
        await self.async_print_file(path)

    def _require_idle(self, what: str) -> None:
        if self.state.is_active:
            raise HomeAssistantError(f"Can't {what} while a print is running")

    # ---- storage
    async def async_refresh_sd(self) -> list[dict[str, Any]]:
        if not self.has_lan:
            return []

        def _ls() -> tuple[list[dict], list[dict]]:
            files = []
            for folder in ("/", "/cache"):
                try:
                    for f in self.ftp.list(folder):
                        if not f["dir"] and f["name"].lower().endswith(".3mf"):
                            files.append({**f, "path": f"{folder.rstrip('/')}/{f['name']}".lstrip("/")})
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("SD list %s failed: %s", folder, err)
            tl = []
            try:
                tl = [f for f in self.ftp.list("/timelapse") if not f["dir"]]
            except Exception:  # noqa: BLE001
                pass
            return files, tl
        self.sd_files, self.sd_timelapses = await self.hass.async_add_executor_job(_ls)
        self.async_update_listeners()
        return self.sd_files

    async def async_upload(self, local_path: str, remote_name: str) -> str:
        remote = "/" + remote_name.lstrip("/")

        def _up() -> None:
            with open(local_path, "rb") as fh:
                self.ftp.upload(fh, remote)
        await self.hass.async_add_executor_job(_up)
        await self.async_refresh_sd()
        return remote.lstrip("/")

    async def async_upload_bytes(self, data: bytes, remote_name: str) -> str:
        remote = "/" + remote_name.lstrip("/")
        await self.hass.async_add_executor_job(self.ftp.upload, io.BytesIO(data), remote)
        await self.async_refresh_sd()
        return remote.lstrip("/")

    async def async_delete_sd(self, path: str) -> None:
        await self.hass.async_add_executor_job(self.ftp.delete, "/" + path.lstrip("/"))
        await self.async_refresh_sd()
