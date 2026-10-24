"""Maintenance tracker + advisor tests."""

import conftest  # noqa: F401

from bambu_x2d import maintenance as maint
from bambu_x2d.advisor import AdvisorInputs, evaluate


def test_maintenance_due():
    items = maint.status(print_hours=320.0, done={"lube_rails": 0.0, "bed_wash": 300.0},
                         abrasive_g=500, nozzle_type="stainless_steel")
    by_key = {i["key"]: i for i in items}
    assert by_key["lube_rails"]["due"] is True
    assert by_key["clean_rods"]["due"] is True          # never done, 320 h > 250 h
    assert by_key["bed_wash"]["due"] is False and by_key["bed_wash"]["since_h"] == 20.0
    noz = by_key["nozzle_wear"]
    assert noz["pct"] == 50 and noz["due"] is False
    nxt = maint.next_due(items)
    assert nxt["due"] and nxt["due_in_h"] == -70.0       # most overdue first


def test_maintenance_hardened_budget():
    items = maint.status(10, {}, abrasive_g=500, nozzle_type="hardened_steel")
    noz = next(i for i in items if i["key"] == "nozzle_wear")
    assert noz["pct"] == round(100 * 500 / 8000)


def _keys(ws):
    return {w["key"] for w in ws}


def test_advisor_abrasive_nozzle():
    ws = evaluate(AdvisorInputs(printing=True, job_filament_types=["PLA-CF"],
                                nozzle_type="stainless_steel", nozzle_diameter=0.4))
    assert any(k.startswith("abrasive_") for k in _keys(ws))
    ws = evaluate(AdvisorInputs(printing=True, job_filament_types=["PLA-CF"],
                                nozzle_type="hardened_steel", nozzle_diameter=0.4))
    assert not any(k.startswith("abrasive_") for k in _keys(ws))


def test_advisor_cold_chamber_for_abs():
    ws = evaluate(AdvisorInputs(printing=True, job_filament_types=["ABS"], chamber_c=25))
    assert any(k.startswith("chamber_") for k in _keys(ws))


def test_advisor_pla_hot_chamber():
    ws = evaluate(AdvisorInputs(printing=True, job_filament_types=["PLA"], chamber_c=45))
    assert "pla_hot_chamber" in _keys(ws)


def test_advisor_pairings():
    ws = evaluate(AdvisorInputs(printing=True, job_filament_types=["PLA", "ABS"], chamber_c=50))
    assert "pair_risky" in _keys(ws)
    ws = evaluate(AdvisorInputs(printing=True, job_filament_types=["PLA", "PETG"]))
    assert "pair_support" in _keys(ws)


def test_advisor_humidity():
    loaded = [{"type": "PETG", "name": None, "info_idx": None, "remain": 80}]
    ws = evaluate(AdvisorInputs(loaded=loaded, ams_humidity=[(0, 5)]))
    assert "humidity" in _keys(ws)
    ws = evaluate(AdvisorInputs(loaded=loaded, ams_humidity=[(0, 2)]))
    assert "humidity" not in _keys(ws)


def test_advisor_too_cold_and_order():
    ws = evaluate(AdvisorInputs(printing=False, ambient_f=42, min_start_f=50,
                                job_filament_types=["PLA-CF"], nozzle_type="stainless_steel"))
    keys = [w["key"] for w in ws]
    assert "too_cold" in keys
    assert keys[0].startswith("abrasive_")  # alerts sort first
