"""Printer report parsing. Pure Python, unit-tested without Home Assistant.

The printer pushes JSON on device/<serial>/report. A `pushall` returns the full
document; afterwards most firmware sends deltas. We keep one merged raw dict and
re-derive a typed PrinterState from it on every message.

Dual-nozzle printers (H2D, X2D) add a `print.device` block whose temperatures are
packed ints: low 16 bits = current, high 16 bits = target. Classic fields are used
as a fallback, so single-nozzle and dual-nozzle firmware both parse.
"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass, field
from typing import Any

from .const import (
    CANCELLED_ERRORS,
    HMS_WIKI,
    HOME_FLAG_BITS,
    SD_BITS_SHIFT,
    SPEED_LEVELS,
    STAGES,
    TRAY_EXTERNAL,
)


# ------------------------------------------------------------------ merging
def deep_merge(base: dict, delta: dict) -> dict:
    """Merge `delta` into `base` in place. Lists of {id: ...} dicts merge by id."""
    for key, val in delta.items():
        cur = base.get(key)
        if isinstance(val, dict) and isinstance(cur, dict):
            deep_merge(cur, val)
        elif (
            isinstance(val, list) and isinstance(cur, list) and val
            and all(isinstance(i, dict) and "id" in i for i in val)
            and all(isinstance(i, dict) and "id" in i for i in cur)
        ):
            index = {str(i["id"]): i for i in cur}
            for item in val:
                existing = index.get(str(item["id"]))
                if existing is not None:
                    deep_merge(existing, item)
                else:
                    cur.append(item)
        else:
            base[key] = val
    return base


# ------------------------------------------------------------------ helpers
def _num(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _int(val: Any, default: int | None = None) -> int | None:
    n = _num(val)
    return default if n is None else int(n)


def unpack_temp(val: Any) -> tuple[float | None, float | None]:
    """Packed dual-nozzle temperature → (current, target)."""
    v = _int(val)
    if v is None:
        return None, None
    cur = v & 0xFFFF
    tgt = (v >> 16) & 0xFFFF
    if cur > 1000:  # not packed after all
        return float(v), None
    return float(cur), float(tgt)


def fan_pct(val: Any) -> int | None:
    """Fan speeds arrive as gear strings 0–15 (sometimes 0–255)."""
    v = _int(val)
    if v is None:
        return None
    if v <= 15:
        return round(v / 15 * 100)
    return round(min(v, 255) / 255 * 100)


def wifi_dbm(val: Any) -> int | None:
    if val is None:
        return None
    return _int(str(val).lower().replace("dbm", "").strip())


def ip_from_int(val: Any) -> str | None:
    v = _int(val)
    if not v:
        return None
    try:
        return socket.inet_ntoa(struct.pack("<I", v & 0xFFFFFFFF))
    except (OSError, struct.error):
        return None


def hms_code(attr: int, code: int) -> str:
    return f"{attr >> 16:04X}_{attr & 0xFFFF:04X}_{code >> 16:04X}_{code & 0xFFFF:04X}"


def hex_color(val: Any) -> str | None:
    if not val or not isinstance(val, str):
        return None
    v = val.strip().lstrip("#").upper()
    return v[:6] if len(v) >= 6 else None


# ------------------------------------------------------------------ dataclasses
@dataclass
class Tray:
    ams_id: int
    tray_id: int
    present: bool = False
    type: str | None = None
    sub_brand: str | None = None
    color: str | None = None          # RRGGBB
    colors: list[str] = field(default_factory=list)
    remain: int | None = None         # % (RFID spools only), None when unknown
    k: float | None = None
    nozzle_min: int | None = None
    nozzle_max: int | None = None
    weight_g: int | None = None
    diameter: float | None = None
    tag_uid: str | None = None
    tray_uuid: str | None = None
    info_idx: str | None = None

    @property
    def global_index(self) -> int:
        if self.ams_id == TRAY_EXTERNAL:
            return TRAY_EXTERNAL
        if self.ams_id >= 128:  # AMS HT units report ids 128+, one slot each
            return self.ams_id
        return self.ams_id * 4 + self.tray_id

    @property
    def key(self) -> str:
        if self.ams_id == TRAY_EXTERNAL:
            return f"external_{self.tray_id + 1}"
        return f"ams{self.ams_id + 1}_tray{self.tray_id + 1}"

    @property
    def label(self) -> str:
        return self.sub_brand or self.type or ("Empty" if not self.present else "Unknown")


@dataclass
class Ams:
    id: int
    humidity_index: int | None = None   # 1 (dry) – 5 (wet)
    humidity_pct: int | None = None
    temp: float | None = None
    dry_remaining_min: int | None = None
    trays: list[Tray] = field(default_factory=list)


@dataclass
class Nozzle:
    id: int
    temp: float | None = None
    target: float | None = None
    diameter: float | None = None
    type: str | None = None


@dataclass
class Hms:
    attr: int
    code: int

    @property
    def full_code(self) -> str:
        return hms_code(self.attr, self.code)

    @property
    def wiki(self) -> str:
        return HMS_WIKI.format(code=self.full_code)

    @property
    def severity(self) -> int:
        return (self.code >> 16) & 0xF


@dataclass
class PrinterState:
    online: bool = False
    gcode_state: str = "unknown"
    stage_id: int = -1
    stage: str = "idle"
    sub_stage: int | None = None
    percent: int = 0
    remaining_min: int | None = None
    layer: int = 0
    total_layers: int = 0
    task_name: str | None = None
    gcode_file: str | None = None
    print_type: str | None = None
    task_id: str | None = None
    subtask_id: str | None = None
    gcode_start_time: int | None = None
    nozzles: list[Nozzle] = field(default_factory=list)
    active_nozzle: int = 0
    bed_temp: float | None = None
    bed_target: float | None = None
    chamber_temp: float | None = None
    chamber_target: float | None = None
    fans: dict[str, int | None] = field(default_factory=dict)
    speed_level: int | None = None
    speed_mag: int | None = None
    lights: dict[str, str] = field(default_factory=dict)
    amss: list[Ams] = field(default_factory=list)
    external: list[Tray] = field(default_factory=list)
    tray_now: int | None = None
    tray_target: int | None = None
    hms: list[Hms] = field(default_factory=list)
    print_error: int = 0
    wifi_dbm: int | None = None
    ip: str | None = None
    sdcard: str | None = None         # none / present / abnormal
    home_flag: int | None = None
    flags: dict[str, bool | None] = field(default_factory=dict)
    door_open: bool | None = None
    xcam: dict[str, Any] = field(default_factory=dict)
    ipcam: dict[str, Any] = field(default_factory=dict)
    skipped_objects: list[int] = field(default_factory=list)
    upgrade: dict[str, Any] = field(default_factory=dict)
    firmware: dict[str, str] = field(default_factory=dict)
    queue_number: int | None = None

    # ---- convenience
    @property
    def is_dual(self) -> bool:
        return len(self.nozzles) > 1

    @property
    def is_active(self) -> bool:
        return self.gcode_state in ("prepare", "running", "pause")

    @property
    def is_printing(self) -> bool:
        return self.gcode_state == "running"

    @property
    def is_cancelled(self) -> bool:
        return self.gcode_state == "failed" and self.print_error in CANCELLED_ERRORS

    @property
    def nozzle(self) -> Nozzle | None:
        if not self.nozzles:
            return None
        for n in self.nozzles:
            if n.id == self.active_nozzle:
                return n
        return self.nozzles[0]

    @property
    def speed_name(self) -> str | None:
        return SPEED_LEVELS.get(self.speed_level or 0)

    @property
    def all_trays(self) -> list[Tray]:
        out = [t for a in self.amss for t in a.trays]
        out.extend(self.external)
        return out

    @property
    def active_tray(self) -> Tray | None:
        if self.tray_now is None or self.tray_now == 255:
            return None
        for t in self.all_trays:
            if t.global_index == self.tray_now:
                return t
        return None

    @property
    def camera_url_reported(self) -> str | None:
        url = self.ipcam.get("rtsp_url")
        if isinstance(url, str) and url.startswith("rtsp"):
            return url
        return None


# ------------------------------------------------------------------ parsing
def _parse_tray(ams_id: int, raw: dict) -> Tray:
    tray_id = _int(raw.get("id"), 0) or 0
    ttype = raw.get("tray_type") or None
    remain = _int(raw.get("remain"))
    return Tray(
        ams_id=ams_id,
        tray_id=tray_id,
        present=bool(ttype),
        type=ttype,
        sub_brand=raw.get("tray_sub_brands") or None,
        color=hex_color(raw.get("tray_color")),
        colors=[c for c in (hex_color(x) for x in raw.get("cols", []) or []) if c],
        remain=remain if remain is not None and remain >= 0 else None,
        k=_num(raw.get("k")),
        nozzle_min=_int(raw.get("nozzle_temp_min")),
        nozzle_max=_int(raw.get("nozzle_temp_max")),
        weight_g=_int(raw.get("tray_weight")),
        diameter=_num(raw.get("tray_diameter")),
        tag_uid=(raw.get("tag_uid") if raw.get("tag_uid") not in ("0000000000000000", "") else None),
        tray_uuid=(raw.get("tray_uuid") if raw.get("tray_uuid") not in ("0" * 32, "") else None),
        info_idx=raw.get("tray_info_idx") or None,
    )


def _parse_ams(p: dict) -> tuple[list[Ams], int | None, int | None]:
    block = p.get("ams") or {}
    units: list[Ams] = []
    for a in block.get("ams", []) or []:
        aid = _int(a.get("id"), 0) or 0
        hum_raw = _int(a.get("humidity_raw"))
        units.append(Ams(
            id=aid,
            humidity_index=_int(a.get("humidity")),
            humidity_pct=hum_raw if hum_raw is not None and 0 <= hum_raw <= 100 else None,
            temp=_num(a.get("temp")),
            dry_remaining_min=_int(a.get("dry_time")),
            trays=[_parse_tray(aid, t) for t in a.get("tray", []) or []],
        ))
    units.sort(key=lambda u: u.id)
    return units, _int(block.get("tray_now")), _int(block.get("tray_tar"))


def _parse_external(p: dict) -> list[Tray]:
    out: list[Tray] = []
    vt = p.get("vt_tray")
    if isinstance(vt, dict):
        t = _parse_tray(TRAY_EXTERNAL, vt)
        t.tray_id = 0
        out.append(t)
    # dual-nozzle firmware: vir_slot list, one per extruder
    for i, vs in enumerate(p.get("vir_slot", []) or []):
        if isinstance(vs, dict):
            t = _parse_tray(TRAY_EXTERNAL, vs)
            t.tray_id = i
            if not any(o.tray_id == i for o in out):
                out.append(t)
    return out


def _parse_nozzles(p: dict) -> tuple[list[Nozzle], int]:
    dev = p.get("device") or {}
    ext = (dev.get("extruder") or {})
    infos = ext.get("info") or []
    noz_meta = {(_int(n.get("id"), 0) or 0): n for n in ((dev.get("nozzle") or {}).get("info") or [])}
    nozzles: list[Nozzle] = []
    for e in infos:
        nid = _int(e.get("id"), 0) or 0
        cur, tgt = unpack_temp(e.get("temp"))
        meta = noz_meta.get(nid, {})
        nozzles.append(Nozzle(
            id=nid, temp=cur, target=tgt,
            diameter=_num(meta.get("diameter")),
            type=meta.get("type") or None,
        ))
    active = 0
    if nozzles:
        state = _int(ext.get("state"))
        if state is not None:
            active = (state >> 4) & 0xF
            if active not in {n.id for n in nozzles}:
                active = nozzles[0].id
        nozzles.sort(key=lambda n: n.id)
        # classic fields describe the active nozzle — use them to fill gaps
        for n in nozzles:
            if n.id == active:
                n.temp = n.temp if n.temp is not None else _num(p.get("nozzle_temper"))
                n.target = n.target if n.target is not None else _num(p.get("nozzle_target_temper"))
                n.diameter = n.diameter or _num(p.get("nozzle_diameter"))
                n.type = n.type or p.get("nozzle_type")
        return nozzles, active
    return [Nozzle(
        id=0,
        temp=_num(p.get("nozzle_temper")),
        target=_num(p.get("nozzle_target_temper")),
        diameter=_num(p.get("nozzle_diameter")),
        type=p.get("nozzle_type") or None,
    )], 0


def parse_state(raw: dict, firmware: dict[str, str] | None = None, online: bool = True) -> PrinterState:
    p: dict = raw.get("print") or {}
    s = PrinterState(online=online, firmware=dict(firmware or {}))

    gs = str(p.get("gcode_state") or "unknown").lower()
    s.gcode_state = gs
    s.stage_id = _int(p.get("stg_cur"), -1)
    s.stage = STAGES.get(s.stage_id, f"stage_{s.stage_id}")
    if gs in ("idle", "finish", "failed") and s.stage_id in (-1, 255, 0):
        s.stage = "idle" if gs == "idle" else gs
    s.sub_stage = _int(p.get("mc_print_sub_stage"))
    s.percent = _int(p.get("mc_percent"), 0) or 0
    s.remaining_min = _int(p.get("mc_remaining_time"))
    s.layer = _int(p.get("layer_num"), 0) or 0
    s.total_layers = _int(p.get("total_layer_num"), 0) or 0
    s.task_name = p.get("subtask_name") or None
    s.gcode_file = p.get("gcode_file") or None
    s.print_type = p.get("print_type") or None
    s.task_id = str(p.get("task_id")) if p.get("task_id") not in (None, "") else None
    s.subtask_id = str(p.get("subtask_id")) if p.get("subtask_id") not in (None, "") else None
    s.gcode_start_time = _int(p.get("gcode_start_time"))
    s.queue_number = _int(p.get("queue_number"))

    s.nozzles, s.active_nozzle = _parse_nozzles(p)

    dev = p.get("device") or {}
    bed_packed = ((dev.get("bed") or {}).get("info") or {}).get("temp")
    if bed_packed is not None:
        s.bed_temp, s.bed_target = unpack_temp(bed_packed)
    if s.bed_temp is None:
        s.bed_temp = _num(p.get("bed_temper"))
    if s.bed_target is None:
        s.bed_target = _num(p.get("bed_target_temper"))

    ctc_packed = ((dev.get("ctc") or {}).get("info") or {}).get("temp")
    if ctc_packed is not None:
        s.chamber_temp, s.chamber_target = unpack_temp(ctc_packed)
    if s.chamber_temp is None:
        s.chamber_temp = _num(p.get("chamber_temper"))

    s.fans = {
        "part": fan_pct(p.get("cooling_fan_speed")),
        "aux": fan_pct(p.get("big_fan1_speed")),
        "chamber": fan_pct(p.get("big_fan2_speed")),
        "heatbreak": fan_pct(p.get("heatbreak_fan_speed")),
    }
    s.speed_level = _int(p.get("spd_lvl"))
    s.speed_mag = _int(p.get("spd_mag"))

    for light in p.get("lights_report", []) or []:
        node = light.get("node")
        if node:
            s.lights[node] = str(light.get("mode", "off"))

    s.amss, s.tray_now, s.tray_target = _parse_ams(p)
    s.external = _parse_external(p)

    s.hms = [Hms(attr=_int(h.get("attr"), 0) or 0, code=_int(h.get("code"), 0) or 0)
             for h in p.get("hms", []) or [] if isinstance(h, dict)]
    s.print_error = _int(p.get("print_error"), 0) or 0

    s.wifi_dbm = wifi_dbm(p.get("wifi_signal"))
    net = (p.get("net") or {}).get("info") or []
    if net and isinstance(net[0], dict):
        s.ip = ip_from_int(net[0].get("ip"))

    hf = _int(p.get("home_flag"))
    s.home_flag = hf
    if hf is not None:
        s.flags = {k: bool((hf >> bit) & 1) for k, bit in HOME_FLAG_BITS.items()}
        s.door_open = s.flags.get("door_open")
        s.sdcard = {0: "none", 1: "present", 2: "abnormal"}.get((hf >> SD_BITS_SHIFT) & 0x3, "unknown")
    if "sdcard" in p and s.sdcard is None:
        s.sdcard = "present" if p.get("sdcard") else "none"

    s.xcam = dict(p.get("xcam") or {})
    s.ipcam = dict(p.get("ipcam") or {})
    s.skipped_objects = [x for x in (_int(o) for o in p.get("s_obj", []) or []) if x is not None]

    up = p.get("upgrade_state") or {}
    newest = None
    for mod in up.get("new_ver_list", []) or []:
        if mod.get("name") == "ota":
            newest = mod.get("new_ver")
    s.upgrade = {
        "new_version": newest or up.get("ota_new_version_number") or None,
        "state": up.get("status"),
        "progress": _int(up.get("progress")),
    }
    return s


def parse_firmware(info: dict) -> dict[str, str]:
    """`info.get_version` reply → {module: version}."""
    out: dict[str, str] = {}
    for mod in info.get("module", []) or []:
        name, ver = mod.get("name"), mod.get("sw_ver")
        if name and ver:
            out[str(name)] = str(ver)
    return out
