"""3mf parser tests against a synthetic Bambu-style archive."""
import io
import json
import zipfile

import conftest  # noqa: F401

from bambu_x2d.threemf import parse_3mf

SLICE_INFO = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <plate>
    <metadata key="index" value="1"/>
    <metadata key="prediction" value="5820"/>
    <metadata key="weight" value="38.42"/>
    <metadata key="nozzle_diameters" value="0.4"/>
    <object identify_id="409" name="guard_left" skipped="false"/>
    <object identify_id="411" name="guard_right" skipped="false"/>
    <filament id="1" type="PETG" color="#1D9E75" used_m="12.4" used_g="37.1" tray_info_idx="GFG00"/>
    <filament id="2" type="PETG" color="#2C2C2A" used_m="0.4" used_g="1.3" tray_info_idx="GFG00"/>
  </plate>
</config>"""

PLATE_JSON = {
    "bed_type": "textured_plate",
    "bbox_objects": [
        {"id": 409, "name": "guard_left", "bbox": [40.0, 60.0, 120.0, 140.0]},
        {"id": 411, "name": "guard_right", "bbox": [140.0, 60.0, 220.0, 140.0]},
    ],
}


def make_3mf() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Metadata/plate_1.gcode", "G28\n")
        z.writestr("Metadata/plate_1.png", b"\x89PNG-fake")
        z.writestr("Metadata/plate_1.json", json.dumps(PLATE_JSON))
        z.writestr("Metadata/slice_info.config", SLICE_INFO)
    return buf.getvalue()


def test_parse():
    meta = parse_3mf(make_3mf())
    assert meta["plate"] == 1
    assert meta["cover"] == b"\x89PNG-fake"
    assert meta["prediction_s"] == 5820
    assert meta["weight_g"] == 38.42
    assert meta["bed_type"] == "textured_plate"
    assert [o["id"] for o in meta["objects"]] == [409, 411]
    assert meta["objects"][0]["bbox"] == [40.0, 60.0, 120.0, 140.0]
    assert meta["filaments"][0]["color"] == "1D9E75"
    assert meta["filaments"][0]["used_g"] == 37.1


def test_weight_fallback():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Metadata/plate_1.gcode", "")
        z.writestr("Metadata/slice_info.config",
                   SLICE_INFO.replace('<metadata key="weight" value="38.42"/>', ""))
    meta = parse_3mf(buf.getvalue())
    assert meta["weight_g"] == 38.4
