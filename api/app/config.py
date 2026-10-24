"""Central configuration.

Every tunable number the product depends on lives here, so the scheduling policy
can be read (and tuned with ``scripts/simulate.py``) in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum


class VisitType(StrEnum):
    FOLLOW_UP = "follow_up"
    NEW_CONSULT = "new_consult"


VISIT_DURATIONS: dict[VisitType, int] = {
    VisitType.FOLLOW_UP: 30,
    VisitType.NEW_CONSULT: 45,
}


@dataclass(frozen=True)
class ScoringWeights:
    """Weights of the placement score. Lower total score is better.

    Each term is normalised to roughly 0..1 per natural unit (noted below), so the
    weights read as "how many units of X is one unit of Y worth".
    """

    preference: float = 1.0  # per hour away from the preferred time
    fragmentation: float = 1.2  # per gap left behind that is too short to book
    demand: float = 1.6  # per unit of demand index, scaled by patient flexibility
    load: float = 1.0  # per unit of doctor utilisation after the booking
    lead_time: float = 0.6  # per day between now and the call
    outside_range: float = 3.0  # flat cost when a slot is outside the patient's ranges


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./rounds.db")
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        )
    )

    # Scheduling grid
    grid_minutes: int = 15
    min_bookable_gap: int = 30  # a free gap shorter than this is dead time
    min_notice_minutes: int = 15  # earliest start relative to "now"
    max_search_ahead_days: int = 6
    outside_range_margin: int = 120  # how far beyond a range fallback options may go
    options_returned: int = 3

    # Utilisation policy
    utilization_target: float = 0.80
    utilization_soft_cap: float = 0.90  # above this the load penalty gets steep
    overcap_penalty: float = 6.0

    # Demand model
    peak_threshold: float = 0.70  # demand index at or above this is "peak"
    flexibility_full_minutes: int = 240  # slack at which a patient counts as fully flexible
    demand_prior_strength: float = 20.0  # requests needed before history outweighs the prior
    demand_history_days: int = 56

    # Holds and no-show policy
    hold_minutes: int = 5
    late_cancel_hours: int = 2
    strike_window_days: int = 90
    strike_no_show: float = 1.0
    strike_late_cancel: float = 0.5
    deposit_amount: int = 50_000  # minor units (paise)
    currency: str = "INR"
    preferred_tolerance_minutes: int = 30  # within this of the preferred time = "preferred"

    weights: ScoringWeights = field(default_factory=ScoringWeights)


settings = Settings()
