"""Wokwi minutes meter: simulated time used in the rolling 30-day window vs the plan limit.

BoardLoop records the configured timeout for runs that don't report their end time, so the
estimate errs high on purpose. Wokwi itself enforces the real limit.
"""
from __future__ import annotations

import time

from .storage import Store

WINDOW_S = 30 * 24 * 3600
WARN_AT = 0.8


def minutes_30d(store: Store, now: float | None = None) -> float:
    now = time.time() if now is None else now
    return round(store.sim_ms_since(int(now - WINDOW_S)) / 60_000, 2)


def status(store: Store, limit: float, now: float | None = None) -> dict:
    used = minutes_30d(store, now)
    out: dict = {"used": used, "limit": limit}
    if limit > 0 and used >= limit:
        out["warning"] = (f"Estimated Wokwi use ({used} min) is at or over your {limit:g}-minute plan "
                          "limit for the last 30 days; Wokwi may refuse runs. Run only failing tests.")
    elif limit > 0 and used >= WARN_AT * limit:
        out["warning"] = (f"Estimated Wokwi use is {used} of {limit:g} minutes (30 days). "
                          "Use mcu_test only=[...] to rerun just the failing tests.")
    return out
