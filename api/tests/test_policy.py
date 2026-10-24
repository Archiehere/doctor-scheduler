from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.services.policy import (
    DepositTier,
    deposit_required,
    is_late_cancel,
    strike_score,
    tier_for,
)

NOW = datetime(2026, 11, 2, 9, 0)


@pytest.mark.parametrize(
    ("strikes", "tier"),
    [
        (0, DepositTier.NONE),
        (0.5, DepositTier.NONE),
        (1, DepositTier.PEAK_ONLY),
        (2, DepositTier.ALL),
        (3.5, DepositTier.ALL),
        (4, DepositTier.RESTRICTED),
    ],
)
def test_tiers(strikes: float, tier: DepositTier) -> None:
    assert tier_for(strikes) == tier


def test_peak_only_tier_waives_off_peak_deposit() -> None:
    assert deposit_required(DepositTier.PEAK_ONLY, is_peak=True)
    assert not deposit_required(DepositTier.PEAK_ONLY, is_peak=False)
    assert deposit_required(DepositTier.ALL, is_peak=False)
    assert not deposit_required(DepositTier.NONE, is_peak=True)


def test_strikes_expire_after_window() -> None:
    old = NOW - timedelta(days=settings.strike_window_days + 1)
    recent = NOW - timedelta(days=3)
    assert strike_score([old, recent], [recent], NOW, settings) == 1.5


def test_late_cancel_boundary() -> None:
    assert is_late_cancel(NOW + timedelta(hours=1, minutes=59), NOW, settings)
    assert not is_late_cancel(NOW + timedelta(hours=2), NOW, settings)
