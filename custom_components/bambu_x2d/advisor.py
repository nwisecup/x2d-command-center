"""The advisor: cross-references live printer state with the filament database.

Pure function over plain inputs so it's unit-testable. Severity:
  info < tip < warn < alert
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import filament_db as fdb


@dataclass
class AdvisorInputs:
    printing: bool = False
    job_filament_types: list[str] = field(default_factory=list)
    loaded: list[dict[str, Any]] = field(default_factory=list)   # [{type, name, info_idx, tray, remain}]
    nozzle_type: str | None = None
    nozzle_diameter: float | None = None
    chamber_c: float | None = None
    ams_humidity: list[tuple[int, int | None]] = field(default_factory=list)  # (ams_id, index 1-5)
    ambient_f: float | None = None
    min_start_f: float = 50.0
    door_open: bool | None = None
    active_type: str | None = None


def _w(severity: str, key: str, title: str, detail: str, action: str | None = None) -> dict[str, Any]:
    return {"severity": severity, "key": key, "title": title, "detail": detail, "action": action}


def evaluate(inp: AdvisorInputs) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    job_recs = [(t, fdb.lookup(t)) for t in inp.job_filament_types]

    # --- nozzle vs abrasive / temps / diameter
    for t, rec in job_recs:
        if rec is None:
            continue
        if rec["abrasive"] and inp.nozzle_type == "stainless_steel":
            out.append(_w("alert", f"abrasive_{t}",
                          f"{rec['label']} with a stainless nozzle",
                          "Carbon/glass-filled filament sands stainless nozzles out of round within "
                          "~1 kg. Swap to the hardened nozzle before long prints.",
                          "Swap nozzle, then mark nozzle wear done in Insights"))
        if rec["min_nozzle"] and inp.nozzle_diameter and inp.nozzle_diameter < rec["min_nozzle"]:
            out.append(_w("alert", f"nozzle_dia_{t}",
                          f"{rec['label']} needs ≥{rec['min_nozzle']} mm nozzle",
                          f"The {inp.nozzle_diameter} mm nozzle will clog on filled filament.", None))
        chamber_opt = rec.get("chamber")
        if inp.printing and chamber_opt and inp.chamber_c is not None and inp.chamber_c < chamber_opt - 10:
            out.append(_w("warn", f"chamber_{t}",
                          f"Chamber {inp.chamber_c:.0f} °C is cold for {rec['label']}",
                          f"{rec['label']} wants ~{chamber_opt} °C to avoid layer splits and warping. "
                          "Run a heat soak before starting next time.",
                          "Use the Soak tab before the next start"))
        if rec["family"] == "PLA" and inp.printing and inp.chamber_c is not None and inp.chamber_c > 38:
            out.append(_w("tip", "pla_hot_chamber",
                          f"Chamber {inp.chamber_c:.0f} °C is warm for PLA",
                          "PLA softens in a warm chamber → heat-creep clogs on long prints. "
                          "Open the door/glass or run the exhaust fan.", "Open door or raise exhaust fan"))

    # --- multi-material pairing
    if len({(fdb.lookup(t) or {}).get("family", t) for t in inp.job_filament_types}) > 1:
        verdict = fdb.classify_pairing(inp.job_filament_types)
        if verdict:
            if verdict["kind"] == "risky":
                worst = next((p for p in verdict["pairs"] if p["level"] == 0), verdict["pairs"][0])
                out.append(_w("alert", "pair_risky", f"Incompatible materials: {worst['pair']}",
                              worst["note"], None))
            elif verdict["kind"] == "support-interface":
                out.append(_w("info", "pair_support", "Break-away support pairing detected",
                              "These materials barely bond — perfect when one is the support interface. "
                              "If you expected a welded two-material part, pick a bonding pair instead.", None))
            elif verdict["kind"] == "soluble-support":
                out.append(_w("info", "pair_soluble", "Soluble support job",
                              "Dissolve supports fully before flexing the part; warm water speeds PVA.", None))

    # --- moisture
    hygro_loaded = []
    for tr in inp.loaded:
        rec = fdb.lookup(tr.get("name") or tr.get("type"), tr.get("info_idx"))
        if rec and rec["hygro"] >= 4:
            hygro_loaded.append((tr, rec))
    wet_ams = [aid for aid, idx in inp.ams_humidity if idx is not None and idx >= 4]
    if wet_ams and hygro_loaded:
        names = ", ".join(sorted({r["label"] for _, r in hygro_loaded}))
        specs = {f"{r['label']}: {r['dry'][0]} °C {r['dry'][1]} h" for _, r in hygro_loaded if r.get("dry")}
        out.append(_w("warn", "humidity",
                      f"AMS is humid with {names} loaded",
                      "Wet filament = stringing, popping, weak layers. Drying specs — " + "; ".join(sorted(specs)),
                      "Tap a tray in Filament → Dry now (AMS 2 Pro)"))

    # --- cold start
    if inp.ambient_f is not None and inp.ambient_f < inp.min_start_f and not inp.printing:
        out.append(_w("warn", "too_cold",
                      f"Room is {inp.ambient_f:.0f} °F — below your {inp.min_start_f:.0f} °F floor",
                      "Electronics and bed adhesion suffer on cold starts. Warm the room or run a heat "
                      "soak with the room-heater option before printing.",
                      "Soak tab → Start soak"))

    # --- door during high-temp print
    if inp.printing and inp.door_open and inp.active_type:
        rec = fdb.lookup(inp.active_type)
        if rec and rec.get("chamber"):
            out.append(_w("warn", "door_open", "Door open mid-print",
                          f"{rec['label']} needs a stable warm chamber — drafts cause layer splits.", "Close the door"))

    # --- low filament for the active job
    for tr in inp.loaded:
        remain = tr.get("remain")
        if inp.printing and tr.get("active") and remain is not None and remain < 15:
            out.append(_w("tip", "low_filament", f"Active spool at {remain} %",
                          "AMS auto-switches to a matching backup spool if one is loaded — load one now "
                          "or expect a runout pause.", "Load a matching spool in another slot"))

    order = {"alert": 0, "warn": 1, "tip": 2, "info": 3}
    out.sort(key=lambda w: order.get(w["severity"], 9))
    return out
