"""Derived metrics. Pure Python."""
from __future__ import annotations

import math
import statistics
from collections import deque


def c_to_f(c: float | None) -> float | None:
    return None if c is None else c * 9 / 5 + 32


def f_to_c(f: float | None) -> float | None:
    return None if f is None else (f - 32) * 5 / 9


def dew_point_c(temp_c: float | None, rh: float | None) -> float | None:
    """Magnus formula."""
    if temp_c is None or rh is None or rh <= 0:
        return None
    g = math.log(rh / 100) + (17.62 * temp_c) / (243.12 + temp_c)
    return 243.12 * g / (17.62 - g)


def parse_price_map(text: str | None) -> dict[str, float]:
    """'PLA=20, PETG=22.5' → {'PLA': 20.0, 'PETG': 22.5}."""
    out: dict[str, float] = {}
    for part in (text or "").replace(";", ",").split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        try:
            out[k.strip().upper()] = float(v.strip())
        except ValueError:
            continue
    return out


def filament_cost(filaments: list[dict], default_per_kg: float, overrides: dict[str, float]) -> float:
    total = 0.0
    for f in filaments:
        ftype = str(f.get("type") or "").upper()
        price = overrides.get(ftype)
        if price is None:  # PLA-CF → PLA
            price = next((v for k, v in overrides.items() if ftype.startswith(k)), default_per_kg)
        total += (f.get("used_g") or 0) / 1000 * price
    return round(total, 2)


class PaceTracker:
    """Rolling median seconds-per-layer from observed layer changes."""

    def __init__(self, window: int = 15) -> None:
        self._durations: deque[float] = deque(maxlen=window)
        self._last: tuple[float, int] | None = None

    def reset(self) -> None:
        self._durations.clear()
        self._last = None

    def on_layer(self, now: float, layer: int) -> None:
        if self._last is not None:
            t0, l0 = self._last
            if layer > l0 and now > t0:
                per = (now - t0) / (layer - l0)
                if 0.5 < per < 3600:
                    self._durations.append(per)
            elif layer < l0:
                self.reset()
        self._last = (now, layer)

    @property
    def seconds_per_layer(self) -> float | None:
        if len(self._durations) < 2:
            return None
        return round(statistics.median(self._durations), 1)

    @property
    def layers_per_hour(self) -> float | None:
        spl = self.seconds_per_layer
        return round(3600 / spl, 1) if spl else None

    def eta_seconds(self, layers_remaining: int) -> float | None:
        spl = self.seconds_per_layer
        if spl is None or layers_remaining < 0:
            return None
        return spl * layers_remaining
