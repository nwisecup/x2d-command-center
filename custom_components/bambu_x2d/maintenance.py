"""Maintenance tracking. Pure Python — intervals from community/Bambu guidance.

Hours are PRINT hours (from lifetime stats), not wall-clock. `done` maps
item key → print-hours total when last serviced. Abrasive grams tracked
separately drive nozzle inspection.
"""
from __future__ import annotations

from typing import Any

ITEMS: list[dict[str, Any]] = [
    {"key": "lube_rails", "label": "Lubricate X/Y rails & lead screws", "interval_h": 300,
     "desc": "Wipe old grease off the rails and Z lead screws, re-apply a thin film "
             "(Bambu supplies the grease). Squeaks or ringing in walls = overdue."},
    {"key": "clean_rods", "label": "Wipe motion rods / belts check", "interval_h": 250,
     "desc": "Dry-wipe the motion rods, check belt tension by ear (pluck test) and "
             "look for debris in the belt teeth."},
    {"key": "nozzle_inspect", "label": "Inspect nozzle & silicone sock", "interval_h": 250,
     "desc": "Check the tip for wear/ooze and the sock for tears. A worn nozzle shows "
             "as inconsistent extrusion width and poor first layers."},
    {"key": "extruder_clean", "label": "Clean extruder gears", "interval_h": 500,
     "desc": "Pop the toolhead cover, brush filament dust out of the drive gears — "
             "dust buildup causes slipping and under-extrusion."},
    {"key": "fans_dust", "label": "Dust fans & vents", "interval_h": 400,
     "desc": "Blow out the part fan, aux fan and MC board vents. A garage printer "
             "collects dust fast; hot electronics die young."},
    {"key": "filter_replace", "label": "Replace carbon filter", "interval_h": 300,
     "desc": "Swap the activated-carbon exhaust media — it saturates silently. "
             "Essential when printing ABS/ASA in an attached garage."},
    {"key": "ams_path", "label": "AMS feed path & desiccant", "interval_h": 350,
     "desc": "Check the PTFE tubes for grooves, blow out filament dust in the AMS, "
             "recharge/replace desiccant."},
    {"key": "bed_wash", "label": "Wash build plate", "interval_h": 50,
     "desc": "Warm water + dish soap, dry with a lint-free cloth. Fingerprint oils are "
             "the #1 cause of first-layer adhesion failures."},
]

# Nozzle wear budget by abrasive filament throughput (grams of CF/GF-filled material)
ABRASIVE_BUDGET_G = {"stainless_steel": 1000, "hardened_steel": 8000}


def status(print_hours: float, done: dict[str, float], abrasive_g: float = 0.0,
           nozzle_type: str | None = None) -> list[dict[str, Any]]:
    out = []
    for item in ITEMS:
        last = float(done.get(item["key"], 0.0))
        since = max(print_hours - last, 0.0)
        due_in = item["interval_h"] - since
        out.append({
            **{k: item[k] for k in ("key", "label", "interval_h", "desc")},
            "since_h": round(since, 1),
            "due_in_h": round(due_in, 1),
            "due": due_in <= 0,
            "pct": min(round(100 * since / item["interval_h"]), 100),
        })
    if nozzle_type:
        budget = ABRASIVE_BUDGET_G.get(nozzle_type, 2000)
        pct = min(round(100 * abrasive_g / budget), 100)
        out.append({
            "key": "nozzle_wear", "label": f"Nozzle wear ({nozzle_type.replace('_', ' ')})",
            "interval_h": None, "since_h": round(abrasive_g, 0), "due_in_h": round(budget - abrasive_g, 0),
            "due": abrasive_g >= budget, "pct": pct,
            "desc": f"~{abrasive_g:.0f} g of abrasive (CF/GF) filament through this nozzle; "
                    f"budget ≈ {budget} g for {nozzle_type.replace('_', ' ')}. Mark done after replacing.",
        })
    out.sort(key=lambda i: i["due_in_h"] if i["due_in_h"] is not None else 0)
    return out


def next_due(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    pending = [i for i in items if i["due_in_h"] is not None]
    return min(pending, key=lambda i: i["due_in_h"]) if pending else None
