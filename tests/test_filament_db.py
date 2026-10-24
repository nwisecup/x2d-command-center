"""Filament database integrity + lookup + bonding tests."""

import conftest  # noqa: F401

from bambu_x2d import filament_db as fdb

REQUIRED = {"label", "family", "aliases", "info_idx", "nozzle", "bed", "chamber", "enclosure",
            "cooling", "max_vol_speed", "density", "tensile_mpa", "flex_mod_mpa", "impact_kjm2",
            "hdt_c", "shore", "hygro", "dry", "ams", "abrasive", "hardened", "min_nozzle",
            "plate", "glue", "warp", "use_cases", "notes"}


def test_schema_complete():
    assert len(fdb.M) >= 15
    for key, rec in fdb.M.items():
        missing = REQUIRED - set(rec)
        assert not missing, f"{key} missing {missing}"
        lo, hi = rec["nozzle"]
        assert 150 < lo < hi <= 320, key
        blo, bhi = rec["bed"]
        assert 20 <= blo <= bhi <= 120, key
        assert rec["ams"] in ("yes", "ht_only", "external"), key
        assert 1 <= rec["hygro"] <= 5 and 1 <= rec["warp"] <= 5, key
        assert rec["enclosure"] in ("open", "recommended", "required"), key
        if rec["dry"] is not None:
            dt, dh = rec["dry"]
            assert 40 <= dt <= 90 and 1 <= dh <= 24, key
        if rec["abrasive"]:
            assert rec["hardened"], f"{key}: abrasive implies hardened nozzle"


def test_aliases_unique():
    seen = {}
    for key, rec in fdb.M.items():
        for a in rec["aliases"]:
            assert a == a.lower(), f"{key}: alias '{a}' must be lowercase"
            assert a not in seen, f"alias '{a}' in both {seen.get(a)} and {key}"
            seen[a] = key


def test_lookup():
    assert fdb.lookup("PETG")["label"] == "PETG"
    assert fdb.lookup("Bambu PLA Matte")["label"] == "PLA Matte"
    assert fdb.lookup("pla-cf")["label"] == "PLA-CF"
    assert fdb.lookup(None, "GFA00")["label"] == "PLA"
    assert fdb.lookup("whatever", "GFN04")["label"] == "PAHT-CF"
    assert fdb.lookup("ASA")["family"] == "ABS"
    assert fdb.lookup("TPU 95A HF")["label"] == "TPU 95A"
    assert fdb.lookup("totally unknown stuff") is None


def test_compatibility():
    same = fdb.compatibility("PLA", "pla matte")
    assert same["level"] == 4
    weak = fdb.compatibility("PLA", "PETG")
    assert weak["level"] == 1 and "support" in weak["note"].lower()
    assert fdb.compatibility("PETG", "TPU")["level"] == 3
    assert fdb.compatibility("PLA", "ABS")["level"] == 0
    assert fdb.compatibility("ABS", "HIPS")["level"] == 3
    # symmetric
    assert fdb.compatibility("TPU", "PETG") == fdb.compatibility("PETG", "TPU")
    # unknown pairing is honest
    assert fdb.compatibility("PC", "TPU")["verdict"] == "unknown"


def test_classify_pairing():
    v = fdb.classify_pairing(["PLA", "PETG"])
    assert v["kind"] == "support-interface"
    v = fdb.classify_pairing(["PLA", "PVA"])
    assert v["kind"] == "soluble-support"
    v = fdb.classify_pairing(["PETG", "TPU"])
    assert v["kind"] == "laminate"
    v = fdb.classify_pairing(["PLA", "ABS"])
    assert v["kind"] == "risky"
    assert fdb.classify_pairing(["PLA", "PLA Matte"]) is None  # same family
    assert fdb.classify_pairing(["PLA"]) is None


def test_abrasive_and_dry():
    assert fdb.abrasive("PLA-CF") is True
    assert fdb.abrasive("PLA") is False
    assert fdb.abrasive("Mystery Glow in the dark") is True  # heuristic
    assert fdb.dry_spec("PA") == (80, 12)
    assert fdb.dry_spec("nope nothing") is None


def test_export_serializable():
    import json
    out = fdb.export()
    json.dumps(out)
    assert out["version"] >= 1 and len(out["pairs"]) >= 10
