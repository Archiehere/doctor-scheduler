"""iCalendar export so patients can put the call in their own calendar."""

from __future__ import annotations

from app.clock import CLINIC_TZ
from app.models import Booking


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def booking_ics(booking: Booking) -> str:
    fmt = "%Y%m%dT%H%M%S"
    tz = CLINIC_TZ.key
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Rounds//Doctor calls//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{booking.code}@rounds.local",
        f"DTSTAMP:{booking.created_at.strftime(fmt)}",
        f"DTSTART;TZID={tz}:{booking.starts_at.strftime(fmt)}",
        f"DTEND;TZID={tz}:{booking.ends_at.strftime(fmt)}",
        f"SUMMARY:{_escape(f'Video call with {booking.doctor.name}')}",
        f"DESCRIPTION:{_escape(f'Booking reference {booking.code}.')}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"
