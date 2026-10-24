"""Heat-soak state machine tests."""

import conftest  # noqa: F401

from bambu_x2d.soak import Inputs, Phase, SoakConfig, SoakEngine


def mk(now=0.0, chamber=15.0, bed=20.0, ambient=48.0, printing=False):
    return Inputs(now=now, chamber=chamber, bed=bed, ambient_f=ambient, printing=printing)


CFG = SoakConfig(chamber_c=60, bed_c=100, hold_base_min=25, band_c=3, max_heat_min=60,
                 keep_warm_min=45, cold_scaling=True, cold_ref_f=65, cold_min_per_f=0.5,
                 cold_max_min=20, min_start_f=50)


def test_cold_scaling():
    assert CFG.hold_required(65) == 25
    assert CFG.hold_required(48) == 25 + 8.5
    assert CFG.hold_required(0) == 45          # capped
    no_scale = SoakConfig(**{**CFG.__dict__, "cold_scaling": False})
    assert no_scale.hold_required(0) == 25


def test_full_cycle():
    e = SoakEngine(rate=1.0)
    act = e.start(CFG, mk(now=0))
    assert e.phase == Phase.HEATING
    assert act.heat == (100, 60)
    # heating: chamber climbs
    t = 0.0
    chamber = 15.0
    while e.phase == Phase.HEATING and t < 3600 * 2:
        t += 15
        chamber = min(60.0, chamber + 0.25)
        e.tick(mk(now=t, chamber=chamber, bed=100))
    assert e.phase == Phase.SOAKING
    # soak accumulates in real minutes
    events = []
    while e.phase == Phase.SOAKING and t < 3600 * 4:
        t += 15
        events += e.tick(mk(now=t, chamber=59, bed=100)).events
    assert "soak_ready" in events
    assert e.phase in (Phase.READY, Phase.KEEP_WARM)
    assert e.held_min >= CFG.hold_required(48)
    # keep warm expiry
    e.tick(mk(now=t + 1))  # READY → KEEP_WARM
    act = e.tick(mk(now=t + CFG.keep_warm_min * 60 + 120, chamber=58, bed=100))
    assert act.heaters_off and "soak_expired" in act.events
    assert e.phase == Phase.IDLE


def test_dip_costs_double():
    e = SoakEngine(rate=1.0)
    e.start(CFG, mk())
    e.phase = Phase.SOAKING
    e.hold_required = 10
    e._last = 0.0
    e.tick(mk(now=60, chamber=59))      # +1
    assert e.held_min == 1.0
    e.tick(mk(now=120, chamber=50))     # dip → −2
    assert e.held_min == 0.0
    e.tick(mk(now=180, chamber=59))
    assert e.held_min == 1.0


def test_stall_aborts():
    e = SoakEngine(rate=1.0)
    e.start(CFG, mk(now=0, chamber=15))
    act = e.tick(mk(now=CFG.max_heat_min * 60 + 30, chamber=20))   # way below target
    assert "soak_aborted" in act.events and act.heaters_off
    assert e.phase == Phase.ABORTED


def test_stall_close_relaxes():
    e = SoakEngine(rate=1.0)
    e.start(CFG, mk(now=0, chamber=15))
    act = e.tick(mk(now=CFG.max_heat_min * 60 + 30, chamber=55, bed=100))  # within band+5
    assert "soak_stalled" in act.events
    assert e.phase == Phase.SOAKING and e.relaxed
    # relaxed floor: 60-3-5=52 counts
    e.tick(mk(now=CFG.max_heat_min * 60 + 90, chamber=53, bed=100))
    assert e.held_min > 0


def test_warming_ambient_first():
    cfg = SoakConfig(**{**CFG.__dict__, "use_ambient_heater": True})
    e = SoakEngine()
    act = e.start(cfg, mk(ambient=45))
    assert e.phase == Phase.WARMING_AMBIENT and act.ambient_heater is True
    act = e.tick(mk(now=300, ambient=51))
    assert e.phase == Phase.HEATING and act.heat == (100, 60)


def test_print_handoff():
    e = SoakEngine()
    e.start(CFG, mk())
    act = e.tick(mk(now=60, printing=True))
    assert "soak_handoff" in act.events and e.phase == Phase.IDLE


def test_cancel():
    e = SoakEngine()
    e.start(CFG, mk())
    act = e.cancel()
    assert act.heaters_off and e.phase == Phase.IDLE


def test_learning():
    e = SoakEngine(rate=0.8)
    e.start(CFG, mk(now=0, chamber=20))
    # 40 °C gained in 20 min → 2.0; blended 0.6*0.8+0.4*2.0 = 1.28
    e.tick(mk(now=1200, chamber=60, bed=100))
    assert abs(e.rate - 1.28) < 0.01
    assert e.heatup_estimate_min(20) == round((60 - 3 - 20) / 1.28, 1)
