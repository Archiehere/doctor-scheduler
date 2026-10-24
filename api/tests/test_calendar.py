"""Day-level availability and request validation used by the booking form."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import MONDAY, FakeClock, add_doctor, book, request_body


def _calendar(client: TestClient, days: int = 7) -> dict[str, dict[str, int]]:
    response = client.get(f"/calendar?days={days}")
    assert response.status_code == 200, response.text
    return {d["day"]: d for d in response.json()}


def test_calendar_marks_weekends_closed(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr A")  # 09:00-13:00, Mon-Fri
    days = _calendar(client)

    monday = days[MONDAY.isoformat()]
    assert monday["open_minutes"] == 240
    assert monday["bookable_minutes"] == 240
    saturday = days[(MONDAY + timedelta(days=5)).isoformat()]
    assert (saturday["open_minutes"], saturday["bookable_minutes"]) == (0, 0)


def test_calendar_drops_time_that_has_passed(
    client: TestClient, session: Session, fake_clock: FakeClock
) -> None:
    add_doctor(session, "Dr A")
    fake_clock.advance(hours=4, minutes=40)  # 12:40, notice pushes the earliest start to 13:00
    today = _calendar(client)[MONDAY.isoformat()]
    assert today["open_minutes"] == 240
    assert today["bookable_minutes"] == 0


def test_calendar_ignores_gaps_too_short_to_book(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr A", hours=[(9 * 60, 10 * 60 + 15)])
    book(client, ranges=[(9 * 60, 10 * 60 + 15)], preferred=9 * 60 + 15)
    today = _calendar(client)[MONDAY.isoformat()]
    # One 30-minute call leaves 45 minutes, split into gaps of 15 and 30 at most.
    assert today["bookable_minutes"] < 75
    assert today["bookable_minutes"] % 15 == 0


def test_requests_beyond_the_booking_horizon_are_rejected(
    client: TestClient, session: Session
) -> None:
    add_doctor(session, "Dr A")
    response = client.post("/booking-requests", json=request_body(day=MONDAY + timedelta(days=60)))
    assert response.status_code == 422
    assert "days ahead" in response.json()["error"]["message"]


def test_schema_errors_use_the_domain_error_shape(client: TestClient) -> None:
    response = client.post("/booking-requests", json={**request_body(), "email": "nope"})
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation", "message": "Enter a valid email"}}
