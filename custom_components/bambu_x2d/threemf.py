"""Read what we need from a sliced .3mf: cover image, objects (+ bed footprint), filament use.

Pure Python. Bambu-sliced 3mf files carry:
  Metadata/plate_N.png       cover thumbnail
  Metadata/plate_N.json      bbox_objects: per-object footprint on the bed (mm)
  Metadata/slice_info.config XML: objects (identify_id/name/skipped), filament use, prediction, weight
"""
from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any


def _plates(names: list[str]) -> list[int]:
    out = set()
    for n in names:
        m = re.match(r"Metadata/plate_(\d+)\.(gcode|png|json)$", n)
        if m:
            out.add(int(m.group(1)))
    return sorted(out)


def _meta(el: ET.Element, key: str) -> str | None:
    for m in el.findall("metadata"):
        if m.get("key") == key:
            return m.get("value")
    return None


def _num(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def parse_3mf(data: bytes, plate: int | None = None) -> dict[str, Any]:
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    plates = _plates(names)
    gcode_plates = sorted(
        int(m.group(1)) for n in names if (m := re.match(r"Metadata/plate_(\d+)\.gcode$", n))
    )
    if plate is None:
        plate = (gcode_plates or plates or [1])[0]

    out: dict[str, Any] = {
        "plate": plate, "plates": plates, "cover": None, "objects": [], "filaments": [],
        "prediction_s": None, "weight_g": None, "bed_type": None, "nozzle_diameter": None,
    }

    cover_name = f"Metadata/plate_{plate}.png"
    if cover_name in names:
        out["cover"] = z.read(cover_name)

    # objects from slice_info
    objects: dict[str, dict] = {}
    if "Metadata/slice_info.config" in names:
        root = ET.fromstring(z.read("Metadata/slice_info.config"))
        for pl in root.iter("plate"):
            idx = _meta(pl, "index")
            if idx is not None and int(idx) != plate:
                continue
            out["prediction_s"] = int(_num(_meta(pl, "prediction"))) or None
            out["weight_g"] = round(_num(_meta(pl, "weight")), 2) or None
            out["nozzle_diameter"] = _num(_meta(pl, "nozzle_diameters"), 0) or None
            for o in pl.findall("object"):
                oid = o.get("identify_id")
                if oid is None:
                    continue
                objects[oid] = {
                    "id": int(oid), "name": o.get("name") or f"Object {oid}",
                    "skipped": (o.get("skipped") or "false").lower() == "true", "bbox": None,
                }
            for f in pl.findall("filament"):
                out["filaments"].append({
                    "id": int(_num(f.get("id"), 0)),
                    "type": f.get("type"),
                    "color": (f.get("color") or "").lstrip("#").upper()[:6] or None,
                    "used_m": round(_num(f.get("used_m")), 2),
                    "used_g": round(_num(f.get("used_g")), 2),
                    "tray_info_idx": f.get("tray_info_idx"),
                })
            break

    # footprints from plate_N.json
    pj = f"Metadata/plate_{plate}.json"
    if pj in names:
        try:
            meta = json.loads(z.read(pj))
        except ValueError:
            meta = {}
        out["bed_type"] = meta.get("bed_type")
        unmatched = []
        for b in meta.get("bbox_objects", []) or []:
            bbox = b.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            key = str(b.get("id")) if b.get("id") is not None else None
            if key and key in objects:
                objects[key]["bbox"] = [round(_num(v), 2) for v in bbox]
            else:
                unmatched.append((b.get("name"), bbox))
        for name, bbox in unmatched:  # fall back to matching by name
            for o in objects.values():
                if o["bbox"] is None and o["name"] == name:
                    o["bbox"] = [round(_num(v), 2) for v in bbox]
                    break

    out["objects"] = sorted(objects.values(), key=lambda o: o["id"])
    if out["weight_g"] is None and out["filaments"]:
        out["weight_g"] = round(sum(f["used_g"] for f in out["filaments"]), 2)
    return out
