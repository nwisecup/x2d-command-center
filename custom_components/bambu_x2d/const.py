"""Constants for X2D Command Center. Pure Python — no Home Assistant imports."""
from __future__ import annotations

DOMAIN = "bambu_x2d"
NAME = "X2D Command Center"
VERSION = "0.2.1"
MANUFACTURER = "Bambu Lab"

MQTT_PORT = 8883
FTP_PORT = 990
RTSP_PORT = 322
SSDP_LISTEN_PORT = 2021
SSDP_SEARCH_PORT = 1990
MQTT_USER = "bblp"

# ---- config entry data ----
CONF_SERIAL = "serial"
CONF_ACCESS_CODE = "access_code"
CONF_MODEL = "model"
CONF_HOST = "host"
CONF_NAME = "name"
CONF_MODE = "mode"                  # lan | hybrid | cloud
CONF_CLOUD = "cloud"                # {email, uid, token, region}

MODE_LAN = "lan"
MODE_HYBRID = "hybrid"
MODE_CLOUD = "cloud"
MODES = [MODE_LAN, MODE_HYBRID, MODE_CLOUD]

# ---- options (everything user-specific lives here, not in code) ----
OPT_AMBIENT_TEMP = "ambient_temp_entity"
OPT_AMBIENT_HUM = "ambient_humidity_entity"
OPT_MIN_START_F = "min_start_temp_f"
OPT_HEATER = "heater_entity"
OPT_POWER = "power_entity"
OPT_ENERGY_PRICE = "energy_price_kwh"
OPT_FILAMENT_PRICE = "filament_price_kg"
OPT_FILAMENT_PRICES = "filament_prices"
OPT_CURRENCY = "currency"
OPT_NOTIFY = "notify_services"
OPT_NOTIFY_EVENTS = "notify_events"
OPT_TL_ENABLED = "timelapse_enabled"
OPT_TL_FPS = "timelapse_fps"
OPT_TL_WIDTH = "timelapse_width"
OPT_TL_KEEP_FRAMES = "timelapse_keep_frames"
OPT_TL_RETENTION = "timelapse_retention"
OPT_SOAK_BAND = "soak_band_c"
OPT_SOAK_MAX_HEAT = "soak_max_heat_min"
OPT_SOAK_KEEP_WARM = "soak_keep_warm_min"
OPT_SOAK_COLD_REF_F = "soak_cold_ref_f"
OPT_SOAK_COLD_PER_F = "soak_cold_min_per_f"
OPT_SOAK_COLD_MAX = "soak_cold_max_min"
OPT_HMS_LOOKUP = "hms_lookup"
OPT_SD_URL_PREFIX = "sd_url_prefix"
OPT_CAMERA_URL = "camera_url_override"
OPT_DUAL_NOZZLE_T = "dual_nozzle_t_prefix"

DEFAULT_OPTIONS: dict = {
    OPT_MIN_START_F: 50.0,
    OPT_ENERGY_PRICE: 0.14,
    OPT_FILAMENT_PRICE: 22.0,
    OPT_FILAMENT_PRICES: "",
    OPT_CURRENCY: "USD",
    OPT_NOTIFY: [],
    OPT_NOTIFY_EVENTS: ["finished", "failed", "hms_error", "soak_ready", "too_cold", "filament_runout"],
    OPT_TL_ENABLED: True,
    OPT_TL_FPS: 30,
    OPT_TL_WIDTH: 1280,
    OPT_TL_KEEP_FRAMES: False,
    OPT_TL_RETENTION: 100,
    OPT_SOAK_BAND: 3.0,
    OPT_SOAK_MAX_HEAT: 60,
    OPT_SOAK_KEEP_WARM: 45,
    OPT_SOAK_COLD_REF_F: 65.0,
    OPT_SOAK_COLD_PER_F: 0.5,
    OPT_SOAK_COLD_MAX: 20,
    OPT_HMS_LOOKUP: True,
    OPT_SD_URL_PREFIX: "file:///sdcard/",
    OPT_CAMERA_URL: "",
    OPT_DUAL_NOZZLE_T: True,
}

NOTIFY_EVENT_CHOICES = [
    "started", "paused", "finished", "failed", "cancelled", "hms_error",
    "filament_runout", "milestone", "soak_ready", "soak_aborted", "too_cold",
    "timelapse_ready", "first_layer", "queue", "advisor", "maintenance",
]

# ---- printer protocol vocab ----
GCODE_STATES = ["idle", "prepare", "running", "pause", "finish", "failed", "slicing", "unknown"]
ACTIVE_STATES = {"prepare", "running", "pause"}

SPEED_LEVELS = {1: "silent", 2: "standard", 3: "sport", 4: "ludicrous"}
SPEED_BY_NAME = {v: k for k, v in SPEED_LEVELS.items()}

# stg_cur → slug. Unknown ids render as "stage_<n>".
STAGES = {
    -1: "idle", 255: "idle", 0: "printing", 1: "auto_bed_leveling",
    2: "heatbed_preheating", 3: "sweeping_xy_mech_mode", 4: "changing_filament",
    5: "m400_pause", 6: "paused_filament_runout", 7: "heating_hotend",
    8: "calibrating_extrusion", 9: "scanning_bed_surface", 10: "inspecting_first_layer",
    11: "identifying_build_plate_type", 12: "calibrating_micro_lidar", 13: "homing_toolhead",
    14: "cleaning_nozzle_tip", 15: "checking_extruder_temperature", 16: "paused_user",
    17: "paused_front_cover_falling", 18: "calibrating_micro_lidar", 19: "calibrating_extrusion_flow",
    20: "paused_nozzle_temperature_malfunction", 21: "paused_heat_bed_temperature_malfunction",
    22: "filament_unloading", 23: "paused_skipped_step", 24: "filament_loading",
    25: "calibrating_motor_noise", 26: "paused_ams_lost", 27: "paused_low_fan_speed_heat_break",
    28: "paused_chamber_temperature_control_error", 29: "cooling_chamber",
    30: "paused_user_gcode", 31: "motor_noise_showoff", 32: "paused_nozzle_filament_covered_detected",
    33: "paused_cutter_error", 34: "paused_first_layer_error", 35: "paused_nozzle_clog",
    36: "check_absolute_accuracy_before_calibration", 37: "absolute_accuracy_calibration",
    38: "check_absolute_accuracy_after_calibration", 39: "calibrate_nozzle_offset",
    40: "bed_level_high_temperature", 41: "check_quick_release", 42: "check_door_and_cover",
    43: "laser_calibration", 44: "check_plaser_marker", 45: "check_raised_height",
    46: "check_material", 47: "live_view_camera_calibration", 48: "waiting_for_heatbed_temperature",
    49: "check_material_position", 50: "cutting_module_offset_calibration",
    51: "measuring_surface", 52: "thermal_preconditioning",
}
RUNOUT_STAGES = {6}

# print_error values that mean "user cancelled", not a failure
CANCELLED_ERRORS = {50348044, 50364436}

# xcam AI modules (name → label)
XCAM_MODULES = {
    "printing_monitor": "AI print monitoring",
    "spaghetti_detector": "Spaghetti detection",
    "first_layer_inspector": "First-layer inspection",
    "buildplate_marker_detector": "Build-plate marker check",
}
HALT_SENSITIVITIES = ["low", "medium", "high"]

# home_flag bit positions (X1/H2 family, community-documented — verify on X2D).
HOME_FLAG_BITS = {
    "auto_recovery": 4,
    "sound_enable": 17,
    "filament_tangle_detect": 20,
    "door_open": 23,
}
SD_BITS_SHIFT = 8  # (home_flag >> 8) & 0x3 → 0 none, 1 present, 2 abnormal

# print_option keys we can set
PRINT_OPTIONS = {
    "auto_recovery": "Auto-recover from step loss",
    "sound_enable": "Printer sounds",
    "filament_tangle_detect": "Filament tangle detection",
    "air_print_detect": "Air-printing detection",
    "nozzle_blob_detect": "Nozzle blob detection",
}

# calibration bitmask — Bambu Studio's mapping (bit0 lidar, bit1 bed, bit2 vibration, bit3 motor noise).
CAL_LIDAR = 0x01
CAL_BED_LEVEL = 0x02
CAL_VIBRATION = 0x04
CAL_MOTOR_NOISE = 0x08
CAL_NOZZLE_OFFSET = 0x10  # dual-nozzle only; verify on X2D

# AMS tray special targets for ams_change_filament
TRAY_EXTERNAL = 254
TRAY_UNLOAD = 255

# Heat-soak presets: (chamber °C, bed °C, base hold min)
SOAK_PRESETS = {
    "pla": ("PLA", 28, 55, 10),
    "petg": ("PETG", 35, 70, 15),
    "abs_asa": ("ABS / ASA", 60, 100, 25),
    "pc": ("PC", 65, 110, 30),
    "pa": ("PA / Nylon", 60, 100, 30),
    "custom": ("Custom", None, None, None),
}

EVENT_TYPES = [
    "print_started", "print_paused", "print_resumed", "print_finished",
    "print_failed", "print_cancelled", "hms_error", "filament_runout",
    "milestone", "soak_ready", "soak_aborted", "soak_expired",
    "timelapse_ready", "too_cold", "first_layer", "queue_next",
    "advisor_warning", "maintenance_due",
]

HMS_WIKI = "https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/{code}"
HMS_LOOKUP_URL = "https://e.bambulab.com/query.php?lang=en"

STORE_VERSION = 1
HISTORY_LIMIT = 300
QUEUE_LIMIT = 30
PUSHALL_INTERVAL_S = 300
SOAK_TICK_S = 15
ENERGY_TICK_S = 30
SD_REFRESH_S = 900
FIRST_LAYER_CHECK_LAYER = 3
