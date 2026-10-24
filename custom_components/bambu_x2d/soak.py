"""Heat-soak state machine. Pure Python, tick-driven, fully unit-tested.

The coordinator calls tick() every ~15 s with fresh readings and executes the
returned actions (heater commands, ambient heater switch, events). Keeping the
logic here makes it testable without a printer or Home Assistant.

Phases: idle → [warming_ambient] → heating → soaking → ready → keep_warm → idle
                                        └→ aborted
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    IDLE = "idle"
    WARMING_AMBIENT = "warming_ambient"
    HEATING = "heating"
    SOAKING = "soaking"
    READY = "ready"
    KEEP_WARM = "keep_warm"
    ABORTED = "aborted"


ACTIVE = {Phase.WARMING_AMBIENT, Phase.HEATING, Phase.SOAKING, Phase.READY, Phase.KEEP_WARM}


@dataclass
class SoakConfig:
    chamber_c: float = 60
    bed_c: float = 100
    hold_base_min: float = 25
    band_c: float = 3
    max_heat_min: float = 60
    keep_warm_min: float = 45
    cold_scaling: bool = True
    cold_ref_f: float = 65
    cold_min_per_f: float = 0.5
    cold_max_min: float = 20
    min_start_f: float = 50
    use_ambient_heater: bool = False
    ambient_warm_max_min: float = 60

    def hold_required(self, ambient_f: float | None) -> float:
        add = 0.0
        if self.cold_scaling and ambient_f is not None:
            add = max(0.0, min((self.cold_ref_f - ambient_f) * self.cold_min_per_f, self.cold_max_min))
        return round(self.hold_base_min + add, 1)

    def cold_adder(self, ambient_f: float | None) -> float:
        return round(self.hold_required(ambient_f) - self.hold_base_min, 1)


@dataclass
class Inputs:
    now: float
    chamber: float | None
    bed: float | None
    ambient_f: float | None = None
    printing: bool = False


@dataclass
class Actions:
    heat: tuple[int, int] | None = None   # (bed °C, chamber °C)
    heaters_off: bool = False
    ambient_heater: bool | None = None    # True on / False off / None leave
    events: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.heat or self.heaters_off or self.ambient_heater is not None or self.events)


class SoakEngine:
    def __init__(self, rate: float = 0.8) -> None:
        self.phase = Phase.IDLE
        self.cfg = SoakConfig()
        self.rate = rate                  # learned °C/min
        self.started: float | None = None
        self.heat_t0: float | None = None
        self.c0: float | None = None
        self.held_min = 0.0
        self.hold_required = 0.0
        self.relaxed = False              # heating timed out but close enough
        self.ready_at: float | None = None
        self._last: float | None = None
        self._ambient_heater_on = False

    # ------------------------------------------------------------ queries
    @property
    def active(self) -> bool:
        return self.phase in ACTIVE

    def heatup_estimate_min(self, chamber: float | None) -> float:
        if chamber is None:
            return 0.0
        need = self.cfg.chamber_c - self.cfg.band_c - chamber
        return round(max(need, 0) / max(self.rate, 0.1), 1)

    def remaining_min(self, inp: Inputs) -> float:
        if self.phase in (Phase.IDLE, Phase.ABORTED, Phase.WARMING_AMBIENT, Phase.HEATING):
            hold = self.hold_required if self.phase != Phase.IDLE else self.cfg.hold_required(inp.ambient_f)
            return round(self.heatup_estimate_min(inp.chamber) + hold, 1)
        if self.phase == Phase.SOAKING:
            return round(max(self.hold_required - self.held_min, 0), 1)
        return 0.0

    def progress(self, inp: Inputs) -> int:
        if self.phase == Phase.HEATING and self.c0 is not None and inp.chamber is not None:
            span = max(self.cfg.chamber_c - self.cfg.band_c - self.c0, 1)
            return round(max(0.0, min((inp.chamber - self.c0) / span, 1.0)) * 50)
        if self.phase == Phase.SOAKING:
            return round(50 + min(self.held_min / max(self.hold_required, 1), 1.0) * 50)
        if self.phase in (Phase.READY, Phase.KEEP_WARM):
            return 100
        return 0

    # ------------------------------------------------------------ control
    def start(self, cfg: SoakConfig, inp: Inputs) -> Actions:
        self.cfg = cfg
        self.started = inp.now
        self.held_min = 0.0
        self.relaxed = False
        self.ready_at = None
        self.hold_required = cfg.hold_required(inp.ambient_f)
        self._last = inp.now
        act = Actions()
        too_cold = inp.ambient_f is not None and inp.ambient_f < cfg.min_start_f
        if too_cold and cfg.use_ambient_heater:
            self.phase = Phase.WARMING_AMBIENT
            act.ambient_heater = True
            self._ambient_heater_on = True
            return act
        return self._begin_heating(inp, act)

    def cancel(self) -> Actions:
        act = Actions(heaters_off=self.phase != Phase.IDLE)
        if self._ambient_heater_on:
            act.ambient_heater = False
            self._ambient_heater_on = False
        self._reset(Phase.IDLE)
        return act

    def _reset(self, phase: Phase) -> None:
        self.phase = phase
        self.held_min = 0.0
        self.c0 = None
        self.heat_t0 = None

    def _begin_heating(self, inp: Inputs, act: Actions) -> Actions:
        self.phase = Phase.HEATING
        self.heat_t0 = inp.now
        self.c0 = inp.chamber
        act.heat = (int(self.cfg.bed_c), int(self.cfg.chamber_c))
        return act

    def _learn(self, inp: Inputs) -> None:
        if self.heat_t0 is None or self.c0 is None or inp.chamber is None:
            return
        mins = (inp.now - self.heat_t0) / 60
        gained = inp.chamber - self.c0
        if mins > 2 and gained > 2:
            self.rate = round(max(0.1, min(0.6 * self.rate + 0.4 * gained / mins, 3.0)), 2)

    def tick(self, inp: Inputs) -> Actions:
        act = Actions()
        dt_min = 0.0 if self._last is None else max(0.0, (inp.now - self._last) / 60)
        self._last = inp.now
        cfg = self.cfg

        if inp.printing and self.phase not in (Phase.IDLE, Phase.ABORTED):
            act.events.append("soak_handoff")
            if self._ambient_heater_on:
                act.ambient_heater = False
                self._ambient_heater_on = False
            self._reset(Phase.IDLE)
            return act

        if self.phase == Phase.WARMING_AMBIENT:
            warm = inp.ambient_f is not None and inp.ambient_f >= cfg.min_start_f
            t0 = self.started if self.started is not None else inp.now
            waited = (inp.now - t0) / 60 >= cfg.ambient_warm_max_min
            if warm or waited:
                return self._begin_heating(inp, act)
            return act

        if self.phase == Phase.HEATING:
            chamber_ok = inp.chamber is not None and inp.chamber >= cfg.chamber_c - cfg.band_c
            bed_ok = inp.bed is None or cfg.bed_c <= 0 or inp.bed >= cfg.bed_c - 3
            t0 = self.heat_t0 if self.heat_t0 is not None else inp.now
            elapsed = (inp.now - t0) / 60
            if chamber_ok and bed_ok:
                self._learn(inp)
                self.phase = Phase.SOAKING
            elif elapsed >= cfg.max_heat_min:
                self._learn(inp)
                if inp.chamber is None or inp.chamber < cfg.chamber_c - cfg.band_c - 5:
                    act.heaters_off = True
                    act.events.append("soak_aborted")
                    if self._ambient_heater_on:
                        act.ambient_heater = False
                        self._ambient_heater_on = False
                    self._reset(Phase.ABORTED)
                    return act
                self.relaxed = True
                act.events.append("soak_stalled")
                self.phase = Phase.SOAKING
            return act

        if self.phase == Phase.SOAKING:
            floor = cfg.chamber_c - cfg.band_c - (5 if self.relaxed else 0)
            if inp.chamber is not None and inp.chamber >= floor:
                self.held_min += dt_min
            else:
                self.held_min = max(0.0, self.held_min - 2 * dt_min)
            if self.held_min >= self.hold_required:
                self.phase = Phase.READY
                self.ready_at = inp.now
                act.events.append("soak_ready")
                if self._ambient_heater_on:
                    act.ambient_heater = False
                    self._ambient_heater_on = False
            return act

        if self.phase == Phase.READY:
            self.phase = Phase.KEEP_WARM
            return act

        if self.phase == Phase.KEEP_WARM:
            if self.ready_at is not None and (inp.now - self.ready_at) / 60 >= cfg.keep_warm_min:
                act.heaters_off = True
                act.events.append("soak_expired")
                self._reset(Phase.IDLE)
            return act

        return act
