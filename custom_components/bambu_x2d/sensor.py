"""Sensors — every data point the printer reports, plus derived metrics."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import X2DConfigEntry
from .const import GCODE_STATES, OPT_AMBIENT_HUM, OPT_AMBIENT_TEMP, OPT_CURRENCY
from .coordinator import X2DCoordinator
from .entity import X2DEntity
from .models import Tray
from .soak import Phase

C = X2DCoordinator
TEMP = dict(device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS, suggested_display_precision=0)
DIAG = EntityCategory.DIAGNOSTIC


@dataclass(frozen=True, kw_only=True)
class X2DSensorDescription(SensorEntityDescription):
    value_fn: Callable[[C], Any]
    attrs_fn: Callable[[C], dict[str, Any]] | None = None
    exists_fn: Callable[[C], bool] = lambda c: True
    always_available: bool = False
    currency: bool = False


def _ts(epoch: float | None) -> datetime | None:
    return datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else None


def _active(c: C) -> bool:
    return c.state.is_active


def _hms_attrs(c: C) -> dict[str, Any]:
    return {"errors": [{"code": h.full_code, "description": c.hms_lookup.describe(h.full_code),
                        "wiki": h.wiki, "severity": h.severity} for h in c.state.hms]}


def _last_job(c: C) -> dict[str, Any]:
    if not c.history:
        return {}
    j = c.history[0]
    return {k: j.get(k) for k in ("result", "duration_s", "weight_g", "filament_cost", "energy_kwh",
                                   "energy_cost", "timelapse", "layers", "error")} | {"ended": _ts(j.get("ended"))}


def _success(c: C) -> int | None:
    ok, bad = c.stats.get("finished", 0), c.stats.get("failed", 0)
    return round(100 * ok / (ok + bad)) if ok + bad else None


def _tray_attrs(t: Tray | None) -> dict[str, Any]:
    if not t:
        return {}
    return {"ams": t.ams_id + 1 if t.ams_id < 128 else t.ams_id, "slot": t.tray_id + 1, "type": t.type,
            "name": t.sub_brand, "color": t.color, "colors": t.colors, "remain": t.remain, "k": t.k,
            "nozzle_temp_min": t.nozzle_min, "nozzle_temp_max": t.nozzle_max, "weight_g": t.weight_g,
            "tag_uid": t.tag_uid, "uuid": t.tray_uuid, "info_idx": t.info_idx, "global_index": t.global_index}


def _has_ambient(c: C) -> bool:
    return bool(c.opts.get(OPT_AMBIENT_TEMP))


SENSORS: tuple[X2DSensorDescription, ...] = (
    # ---------------- job
    X2DSensorDescription(key="print_status", name="Print status", device_class=SensorDeviceClass.ENUM,
                         options=GCODE_STATES, icon="mdi:printer-3d", value_fn=lambda c: c.state.gcode_state),
    X2DSensorDescription(key="stage", name="Stage", icon="mdi:state-machine", value_fn=lambda c: c.state.stage,
                         attrs_fn=lambda c: {"stage_id": c.state.stage_id, "sub_stage": c.state.sub_stage}),
    X2DSensorDescription(key="progress", name="Progress", native_unit_of_measurement=PERCENTAGE,
                         state_class=SensorStateClass.MEASUREMENT, icon="mdi:progress-clock",
                         value_fn=lambda c: c.state.percent),
    X2DSensorDescription(key="remaining_time", name="Remaining time", device_class=SensorDeviceClass.DURATION,
                         native_unit_of_measurement=UnitOfTime.MINUTES, icon="mdi:timer-sand",
                         value_fn=lambda c: c.state.remaining_min if _active(c) else 0),
    X2DSensorDescription(key="end_time", name="End time", device_class=SensorDeviceClass.TIMESTAMP,
                         icon="mdi:clock-end", value_fn=lambda c: c.printer_eta),
    X2DSensorDescription(key="start_time", name="Start time", device_class=SensorDeviceClass.TIMESTAMP,
                         icon="mdi:clock-start", value_fn=lambda c: _ts((c.job or {}).get("started"))),
    X2DSensorDescription(key="elapsed", name="Elapsed", device_class=SensorDeviceClass.DURATION,
                         native_unit_of_measurement=UnitOfTime.MINUTES, icon="mdi:timer-play",
                         value_fn=lambda c: c.elapsed_min),
    X2DSensorDescription(key="current_layer", name="Current layer", icon="mdi:layers-triple",
                         state_class=SensorStateClass.MEASUREMENT, value_fn=lambda c: c.state.layer),
    X2DSensorDescription(key="total_layers", name="Total layers", icon="mdi:layers",
                         value_fn=lambda c: c.state.total_layers),
    X2DSensorDescription(key="layers_remaining", name="Layers remaining", icon="mdi:layers-minus",
                         value_fn=lambda c: c.layers_remaining),
    X2DSensorDescription(key="task_name", name="Task", icon="mdi:file-cad", value_fn=lambda c: c.state.task_name),
    X2DSensorDescription(key="gcode_file", name="G-code file", icon="mdi:file", entity_category=DIAG,
                         value_fn=lambda c: c.state.gcode_file),
    X2DSensorDescription(key="print_type", name="Job source", icon="mdi:source-branch", entity_category=DIAG,
                         value_fn=lambda c: c.state.print_type),
    X2DSensorDescription(key="seconds_per_layer", name="Seconds per layer", native_unit_of_measurement=UnitOfTime.SECONDS,
                         state_class=SensorStateClass.MEASUREMENT, icon="mdi:timer-outline",
                         value_fn=lambda c: c.pace.seconds_per_layer if _active(c) else None),
    X2DSensorDescription(key="layers_per_hour", name="Layers per hour", native_unit_of_measurement="layers/h",
                         state_class=SensorStateClass.MEASUREMENT, icon="mdi:speedometer",
                         value_fn=lambda c: c.pace.layers_per_hour if _active(c) else None),
    X2DSensorDescription(key="smart_eta", name="Pace-based ETA", device_class=SensorDeviceClass.TIMESTAMP,
                         icon="mdi:clock-check", value_fn=lambda c: c.smart_eta),
    X2DSensorDescription(key="eta_drift", name="ETA drift", native_unit_of_measurement=UnitOfTime.MINUTES,
                         icon="mdi:clock-alert", value_fn=lambda c: c.eta_drift_min),
    X2DSensorDescription(key="job_weight", name="Job filament", device_class=SensorDeviceClass.WEIGHT,
                         native_unit_of_measurement=UnitOfMass.GRAMS, icon="mdi:weight-gram",
                         value_fn=lambda c: (c.job or {}).get("weight_g"),
                         attrs_fn=lambda c: {"filaments": (c.job or {}).get("filaments") or [],
                                             "slicer_estimate_s": (c.job or {}).get("prediction_s")}),
    X2DSensorDescription(key="job_filament_cost", name="Job filament cost", device_class=SensorDeviceClass.MONETARY,
                         currency=True, icon="mdi:cash", value_fn=lambda c: c.job_cost["filament"]),
    X2DSensorDescription(key="job_energy", name="Job energy", device_class=SensorDeviceClass.ENERGY,
                         native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, icon="mdi:lightning-bolt",
                         suggested_display_precision=3, value_fn=lambda c: (c.job or {}).get("energy_kwh"),
                         exists_fn=lambda c: True),
    X2DSensorDescription(key="job_energy_cost", name="Job energy cost", device_class=SensorDeviceClass.MONETARY,
                         currency=True, icon="mdi:cash-clock", value_fn=lambda c: c.job_cost["energy"]),
    X2DSensorDescription(key="job_total_cost", name="Job total cost", device_class=SensorDeviceClass.MONETARY,
                         currency=True, icon="mdi:cash-multiple", value_fn=lambda c: c.job_cost["total"]),
    X2DSensorDescription(key="skipped_objects", name="Skipped objects", icon="mdi:cube-off",
                         value_fn=lambda c: len(c.state.skipped_objects),
                         attrs_fn=lambda c: {"ids": c.state.skipped_objects}),
    X2DSensorDescription(key="job_objects", name="Objects on plate", icon="mdi:cube-outline",
                         value_fn=lambda c: len((c.job_meta or {}).get("objects", [])) if c.job_meta else None,
                         attrs_fn=lambda c: {"objects": [{"id": o["id"], "name": o["name"]}
                                                         for o in (c.job_meta or {}).get("objects", [])]}),
    # ---------------- thermals
    X2DSensorDescription(key="nozzle_temp", name="Nozzle temperature", icon="mdi:printer-3d-nozzle-heat", **TEMP,
                         value_fn=lambda c: c.state.nozzle.temp if c.state.nozzle else None),
    X2DSensorDescription(key="nozzle_target", name="Nozzle target", icon="mdi:target", **TEMP,
                         value_fn=lambda c: c.state.nozzle.target if c.state.nozzle else None),
    X2DSensorDescription(key="bed_temp", name="Bed temperature", icon="mdi:radiator", **TEMP,
                         value_fn=lambda c: c.state.bed_temp),
    X2DSensorDescription(key="bed_target", name="Bed target", icon="mdi:target", **TEMP,
                         value_fn=lambda c: c.state.bed_target),
    X2DSensorDescription(key="chamber_temp", name="Chamber temperature", icon="mdi:home-thermometer", **TEMP,
                         value_fn=lambda c: c.state.chamber_temp),
    X2DSensorDescription(key="chamber_target", name="Chamber target", icon="mdi:target", **TEMP,
                         value_fn=lambda c: c.state.chamber_target),
    X2DSensorDescription(key="active_nozzle", name="Active nozzle", icon="mdi:swap-horizontal",
                         exists_fn=lambda c: c.state.is_dual, value_fn=lambda c: c.state.active_nozzle + 1),
    X2DSensorDescription(key="nozzle_diameter", name="Nozzle diameter", native_unit_of_measurement="mm",
                         icon="mdi:diameter", entity_category=DIAG,
                         value_fn=lambda c: c.state.nozzle.diameter if c.state.nozzle else None,
                         attrs_fn=lambda c: {"nozzles": [{"id": n.id + 1, "diameter": n.diameter, "type": n.type}
                                                         for n in c.state.nozzles]}),
    X2DSensorDescription(key="nozzle_type", name="Nozzle type", icon="mdi:diamond-stone", entity_category=DIAG,
                         value_fn=lambda c: c.state.nozzle.type if c.state.nozzle else None),
    X2DSensorDescription(key="heatbreak_fan", name="Heatbreak fan", native_unit_of_measurement=PERCENTAGE,
                         icon="mdi:fan-chevron-up", entity_category=DIAG, value_fn=lambda c: c.state.fans.get("heatbreak")),
    X2DSensorDescription(key="speed_magnitude", name="Speed magnitude", native_unit_of_measurement=PERCENTAGE,
                         icon="mdi:speedometer-medium", value_fn=lambda c: c.state.speed_mag),
    # ---------------- filament
    X2DSensorDescription(key="active_tray", name="Active filament", icon="mdi:spool",
                         value_fn=lambda c: c.state.active_tray.label if c.state.active_tray else None,
                         attrs_fn=lambda c: _tray_attrs(c.state.active_tray) | {"tray_now": c.state.tray_now}),
    # ---------------- diagnostics
    X2DSensorDescription(key="wifi_signal", name="Wi-Fi signal", device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                         native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                         state_class=SensorStateClass.MEASUREMENT, entity_category=DIAG,
                         value_fn=lambda c: c.state.wifi_dbm),
    X2DSensorDescription(key="ip_address", name="IP address", icon="mdi:ip-network", entity_category=DIAG,
                         value_fn=lambda c: c.state.ip or c.host),
    X2DSensorDescription(key="firmware", name="Firmware", icon="mdi:chip", entity_category=DIAG,
                         value_fn=lambda c: c.firmware.get("ota"), attrs_fn=lambda c: {"modules": c.firmware}),
    X2DSensorDescription(key="hms_count", name="HMS errors", icon="mdi:alert-circle",
                         state_class=SensorStateClass.MEASUREMENT, value_fn=lambda c: len(c.state.hms), attrs_fn=_hms_attrs),
    X2DSensorDescription(key="print_error", name="Print error", icon="mdi:alert-octagon", entity_category=DIAG,
                         value_fn=lambda c: f"{c.state.print_error:08X}" if c.state.print_error else "none",
                         attrs_fn=lambda c: {"description": c.hms_lookup.describe_error(c.state.print_error)}),
    X2DSensorDescription(key="last_command", name="Last command", icon="mdi:console", entity_category=DIAG,
                         value_fn=lambda c: (c.last_command or {}).get("result"),
                         attrs_fn=lambda c: dict(c.last_command or {})),
    X2DSensorDescription(key="sd_card", name="Storage", icon="mdi:sd", entity_category=DIAG,
                         value_fn=lambda c: c.state.sdcard,
                         attrs_fn=lambda c: {"print_files": len(c.sd_files), "printer_timelapses": len(c.sd_timelapses)}),
    # ---------------- lifetime
    X2DSensorDescription(key="prints_finished", name="Prints finished", state_class=SensorStateClass.TOTAL_INCREASING,
                         icon="mdi:check-decagram", always_available=True, value_fn=lambda c: c.stats.get("finished", 0)),
    X2DSensorDescription(key="prints_failed", name="Prints failed", state_class=SensorStateClass.TOTAL_INCREASING,
                         icon="mdi:alert-decagram", always_available=True, value_fn=lambda c: c.stats.get("failed", 0)),
    X2DSensorDescription(key="prints_cancelled", name="Prints cancelled", state_class=SensorStateClass.TOTAL_INCREASING,
                         icon="mdi:cancel", always_available=True, value_fn=lambda c: c.stats.get("cancelled", 0)),
    X2DSensorDescription(key="success_rate", name="Success rate", native_unit_of_measurement=PERCENTAGE,
                         icon="mdi:percent", always_available=True, value_fn=_success),
    X2DSensorDescription(key="lifetime_hours", name="Lifetime print time", device_class=SensorDeviceClass.DURATION,
                         native_unit_of_measurement=UnitOfTime.HOURS, state_class=SensorStateClass.TOTAL_INCREASING,
                         suggested_display_precision=1, always_available=True,
                         value_fn=lambda c: round(c.stats.get("print_seconds", 0) / 3600, 2)),
    X2DSensorDescription(key="lifetime_filament", name="Lifetime filament", device_class=SensorDeviceClass.WEIGHT,
                         native_unit_of_measurement=UnitOfMass.GRAMS, state_class=SensorStateClass.TOTAL_INCREASING,
                         always_available=True, icon="mdi:spool",
                         value_fn=lambda c: c.stats.get("filament_g", 0), attrs_fn=lambda c: {"by_type_g": c.stats.get("by_type", {})}),
    X2DSensorDescription(key="lifetime_cost", name="Lifetime cost", device_class=SensorDeviceClass.MONETARY,
                         currency=True, always_available=True, state_class=SensorStateClass.TOTAL,
                         value_fn=lambda c: round(c.stats.get("filament_cost", 0) + c.stats.get("energy_cost", 0), 2)),
    X2DSensorDescription(key="lifetime_energy", name="Lifetime energy", device_class=SensorDeviceClass.ENERGY,
                         native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.TOTAL_INCREASING,
                         always_available=True, value_fn=lambda c: c.stats.get("energy_kwh", 0)),
    X2DSensorDescription(key="last_job", name="Last job", icon="mdi:history", always_available=True,
                         value_fn=lambda c: c.history[0]["name"] if c.history else None, attrs_fn=_last_job),
    # ---------------- environment (only when an ambient sensor is configured)
    X2DSensorDescription(key="ambient_temp", name="Ambient temperature", device_class=SensorDeviceClass.TEMPERATURE,
                         native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT, state_class=SensorStateClass.MEASUREMENT,
                         suggested_display_precision=0, always_available=True, exists_fn=_has_ambient,
                         value_fn=lambda c: c.ambient_f),
    X2DSensorDescription(key="ambient_humidity", name="Ambient humidity", device_class=SensorDeviceClass.HUMIDITY,
                         native_unit_of_measurement=PERCENTAGE, always_available=True,
                         exists_fn=lambda c: bool(c.opts.get(OPT_AMBIENT_HUM)), value_fn=lambda c: c.ambient_rh),
    X2DSensorDescription(key="dew_point", name="Ambient dew point", device_class=SensorDeviceClass.TEMPERATURE,
                         native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT, suggested_display_precision=0,
                         always_available=True, exists_fn=lambda c: bool(c.opts.get(OPT_AMBIENT_HUM)) and _has_ambient(c),
                         value_fn=lambda c: c.dew_point_f),
    X2DSensorDescription(key="startup_margin", name="Startup margin", device_class=SensorDeviceClass.TEMPERATURE,
                         native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT, icon="mdi:thermometer-alert",
                         always_available=True, exists_fn=_has_ambient, value_fn=lambda c: c.startup_margin_f),
    # ---------------- heat soak
    X2DSensorDescription(key="soak_phase", name="Heat soak", device_class=SensorDeviceClass.ENUM,
                         options=[p.value for p in Phase], icon="mdi:radiator", always_available=True,
                         value_fn=lambda c: c.soak.phase.value),
    X2DSensorDescription(key="soak_progress", name="Heat soak progress", native_unit_of_measurement=PERCENTAGE,
                         icon="mdi:progress-clock", always_available=True, value_fn=lambda c: c.soak.progress(c.soak_inputs())),
    X2DSensorDescription(key="soak_remaining", name="Heat soak remaining", native_unit_of_measurement=UnitOfTime.MINUTES,
                         icon="mdi:timer-outline", always_available=True, value_fn=lambda c: round(c.soak_remaining)),
    X2DSensorDescription(key="soak_hold_required", name="Heat soak hold", native_unit_of_measurement=UnitOfTime.MINUTES,
                         icon="mdi:timer-sand", always_available=True, value_fn=lambda c: c.soak_hold_required,
                         attrs_fn=lambda c: {"cold_adder": c.soak_config().cold_adder(c.ambient_f)}),
    X2DSensorDescription(key="soak_held", name="Heat soak held", native_unit_of_measurement=UnitOfTime.MINUTES,
                         icon="mdi:timer-check", always_available=True, value_fn=lambda c: round(c.soak.held_min, 1)),
    X2DSensorDescription(key="soak_ready_at", name="Heat soak ready at", device_class=SensorDeviceClass.TIMESTAMP,
                         icon="mdi:clock-check", always_available=True, value_fn=lambda c: c.soak_ready_at),
    X2DSensorDescription(key="soak_start_at", name="Heat soak starts at", device_class=SensorDeviceClass.TIMESTAMP,
                         icon="mdi:calendar-start", always_available=True,
                         value_fn=lambda c: c.soak_start_at if c.settings.get("soak_armed") else None),
    X2DSensorDescription(key="soak_heat_rate", name="Chamber heat rate", native_unit_of_measurement="°C/min",
                         icon="mdi:chart-line", entity_category=DIAG, always_available=True, value_fn=lambda c: c.soak.rate),
    # ---------------- connection / queue / advisor / maintenance
    X2DSensorDescription(key="connection", name="Connection", device_class=SensorDeviceClass.ENUM,
                         options=["local", "cloud", "both", "offline"], icon="mdi:lan-connect",
                         always_available=True, value_fn=lambda c: c.link,
                         attrs_fn=lambda c: {"mode": c.mode, "lan_host": bool(c.host),
                                             "cloud_linked": bool(c.cloud_cfg.get("token"))}),
    X2DSensorDescription(key="queue", name="Print queue", icon="mdi:tray-full", always_available=True,
                         state_class=SensorStateClass.MEASUREMENT,
                         value_fn=lambda c: len(c.queue),
                         attrs_fn=lambda c: {"jobs": [{"file": q["file"], "plate": q.get("plate")} for q in c.queue],
                                             "auto_continue": bool(c.settings.get("queue_auto"))}),
    X2DSensorDescription(key="advisor", name="Advisor", icon="mdi:lightbulb-on", always_available=True,
                         value_fn=lambda c: len(c.advisor_warnings),
                         attrs_fn=lambda c: {"warnings": c.advisor_warnings}),
    X2DSensorDescription(key="maintenance", name="Maintenance due", icon="mdi:wrench-clock", always_available=True,
                         value_fn=lambda c: sum(1 for m in c.maintenance_status if m["due"]),
                         attrs_fn=lambda c: {"items": c.maintenance_status}),
    X2DSensorDescription(key="abrasive_used", name="Abrasive filament through nozzle",
                         device_class=SensorDeviceClass.WEIGHT, native_unit_of_measurement=UnitOfMass.GRAMS,
                         state_class=SensorStateClass.TOTAL, icon="mdi:grain", always_available=True,
                         entity_category=DIAG, value_fn=lambda c: c.stats.get("abrasive_g", 0.0)),
    # ---------------- timelapse
    X2DSensorDescription(key="timelapse_clips", name="Timelapse clips", icon="mdi:movie-open", always_available=True,
                         value_fn=lambda c: len(c.timelapse.library),
                         attrs_fn=lambda c: {"total_mb": c.timelapse.total_mb, "last": c.timelapse.last_clip,
                                             "rendering": c.timelapse.rendering}),
    X2DSensorDescription(key="timelapse_frames", name="Timelapse frames", icon="mdi:filmstrip", always_available=True,
                         value_fn=lambda c: c.timelapse.frame_count if c.timelapse.job else 0),
)


def _ams_sensors(c: C, ams_id: int) -> list[X2DSensorDescription]:
    n = ams_id + 1 if ams_id < 128 else ams_id
    label = f"AMS {n}" if ams_id < 128 else f"AMS HT {ams_id - 127}"

    def unit(fn):
        return lambda co: next((fn(a) for a in co.state.amss if a.id == ams_id), None)

    return [
        X2DSensorDescription(key=f"ams{n}_humidity_index", name=f"{label} humidity index", icon="mdi:water-percent",
                             state_class=SensorStateClass.MEASUREMENT, value_fn=unit(lambda a: a.humidity_index)),
        X2DSensorDescription(key=f"ams{n}_humidity", name=f"{label} humidity", device_class=SensorDeviceClass.HUMIDITY,
                             native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT,
                             value_fn=unit(lambda a: a.humidity_pct)),
        X2DSensorDescription(key=f"ams{n}_temp", name=f"{label} temperature", **TEMP, value_fn=unit(lambda a: a.temp)),
        X2DSensorDescription(key=f"ams{n}_drying", name=f"{label} drying remaining", icon="mdi:heat-wave",
                             native_unit_of_measurement=UnitOfTime.MINUTES, value_fn=unit(lambda a: a.dry_remaining_min)),
    ]


def _tray_sensor(t: Tray) -> X2DSensorDescription:
    key, ams_id, tray_id = t.key, t.ams_id, t.tray_id

    def find(c: C) -> Tray | None:
        return next((x for x in c.state.all_trays if x.ams_id == ams_id and x.tray_id == tray_id), None)

    name = (f"External spool {tray_id + 1}" if ams_id == 254
            else f"AMS {ams_id + 1} tray {tray_id + 1}" if ams_id < 128 else f"AMS HT {ams_id - 127}")
    return X2DSensorDescription(
        key=key, name=name, icon="mdi:spool",
        value_fn=lambda c: (find(c).label if find(c) else None),
        attrs_fn=lambda c: _tray_attrs(find(c)) | {"active": bool(find(c) and c.state.tray_now == find(c).global_index)},
    )


def _nozzle_sensors(nid: int) -> list[X2DSensorDescription]:
    def n(c: C):
        return next((x for x in c.state.nozzles if x.id == nid), None)
    return [
        X2DSensorDescription(key=f"nozzle{nid + 1}_temp", name=f"Nozzle {nid + 1} temperature", **TEMP,
                             icon="mdi:printer-3d-nozzle-heat", value_fn=lambda c: n(c).temp if n(c) else None),
        X2DSensorDescription(key=f"nozzle{nid + 1}_target", name=f"Nozzle {nid + 1} target", **TEMP,
                             icon="mdi:target", value_fn=lambda c: n(c).target if n(c) else None),
    ]


class X2DSensor(X2DEntity, SensorEntity):
    entity_description: X2DSensorDescription
    # big/volatile attribute payloads stay out of the recorder database
    _unrecorded_attributes = frozenset({"errors", "filaments", "objects", "modules", "colors",
                                        "by_type_g", "ids", "jobs", "warnings", "items"})

    def __init__(self, coord: C, desc: X2DSensorDescription) -> None:
        super().__init__(coord, desc.key, always_available=desc.always_available)
        self.entity_description = desc
        if desc.currency:
            self._attr_native_unit_of_measurement = coord.opts.get(OPT_CURRENCY, "USD")

    @property
    def native_value(self) -> Any:
        try:
            return self.entity_description.value_fn(self.coordinator)
        except (AttributeError, KeyError, TypeError, ValueError, IndexError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        if not fn:
            return None
        try:
            return fn(self.coordinator)
        except (AttributeError, KeyError, TypeError, ValueError, IndexError):
            return None


async def async_setup_entry(hass: HomeAssistant, entry: X2DConfigEntry, add: AddEntitiesCallback) -> None:
    coord = entry.runtime_data
    known: set[str] = set()

    def build() -> list[X2DSensor]:
        descs = [d for d in SENSORS if d.exists_fn(coord)]
        if coord.state.is_dual:
            for n in coord.state.nozzles:
                descs += _nozzle_sensors(n.id)
        for ams in coord.state.amss:
            descs += _ams_sensors(coord, ams.id)
        for tray in coord.state.all_trays:
            descs.append(_tray_sensor(tray))
        new = [X2DSensor(coord, d) for d in descs if d.key not in known]
        known.update(e.key for e in new)
        return new

    add(build())
    sig: list = []

    @callback
    def _check_new() -> None:  # AMS units / external spools / second nozzle added later
        new_sig = [coord.state.is_dual, len(coord.state.nozzles),
                   tuple(a.id for a in coord.state.amss), tuple(t.key for t in coord.state.all_trays)]
        if new_sig != sig[:]:
            sig[:] = new_sig
            if fresh := build():
                add(fresh)

    _check_new()
    entry.async_on_unload(coord.async_add_listener(_check_new))
