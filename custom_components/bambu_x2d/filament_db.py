"""Local filament science database. Pure Python.

Typical published values (Bambu spec sheets and common industry data), rounded.
Mechanical numbers are indicative — batch, color and print settings move them.

Every record:
  label           display name
  family          bonding/advice family (PLA, PETG, ABS, ASA, PC, PA, TPU, PVA, HIPS, SUPPORT, PE/PP exotic)
  aliases         strings matched case-insensitively against tray_type / slicer names
  info_idx        known Bambu filament profile ids (prefix match)
  nozzle          (min, max) °C
  bed             (min, max) °C
  chamber         recommended chamber °C or None (prefers open/cool)
  enclosure       open | recommended | required
  cooling         (min, max) part-fan %
  max_vol_speed   mm³/s — realistic ceiling for speed estimates
  density         g/cm³
  tensile_mpa     tensile strength
  flex_mod_mpa    flexural modulus (stiffness)
  impact_kjm2     notched impact (toughness)
  hdt_c           heat deflection °C (0.45 MPa)
  shore           hardness for flexibles (e.g. "95A")
  hygro           1 dry-tolerant … 5 extremely hygroscopic
  dry             (temp °C, hours) or None
  ams             yes | ht_only | external  (AMS 2 Pro / AMS HT / external spool only)
  abrasive        wears brass/stainless nozzles
  hardened        hardened nozzle required
  min_nozzle      minimum nozzle diameter mm
  plate           recommended build plates
  glue            adhesive advice
  warp            1 flat … 5 severe
  use_cases       what people actually print with it
  notes           the thing everyone learns the hard way
"""
from __future__ import annotations

from typing import Any

DB_VERSION = 1

M: dict[str, dict[str, Any]] = {
    "pla": dict(
        label="PLA", family="PLA", aliases=["pla", "pla basic", "pla+", "pla plus"],
        info_idx=["GFA00", "GFA03", "GFL0", "GFL99"],
        nozzle=(190, 230), bed=(45, 65), chamber=None, enclosure="open", cooling=(80, 100),
        max_vol_speed=21, density=1.24, tensile_mpa=35, flex_mod_mpa=2600, impact_kjm2=27,
        hdt_c=57, shore=None, hygro=2, dry=(50, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.2, plate=["Textured PEI", "Cool Plate"], glue="none needed",
        warp=1, use_cases=["prototypes", "toys", "visual models", "jigs that stay indoors"],
        notes="Easiest material there is, but softens in a hot car (~55 °C). Keep the chamber "
              "door open or chamber <30 °C on long prints or heat creep causes clogs.",
    ),
    "pla_matte": dict(
        label="PLA Matte", family="PLA", aliases=["pla matte", "matte pla"], info_idx=["GFA01"],
        nozzle=(190, 230), bed=(45, 65), chamber=None, enclosure="open", cooling=(80, 100),
        max_vol_speed=22, density=1.31, tensile_mpa=32, flex_mod_mpa=2400, impact_kjm2=23,
        hdt_c=57, shore=None, hygro=2, dry=(50, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.2, plate=["Textured PEI"], glue="none needed", warp=1,
        use_cases=["display pieces", "props", "anything photographed"],
        notes="Hides layer lines beautifully; slightly more brittle than basic PLA.",
    ),
    "pla_silk": dict(
        label="PLA Silk", family="PLA", aliases=["silk", "pla silk", "silk+"], info_idx=["GFA05", "GFA06"],
        nozzle=(210, 230), bed=(45, 65), chamber=None, enclosure="open", cooling=(70, 100),
        max_vol_speed=12, density=1.26, tensile_mpa=28, flex_mod_mpa=2200, impact_kjm2=18,
        hdt_c=55, shore=None, hygro=2, dry=(50, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none needed", warp=1,
        use_cases=["vases", "ornaments", "gifts"],
        notes="Print SLOW for the shine — the gloss comes from slow, hot extrusion. Weak layer bonding.",
    ),
    "pla_cf": dict(
        label="PLA-CF", family="PLA", aliases=["pla-cf", "pla cf", "pla carbon"], info_idx=["GFA50"],
        nozzle=(210, 240), bed=(45, 65), chamber=None, enclosure="open", cooling=(60, 90),
        max_vol_speed=16, density=1.22, tensile_mpa=40, flex_mod_mpa=4800, impact_kjm2=18,
        hdt_c=58, shore=None, hygro=3, dry=(55, 8), ams="yes", abrasive=True, hardened=True,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none needed", warp=1,
        use_cases=["stiff brackets", "drone parts", "matte structural look"],
        notes="Stiff, gorgeous matte finish, dead easy — but it eats stainless nozzles. "
              "Hardened nozzle only, 0.4 mm or larger.",
    ),
    "petg": dict(
        label="PETG", family="PETG", aliases=["petg", "petg basic", "pet-g", "petg hf"],
        info_idx=["GFG00", "GFG02", "GFL01"],
        nozzle=(230, 260), bed=(65, 80), chamber=None, enclosure="open", cooling=(30, 70),
        max_vol_speed=16, density=1.27, tensile_mpa=32, flex_mod_mpa=1600, impact_kjm2=30,
        hdt_c=69, shore=None, hygro=4, dry=(65, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.2, plate=["Textured PEI"], glue="glue stick as RELEASE on smooth PEI (bonds too hard)",
        warp=2, use_cases=["outdoor parts", "brackets", "anything touching water", "garage/trailer fixtures"],
        notes="The workhorse for functional parts: tough, UV-tolerant, slightly flexible. Strings when "
              "wet — dry it. Never print PETG on smooth PEI without glue: it welds and rips the sheet.",
    ),
    "petg_cf": dict(
        label="PETG-CF", family="PETG", aliases=["petg-cf", "petg cf"], info_idx=["GFG50"],
        nozzle=(240, 270), bed=(65, 80), chamber=None, enclosure="open", cooling=(20, 60),
        max_vol_speed=13, density=1.29, tensile_mpa=40, flex_mod_mpa=3600, impact_kjm2=22,
        hdt_c=74, shore=None, hygro=4, dry=(65, 10), ams="yes", abrasive=True, hardened=True,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none needed", warp=1,
        use_cases=["stiff outdoor brackets", "mounts", "fixtures"],
        notes="PETG toughness with CF stiffness and near-zero warp. Hardened nozzle required.",
    ),
    "abs": dict(
        label="ABS", family="ABS", aliases=["abs"], info_idx=["GFB00", "GFL02"],
        nozzle=(240, 280), bed=(90, 100), chamber=55, enclosure="required", cooling=(0, 30),
        max_vol_speed=16, density=1.04, tensile_mpa=38, flex_mod_mpa=1900, impact_kjm2=35,
        hdt_c=87, shore=None, hygro=3, dry=(70, 6), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.2, plate=["Textured PEI", "Smooth PEI + glue"], glue="thin glue layer helps release",
        warp=4, use_cases=["automotive-adjacent parts", "enclosures", "acetone-smoothed pieces", "clip-fit parts"],
        notes="Needs a hot, still chamber — this is what your heat soak is for. Ventilate: styrene fumes. "
              "Acetone vapor smoothing gives injection-molded looks.",
    ),
    "asa": dict(
        label="ASA", family="ABS", aliases=["asa"], info_idx=["GFB01"],
        nozzle=(240, 280), bed=(90, 100), chamber=55, enclosure="required", cooling=(0, 30),
        max_vol_speed=14, density=1.05, tensile_mpa=40, flex_mod_mpa=2000, impact_kjm2=33,
        hdt_c=93, shore=None, hygro=3, dry=(70, 6), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.2, plate=["Textured PEI"], glue="thin glue layer helps release", warp=4,
        use_cases=["anything living outdoors", "vehicle exterior", "garden fixtures", "trailer hardware"],
        notes="ABS's outdoor-proof sibling: real UV stability. Same chamber/heat-soak needs as ABS. "
              "For a mobile-business fleet, exterior mounts should be ASA, not PLA/PETG.",
    ),
    "pc": dict(
        label="PC", family="PC", aliases=["pc", "polycarbonate", "pc fr"], info_idx=["GFC00", "GFC01"],
        nozzle=(260, 290), bed=(100, 110), chamber=60, enclosure="required", cooling=(0, 20),
        max_vol_speed=12, density=1.19, tensile_mpa=60, flex_mod_mpa=2300, impact_kjm2=30,
        hdt_c=117, shore=None, hygro=4, dry=(80, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Smooth PEI + glue", "Textured PEI"], glue="glue stick required for release",
        warp=5, use_cases=["under-hood parts", "high-heat jigs", "load-bearing brackets"],
        notes="Strongest common filament, takes 110+ °C service temps. Maximum chamber, maximum soak, "
              "bone-dry filament or it's brittle foam.",
    ),
    "pa": dict(
        label="PA (Nylon)", family="PA", aliases=["pa", "nylon", "pa6", "pa12", "pa6-gf"], info_idx=["GFN"],
        nozzle=(260, 290), bed=(80, 100), chamber=60, enclosure="required", cooling=(0, 30),
        max_vol_speed=12, density=1.12, tensile_mpa=55, flex_mod_mpa=1600, impact_kjm2=40,
        hdt_c=90, shore=None, hygro=5, dry=(80, 12), ams="ht_only", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI + glue"], glue="glue stick",
        warp=4, use_cases=["gears", "hinges", "wear parts", "snap fits that never break"],
        notes="Tough and slippery — the gear material. The most hygroscopic filament there is: it ruins "
              "in hours on an open spool. Store and print from a dryer or AMS HT.",
    ),
    "paht_cf": dict(
        label="PAHT-CF", family="PA", aliases=["paht-cf", "pa-cf", "pa6-cf", "pahs-cf"], info_idx=["GFN04", "GFN03", "GFN05"],
        nozzle=(270, 300), bed=(80, 100), chamber=60, enclosure="required", cooling=(0, 30),
        max_vol_speed=10, density=1.17, tensile_mpa=90, flex_mod_mpa=6500, impact_kjm2=35,
        hdt_c=150, shore=None, hygro=5, dry=(80, 12), ams="ht_only", abrasive=True, hardened=True,
        min_nozzle=0.4, plate=["Textured PEI + glue"], glue="glue stick", warp=2,
        use_cases=["end-use mechanical parts", "metal replacements", "clipper/tool fixtures"],
        notes="The 'print it once, forget it' engineering material: stiff as filled nylon gets, "
              "150 °C service. Hardened nozzle, relentless drying.",
    ),
    "tpu_95a": dict(
        label="TPU 95A", family="TPU", aliases=["tpu", "tpu 95a", "tpu95a", "tpu for ams"], info_idx=["GFU01", "GFU00"],
        nozzle=(220, 240), bed=(30, 45), chamber=None, enclosure="open", cooling=(40, 80),
        max_vol_speed=6, density=1.21, tensile_mpa=35, flex_mod_mpa=80, impact_kjm2=None,
        hdt_c=None, shore="95A", hygro=4, dry=(70, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI", "Smooth PEI"], glue="none; releases easily when cool",
        warp=1, use_cases=["gaskets", "phone/remote bumpers", "vibration mounts", "trailer drawer liners"],
        notes="'TPU for AMS' (high-speed 95A HF) runs through the AMS; softer generic TPU must go on the "
              "external spool. Print slow, dry it, and disable retraction-heavy settings.",
    ),
    "tpu_soft": dict(
        label="TPU 85A (soft)", family="TPU", aliases=["tpu 85a", "tpu 90a", "85a", "90a"], info_idx=["GFU02"],
        nozzle=(215, 235), bed=(30, 40), chamber=None, enclosure="open", cooling=(40, 80),
        max_vol_speed=3.5, density=1.18, tensile_mpa=25, flex_mod_mpa=25, impact_kjm2=None,
        hdt_c=None, shore="85A", hygro=4, dry=(70, 8), ams="external", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Smooth PEI"], glue="none", warp=1,
        use_cases=["squishy grips", "seals", "wheels"],
        notes="Too soft for the AMS feed path — external spool only, direct and slow.",
    ),
    "pva": dict(
        label="PVA (soluble)", family="PVA", aliases=["pva", "water soluble"], info_idx=["GFS04", "GFS02"],
        nozzle=(215, 230), bed=(45, 60), chamber=None, enclosure="open", cooling=(60, 100),
        max_vol_speed=12, density=1.23, tensile_mpa=20, flex_mod_mpa=1800, impact_kjm2=None,
        hdt_c=None, shore=None, hygro=5, dry=(50, 10), ams="ht_only", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none", warp=1,
        use_cases=["dissolvable supports inside PLA/PETG parts"],
        notes="Dissolves in plain water — magic for internal cavities. Also dissolves in humid garage "
              "air: keep it sealed with desiccant always.",
    ),
    "hips": dict(
        label="HIPS", family="HIPS", aliases=["hips"], info_idx=["GFS05"],
        nozzle=(230, 260), bed=(90, 100), chamber=50, enclosure="required", cooling=(10, 40),
        max_vol_speed=14, density=1.04, tensile_mpa=25, flex_mod_mpa=1700, impact_kjm2=28,
        hdt_c=85, shore=None, hygro=2, dry=(70, 6), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none", warp=3,
        use_cases=["soluble supports for ABS/ASA (d-limonene)", "light stiff parts"],
        notes="Pairs with ABS: similar temps, dissolves in d-limonene leaving perfect surfaces.",
    ),
    "support_w": dict(
        label="Support W (for PLA/PETG)", family="SUPPORT", aliases=["support w", "support for pla", "support for pla/petg"],
        info_idx=["GFS00", "GFS03"],
        nozzle=(190, 230), bed=(45, 65), chamber=None, enclosure="open", cooling=(80, 100),
        max_vol_speed=12, density=1.25, tensile_mpa=15, flex_mod_mpa=1500, impact_kjm2=None,
        hdt_c=None, shore=None, hygro=3, dry=(50, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none", warp=1,
        use_cases=["break-away support interface under PLA/PETG"],
        notes="Use as the INTERFACE layer only (slicer setting) — a few grams per print, peels clean.",
    ),
    "support_g": dict(
        label="Support G (for PA/PC)", family="SUPPORT", aliases=["support g", "support for pa", "support for pa/pc"],
        info_idx=["GFS01"],
        nozzle=(260, 290), bed=(80, 100), chamber=60, enclosure="required", cooling=(0, 30),
        max_vol_speed=10, density=1.20, tensile_mpa=18, flex_mod_mpa=1600, impact_kjm2=None,
        hdt_c=None, shore=None, hygro=4, dry=(80, 8), ams="yes", abrasive=False, hardened=False,
        min_nozzle=0.4, plate=["Textured PEI + glue"], glue="follow base material", warp=2,
        use_cases=["break-away support interface under PA/PC"],
        notes="High-temp support interface for the engineering materials.",
    ),
    "pet_cf": dict(
        label="PET-CF", family="PETG", aliases=["pet-cf", "pet cf"], info_idx=["GFT01", "GFT00"],
        nozzle=(260, 290), bed=(80, 100), chamber=55, enclosure="recommended", cooling=(10, 40),
        max_vol_speed=10, density=1.30, tensile_mpa=70, flex_mod_mpa=5600, impact_kjm2=25,
        hdt_c=120, shore=None, hygro=4, dry=(80, 10), ams="yes", abrasive=True, hardened=True,
        min_nozzle=0.4, plate=["Textured PEI"], glue="none", warp=2,
        use_cases=["stiff high-heat parts without nylon's moisture drama"],
        notes="PAHT-CF performance with easier handling; anneal for full heat resistance.",
    ),
}

# ---------------------------------------------------------------- bonding matrix
# Same family bonds excellently (prints as one part). Cross-family verdicts below.
# level: 4 weld · 3 strong · 2 moderate · 1 weak (break-away) · 0 none/incompatible
_PAIRS: dict[frozenset[str], tuple[int, str]] = {
    frozenset(("PLA", "PETG")): (1, "Barely bonds — the classic break-away pair. Use PETG as support "
                                    "interface under PLA (or vice versa) for clean zero-scar overhangs."),
    frozenset(("PLA", "TPU")): (2, "Moderate weld. Add mechanical interlocks (dovetails, through-holes) "
                                   "for flexible-grip-on-rigid parts."),
    frozenset(("PLA", "PVA")): (3, "PVA sticks well to PLA and dissolves in water — the premium soluble "
                                   "support combo for internal cavities."),
    frozenset(("PLA", "SUPPORT")): (1, "Designed pairing: supports snap away clean."),
    frozenset(("PLA", "ABS")): (0, "Don't combine: temps are incompatible (PLA cooks in an ABS chamber)."),
    frozenset(("PLA", "PC")): (0, "Incompatible temperatures."),
    frozenset(("PLA", "PA")): (0, "Incompatible temperatures and no adhesion."),
    frozenset(("PLA", "HIPS")): (0, "Incompatible temperatures."),
    frozenset(("PETG", "TPU")): (3, "Genuinely strong weld — the go-to rigid+flexible combination "
                                    "(PETG body, TPU gasket/grip in one print)."),
    frozenset(("PETG", "PVA")): (2, "Works as soluble support for PETG; dry both."),
    frozenset(("PETG", "SUPPORT")): (1, "Designed pairing: snap-away interface."),
    frozenset(("PETG", "ABS")): (1, "Weak bond, workable temps — usable as mutual break-away."),
    frozenset(("PETG", "PA")): (0, "No practical adhesion."),
    frozenset(("PETG", "PC")): (1, "Weak; not recommended structurally."),
    frozenset(("ABS", "HIPS")): (3, "Strong in-print bond and HIPS dissolves in d-limonene — "
                                    "the soluble-support system for ABS/ASA."),
    frozenset(("ABS", "PC")): (3, "Bond well (PC/ABS is a real-world blend). Stiff + tough hybrids."),
    frozenset(("ABS", "TPU")): (2, "Moderate; keep chamber modest or TPU softens."),
    frozenset(("ABS", "PA")): (1, "Weak bond."),
    frozenset(("PC", "PA")): (1, "Weak bond; both demand different drying regimes."),
    frozenset(("PC", "SUPPORT")): (1, "Use Support G as the interface."),
    frozenset(("PA", "SUPPORT")): (1, "Use Support G as the interface."),
    frozenset(("PA", "TPU")): (2, "Moderate weld; both love moisture — dry everything."),
    frozenset(("PVA", "TPU")): (2, "Usable soluble support for TPU."),
    frozenset(("ABS", "PVA")): (0, "PVA cooks and clogs at ABS chamber temps."),
}

_LEVELS = {4: "weld", 3: "strong", 2: "moderate", 1: "break-away", 0: "incompatible"}


def materials() -> dict[str, dict[str, Any]]:
    return M


def lookup(name: str | None = None, info_idx: str | None = None) -> dict[str, Any] | None:
    """Resolve a tray's filament to a DB record: info_idx prefix first, then name."""
    if info_idx:
        idx = info_idx.upper()
        best_rec, best_len = None, 0
        for rec in M.values():
            for p in rec["info_idx"]:
                if idx.startswith(p) and len(p) > best_len:
                    best_rec, best_len = rec, len(p)
        if best_rec:
            return best_rec
    if not name:
        return None
    n = name.strip().lower()
    for rec in M.values():
        if n in rec["aliases"]:
            return rec
    # fuzzy: longest alias contained in the name ("Bambu PLA Matte" → pla matte)
    best, best_len = None, 0
    for rec in M.values():
        for a in rec["aliases"]:
            if a in n and len(a) > best_len:
                best, best_len = rec, len(a)
    if best:
        return best
    # family fallback (e.g. "PLA Galaxy")
    for fam_key in ("pla", "petg", "abs", "asa", "pc", "tpu_95a", "pa"):
        if M[fam_key]["family"].lower() in n.split()[0] if n else False:
            return M[fam_key]
    head = n.split()[0] if n else ""
    for rec in M.values():
        if rec["family"].lower() == head:
            return rec
    return None


def compatibility(a: str | dict, b: str | dict) -> dict[str, Any]:
    """Bond verdict between two materials (records, names, or family strings)."""
    fa = a["family"] if isinstance(a, dict) else ((lookup(a) or {}).get("family") or str(a).upper())
    fb = b["family"] if isinstance(b, dict) else ((lookup(b) or {}).get("family") or str(b).upper())
    if fa == fb:
        if fa == "TPU":
            return {"level": 3, "verdict": "strong", "note": "Same-family TPU bonds well; match shore hardness."}
        return {"level": 4, "verdict": "weld", "note": "Same family — prints as one solid part."}
    hit = _PAIRS.get(frozenset((fa, fb)))
    if hit:
        return {"level": hit[0], "verdict": _LEVELS[hit[0]], "note": hit[1]}
    return {"level": 1, "verdict": "unknown", "note": f"No published pairing data for {fa}+{fb} — "
            "test a small weld coupon before trusting it structurally."}


def classify_pairing(types: list[str]) -> dict[str, Any] | None:
    """Advisor verdict for a multi-material job: what is this combination FOR?"""
    fams = []
    for t in types:
        rec = lookup(t)
        fam = rec["family"] if rec else t.upper()
        if fam not in fams:
            fams.append(fam)
    if len(fams) < 2:
        return None
    worst = {"level": 5}
    pairs = []
    for i, a in enumerate(fams):
        for b in fams[i + 1:]:
            c = compatibility(a, b)
            pairs.append({"pair": f"{a}+{b}", **c})
            if c["level"] < worst["level"]:
                worst = c
    kind = ("soluble-support" if "PVA" in fams or ("HIPS" in fams and "ABS" in fams)
            else "support-interface" if "SUPPORT" in fams or worst["level"] == 1
            else "laminate" if worst["level"] >= 3
            else "risky" if worst["level"] == 0 else "mixed")
    return {"kind": kind, "families": fams, "pairs": pairs, "weakest": worst.get("verdict", "unknown")}


def abrasive(name: str | None, info_idx: str | None = None) -> bool:
    rec = lookup(name, info_idx)
    if rec:
        return bool(rec["abrasive"])
    n = (name or "").lower()
    return any(tag in n for tag in ("-cf", " cf", "carbon", "-gf", "glass", "glow", "metal", "sparkle", "galaxy"))


def dry_spec(name: str | None, info_idx: str | None = None) -> tuple[int, int] | None:
    rec = lookup(name, info_idx)
    return tuple(rec["dry"]) if rec and rec.get("dry") else None


def export() -> dict[str, Any]:
    """Serializable snapshot for the frontend."""
    return {
        "version": DB_VERSION,
        "materials": M,
        "levels": _LEVELS,
        "pairs": [{"a": sorted(k)[0], "b": sorted(k)[1], "level": v[0], "note": v[1]} for k, v in _PAIRS.items()],
    }
