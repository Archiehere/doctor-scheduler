"""The current time in clinic-local wall-clock terms.

Injected into routes as a dependency so tests and the seed script can pin "now".
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo(os.getenv("CLINIC_TZ", "Asia/Kolkata"))


def now() -> datetime:
    """Naive datetime in the clinic timezone, truncated to the minute."""
    return datetime.now(CLINIC_TZ).replace(tzinfo=None, second=0, microsecond=0)
