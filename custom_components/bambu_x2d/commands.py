"""Command payload builders. Pure Python — every printer command lives here.

All of these go to device/<serial>/request over the printer's local MQTT broker.
Controls require Developer Mode on current firmware; read-only data does not.
"""
from __future__ import annotations

import itertools
from typing import Any

from .const import CAL_BED_LEVEL, TRAY_UNLOAD

_seq = itertools.count(1)


def seq() -> str:
    return str(next(_seq) % 1_000_000)


def _print(command: str, **extra: Any) -> dict:
    return {"print": {"sequence_id": seq(), "command": command, **extra}}


# ---- status
def pushall() -> dict:
    return {"pushing": {"sequence_id": seq(), "command": "pushall", "version": 1, "push_target": 1}}


def get_version() -> dict:
    return {"info": {"sequence_id": seq(), "command": "get_version"}}


# ---- job control
def pause() -> dict:
    return _print("pause")


def resume() -> dict:
    return _print("resume")


def stop() -> dict:
    return _print("stop")


def speed(level: int) -> dict:
    return _print("print_speed", param=str(int(level)))


def skip_objects(ids: list[int]) -> dict:
    return _print("skip_objects", obj_list=[int(i) for i in ids])


def project_file(
    filename: str,
    *,
    plate: int = 1,
    url_prefix: str = "file:///sdcard/",
    use_ams: bool = True,
    ams_mapping: list[int] | None = None,
    timelapse: bool = False,
    bed_leveling: bool = True,
    flow_cali: bool = False,
    vibration_cali: bool = False,
    layer_inspect: bool = True,
    bed_type: str = "auto",
) -> dict:
    name = filename.lstrip("/")
    subtask = name.rsplit("/", 1)[-1]
    for suffix in (".gcode.3mf", ".3mf"):
        if subtask.lower().endswith(suffix):
            subtask = subtask[: -len(suffix)]
            break
    payload = _print(
        "project_file",
        param=f"Metadata/plate_{int(plate)}.gcode",
        url=f"{url_prefix}{name}",
        subtask_name=subtask,
        use_ams=use_ams,
        timelapse=timelapse,
        bed_leveling=bed_leveling,
        flow_cali=flow_cali,
        vibration_cali=vibration_cali,
        layer_inspect=layer_inspect,
        bed_type=bed_type,
        profile_id="0", project_id="0", subtask_id="0", task_id="0",
    )
    if ams_mapping:
        payload["print"]["ams_mapping"] = list(ams_mapping)
    return payload


# ---- G-code
def gcode(lines: str | list[str]) -> dict:
    text = "\n".join(lines) if isinstance(lines, list) else str(lines).replace("\\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return _print("gcode_line", param=text)


def jog_lines(axis: str, distance: float, feed: int | None = None) -> list[str]:
    axis = axis.upper()
    if axis not in ("X", "Y", "Z"):
        raise ValueError("axis must be X, Y or Z")
    feed = feed or (600 if axis == "Z" else 3000)
    # Same soft-endstop-aware sequence Bambu Studio sends.
    return [
        "M211 S", "M211 X1 Y1 Z1", "M1002 push_ref_mode", "G91",
        f"G1 {axis}{distance:g} F{feed}", "M1002 pop_ref_mode", "M211 R",
    ]


def extrude_lines(mm: float, feed: int = 300, nozzle: int | None = None) -> list[str]:
    lines = [f"T{nozzle}"] if nozzle is not None else []
    return lines + ["M83", f"G0 E{mm:g} F{feed}"]


def nozzle_temp_lines(temp: int, nozzle: int | None = None) -> list[str]:
    if nozzle is None:
        return [f"M104 S{int(temp)}"]
    return [f"M104 T{int(nozzle)} S{int(temp)}"]


def bed_temp_lines(temp: int) -> list[str]:
    return [f"M140 S{int(temp)}"]


def chamber_temp_lines(temp: int) -> list[str]:
    return [f"M141 S{int(temp)}"]


FAN_INDEX = {"part": 1, "aux": 2, "chamber": 3}


def fan_lines(fan: str, percent: int) -> list[str]:
    return [f"M106 P{FAN_INDEX[fan]} S{round(max(0, min(100, percent)) * 2.55)}"]


# ---- lights / camera
def light(node: str, on: bool, flashing: bool = False) -> dict:
    mode = "flashing" if flashing else ("on" if on else "off")
    return {"system": {
        "sequence_id": seq(), "command": "ledctrl", "led_node": node, "led_mode": mode,
        "led_on_time": 500, "led_off_time": 500, "loop_times": 0, "interval_time": 0,
    }}


def camera_record(enable: bool) -> dict:
    return {"camera": {"sequence_id": seq(), "command": "ipcam_record_set",
                       "control": "enable" if enable else "disable"}}


def camera_timelapse(enable: bool) -> dict:
    return {"camera": {"sequence_id": seq(), "command": "ipcam_timelapse",
                       "control": "enable" if enable else "disable"}}


# ---- AI / options
def xcam(module: str, enable: bool, halt: bool = True, sensitivity: str | None = None) -> dict:
    body: dict[str, Any] = {
        "sequence_id": seq(), "command": "xcam_control_set", "module_name": module,
        "control": enable, "enable": enable, "print_halt": halt,
    }
    if sensitivity:
        body["halt_print_sensitivity"] = sensitivity
    return {"xcam": body}


def print_option(key: str, value: bool) -> dict:
    return _print("print_option", **{key: bool(value)})


def calibrate(option: int = CAL_BED_LEVEL) -> dict:
    return _print("calibration", option=int(option))


# ---- AMS
def ams_change(target: int, curr_temp: int, tar_temp: int, *, ams_id: int | None = None,
               slot_id: int | None = None) -> dict:
    extra: dict[str, Any] = {"target": int(target), "curr_temp": int(curr_temp), "tar_temp": int(tar_temp)}
    if ams_id is not None and slot_id is not None:  # newer dual-nozzle firmware
        extra.update(ams_id=int(ams_id), slot_id=int(slot_id))
    return _print("ams_change_filament", **extra)


def unload(curr_temp: int, tar_temp: int = 220) -> dict:
    return ams_change(TRAY_UNLOAD, curr_temp, tar_temp)


def ams_filament_setting(ams_id: int, tray_id: int, *, tray_type: str, color: str,
                         temp_min: int, temp_max: int, info_idx: str = "") -> dict:
    col = color.lstrip("#").upper()
    if len(col) == 6:
        col += "FF"
    return _print(
        "ams_filament_setting", ams_id=int(ams_id), tray_id=int(tray_id),
        tray_info_idx=info_idx, tray_color=col, nozzle_temp_min=int(temp_min),
        nozzle_temp_max=int(temp_max), tray_type=tray_type,
    )


def ams_control(action: str) -> dict:
    """action: resume | reset | pause."""
    return _print("ams_control", param=action)


def ams_drying(ams_id: int, temp: int, minutes: int) -> dict:
    """AMS 2 Pro / AMS HT drying. Community-documented; verify on your firmware."""
    return _print("ams_filament_drying", ams_id=int(ams_id), temp=int(temp),
                  duration=int(minutes), mode=1 if minutes > 0 else 0)
