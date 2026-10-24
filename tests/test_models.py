"""Tests for the pure protocol layer — no Home Assistant required."""

import conftest  # noqa: F401

from bambu_x2d import commands as cmd
from bambu_x2d.derived import PaceTracker, dew_point_c, filament_cost, parse_price_map
from bambu_x2d.discovery import parse_announcement
from bambu_x2d.models import deep_merge, fan_pct, hms_code, parse_state, unpack_temp

FULL = {
    "print": {
        "command": "push_status",
        "gcode_state": "RUNNING", "stg_cur": 0, "mc_percent": 63, "mc_remaining_time": 47,
        "layer_num": 182, "total_layer_num": 288, "subtask_name": "blade_guard_v3",
        "gcode_file": "/data/Metadata/plate_1.gcode", "print_type": "local", "spd_lvl": 2, "spd_mag": 100,
        "nozzle_temper": 220.4, "nozzle_target_temper": 220, "nozzle_diameter": "0.4", "nozzle_type": "stainless_steel",
        "bed_temper": 55.1, "bed_target_temper": 55, "chamber_temper": 41,
        "cooling_fan_speed": "15", "big_fan1_speed": "10", "big_fan2_speed": "5", "heatbreak_fan_speed": "15",
        "wifi_signal": "-58dBm", "home_flag": (1 << 4) | (1 << 17) | (1 << 8),
        "lights_report": [{"node": "chamber_light", "mode": "on"}],
        "hms": [{"attr": 50331904, "code": 131073}],
        "print_error": 0,
        "ams": {"tray_now": "1", "tray_tar": "1", "ams": [{
            "id": "0", "humidity": "2", "humidity_raw": "31", "temp": "28.1",
            "tray": [
                {"id": "0", "tray_type": "PLA", "tray_color": "1D9E75FF", "remain": 62,
                 "tray_sub_brands": "PLA Matte", "nozzle_temp_min": "190", "nozzle_temp_max": "230"},
                {"id": "1", "tray_type": "PETG", "tray_color": "D85A30FF", "remain": -1},
                {"id": "2", "tray_type": "", "remain": 0},
                {"id": "3", "tray_type": "ABS", "tray_color": "2C2C2AFF", "remain": 88},
            ]}]},
        "vt_tray": {"id": "254", "tray_type": "TPU", "tray_color": "F1EFE8FF"},
        "xcam": {"spaghetti_detector": True, "first_layer_inspector": True, "halt_print_sensitivity": "medium"},
        "ipcam": {"ipcam_record": "enable", "rtsp_url": "rtsps://192.168.1.50/streaming/live/1", "timelapse": "disable"},
        "upgrade_state": {"new_ver_list": [{"name": "ota", "new_ver": "01.01.02.00"}]},
        "s_obj": [409],
        "device": {
            "extruder": {"state": 1, "info": [
                {"id": 0, "temp": (220 << 16) | 221},
                {"id": 1, "temp": (0 << 16) | 35},
            ]},
            "nozzle": {"info": [{"id": 0, "diameter": 0.4, "type": "stainless_steel"},
                                 {"id": 1, "diameter": 0.4, "type": "hardened_steel"}]},
            "bed": {"info": {"temp": (55 << 16) | 55}},
            "ctc": {"info": {"temp": (60 << 16) | 41}},
        },
    }
}


def test_parse_full():
    s = parse_state(FULL)
    assert s.gcode_state == "running"
    assert s.is_printing and s.is_active
    assert s.percent == 63 and s.layer == 182 and s.total_layers == 288
    assert s.stage == "printing"
    assert s.task_name == "blade_guard_v3"
    assert s.speed_name == "standard"
    assert s.bed_temp == 55 and s.bed_target == 55
    assert s.chamber_temp == 41 and s.chamber_target == 60
    assert s.fans == {"part": 100, "aux": 67, "chamber": 33, "heatbreak": 100}
    assert s.wifi_dbm == -58
    assert s.lights["chamber_light"] == "on"
    assert s.flags["auto_recovery"] is True and s.flags["sound_enable"] is True
    assert s.sdcard == "present"
    assert s.skipped_objects == [409]
    assert s.upgrade["new_version"] == "01.01.02.00"


def test_dual_nozzle():
    s = parse_state(FULL)
    assert s.is_dual and len(s.nozzles) == 2
    assert s.active_nozzle == 0
    assert s.nozzle.temp == 221 and s.nozzle.target == 220
    n1 = next(n for n in s.nozzles if n.id == 1)
    assert n1.temp == 35 and n1.target == 0
    assert n1.type == "hardened_steel"


def test_single_nozzle_fallback():
    raw = {"print": {k: v for k, v in FULL["print"].items() if k != "device"}}
    s = parse_state(raw)
    assert not s.is_dual
    assert s.nozzle.temp == 220.4 and s.nozzle.target == 220
    assert s.bed_temp == 55.1
    assert s.chamber_temp == 41 and s.chamber_target is None


def test_trays():
    s = parse_state(FULL)
    assert len(s.amss) == 1
    ams = s.amss[0]
    assert ams.humidity_index == 2 and ams.humidity_pct == 31
    trays = ams.trays
    assert trays[0].label == "PLA Matte" and trays[0].remain == 62 and trays[0].color == "1D9E75"
    assert trays[1].remain is None  # -1 → unknown
    assert not trays[2].present
    assert s.external[0].type == "TPU" and s.external[0].global_index == 254
    active = s.active_tray
    assert active is not None and active.tray_id == 1 and active.type == "PETG"


def test_hms():
    s = parse_state(FULL)
    assert s.hms[0].full_code == hms_code(50331904, 131073) == "0300_0100_0002_0001"
    assert "0300_0100_0002_0001" in s.hms[0].wiki


def test_deep_merge_delta():
    import copy
    raw = {}
    deep_merge(raw.setdefault("print", {}), copy.deepcopy(FULL["print"]))
    deep_merge(raw["print"], {"mc_percent": 64, "layer_num": 183,
                              "ams": {"ams": [{"id": "0", "tray": [{"id": "0", "remain": 61}]}]}})
    s = parse_state(raw)
    assert s.percent == 64 and s.layer == 183
    assert s.amss[0].trays[0].remain == 61
    assert s.amss[0].trays[0].type == "PLA"          # survived the delta
    assert s.amss[0].trays[3].type == "ABS"


def test_cancelled_detection():
    raw = {"print": {"gcode_state": "FAILED", "print_error": 50348044}}
    assert parse_state(raw).is_cancelled


def test_unpack_and_fans():
    assert unpack_temp((60 << 16) | 41) == (41, 60)
    assert unpack_temp(None) == (None, None)
    assert fan_pct("15") == 100 and fan_pct("0") == 0 and fan_pct(None) is None
    assert fan_pct(255) == 100


def test_commands():
    p = cmd.pause()
    assert p["print"]["command"] == "pause"
    g = cmd.gcode("M104 S220\\nM140 S60")
    assert g["print"]["param"] == "M104 S220\nM140 S60\n"
    jog = cmd.jog_lines("z", -10)
    assert "G1 Z-10 F600" in jog and jog[0] == "M211 S"
    pf = cmd.project_file("cache/bracket.gcode.3mf", plate=2)["print"]
    assert pf["url"] == "file:///sdcard/cache/bracket.gcode.3mf"
    assert pf["param"] == "Metadata/plate_2.gcode"
    assert pf["subtask_name"] == "bracket"
    assert cmd.nozzle_temp_lines(220, 1) == ["M104 T1 S220"]
    assert cmd.fan_lines("aux", 40) == ["M106 P2 S102"]
    assert cmd.fan_lines("part", 100) == ["M106 P1 S255"]
    st = cmd.ams_filament_setting(0, 2, tray_type="PETG", color="1D9E75", temp_min=220, temp_max=260)["print"]
    assert st["tray_color"] == "1D9E75FF" and st["tray_id"] == 2


def test_pace_tracker():
    p = PaceTracker()
    t = 1000.0
    for i in range(1, 8):
        p.on_layer(t + i * 30, i)
    assert p.seconds_per_layer == 30
    assert p.layers_per_hour == 120
    assert p.eta_seconds(10) == 300
    p.on_layer(t + 9 * 30, 1)   # new print → reset
    assert p.seconds_per_layer is None


def test_derived():
    assert round(dew_point_c(20, 50), 1) == 9.3
    assert dew_point_c(None, 50) is None
    prices = parse_price_map("PLA=18, PETG=22.5; ABS=20")
    assert prices == {"PLA": 18.0, "PETG": 22.5, "ABS": 20.0}
    cost = filament_cost([{"type": "PLA-CF", "used_g": 100}, {"type": "XYZ", "used_g": 50}], 30.0, prices)
    assert cost == round(0.1 * 18 + 0.05 * 30, 2)


def test_discovery_parse():
    data = (b"NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:2021\r\n"
            b"NT: urn:bambulab-com:device:3dprinter:1\r\nUSN: 0409AC1234567890\r\n"
            b"Location: 192.168.1.50\r\nDevModel.bambu.com: X2D\r\n"
            b"DevName.bambu.com: Garage X2D\r\nDevConnect.bambu.com: lan\r\n\r\n")
    dev = parse_announcement(data, "192.168.1.50")
    assert dev == {"serial": "0409AC1234567890", "host": "192.168.1.50", "name": "Garage X2D",
                   "model": "X2D", "connect": "lan", "bind": None, "version": None}
    assert parse_announcement(b"NOTIFY * HTTP/1.1\r\nNT: upnp:rootdevice\r\n\r\n", "1.2.3.4") is None
