"""No-show policy: strikes, deposit tiers and how they combine with demand.

Kept free of I/O so the rules can be unit tested and quoted in the README as-is.

Strikes (rolling window):
    no-show = 1, cancellation within ``late_cancel_hours`` = 0.5

Tiers:
    < 1 strike   -> no deposit
    1 - 2        -> deposit on peak slots only (off-peak is waived)
    2 - 4        -> deposit on every slot
    >= 4         -> restricted: same-day, off-peak slots only, deposit required

Waiving deposits off-peak nudges higher-risk patients toward the hours that need
filling, where a no-show costs the clinic least.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import StrEnum

from app.config import Settings


class DepositTier(StrEnum):
    NONE = "none"
    PEAK_ONLY = "peak_only"
    ALL = "all"
    RESTRICTED = "restricted"


def strike_score(
    no_show_times: Iterable[datetime],
    late_cancel_times: Iterable[datetime],
    now: datetime,
    settings: Settings,
) -> float:
    since = now - timedelta(days=settings.strike_window_days)
    no_shows = sum(1 for t in no_show_times if t >= since)
    late = sum(1 for t in late_cancel_times if t >= since)
    return no_shows * settings.strike_no_show + late * settings.strike_late_cancel


def tier_for(strikes: float) -> DepositTier:
    if strikes >= 4:
        return DepositTier.RESTRICTED
    if strikes >= 2:
        return DepositTier.ALL
    if strikes >= 1:
        return DepositTier.PEAK_ONLY
    return DepositTier.NONE


def deposit_required(tier: DepositTier, is_peak: bool) -> bool:
    if tier == DepositTier.NONE:
        return False
    if tier == DepositTier.PEAK_ONLY:
        return is_peak
    return True


def is_late_cancel(starts_at: datetime, now: datetime, settings: Settings) -> bool:
    return starts_at - now < timedelta(hours=settings.late_cancel_hours)
