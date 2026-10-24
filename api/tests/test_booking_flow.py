"""End-to-end booking flow through the HTTP API."""

from __future__ import annotations

import threading
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.errors import SlotUnavailable
from app.models import Booking, BookingStatus
from app.services import booking as booking_service
from tests.conftest import (
    MONDAY,
    START_OF_DAY,
    FakeClock,
    add_doctor,
    book,
    booking_row,
    hold_option,
    request_body,
)


def test_request_returns_three_options_inside_range(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao")
    add_doctor(session, "Dr Iyer")
    response = client.post("/booking-requests", json=request_body(ranges=[(9 * 60, 12 * 60)]))
    assert response.status_code == 200
    data = response.json()
    assert data["in_range"] is True
    assert len(data["options"]) == 3
    assert "recommended" in data["options"][0]["labels"]
    for opt in data["options"]:
        assert opt["start_minute"] >= 9 * 60 and opt["end_minute"] <= 12 * 60


def test_preferred_time_outside_ranges_is_rejected(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao")
    response = client.post(
        "/booking-requests", json=request_body(ranges=[(9 * 60, 10 * 60)], preferred=15 * 60)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_hold_confirm_and_view(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao")
    booking = book(client)
    assert booking["status"] == "confirmed"
    assert booking["deposit_status"] == "none"
    fetched = client.get(f"/bookings/{booking['code']}").json()
    assert fetched["doctor"]["name"] == "Dr Rao"
    ics = client.get(f"/bookings/{booking['code']}/calendar.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in ics.text


def test_same_slot_cannot_be_held_twice(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao")
    first = client.post("/booking-requests", json=request_body()).json()
    second = client.post("/booking-requests", json=request_body(email="b@example.com")).json()
    hold_option(client, first)
    opt = first["options"][0]
    clash = client.post(
        "/bookings",
        json={
            "request_id": second["request_id"],
            "doctor_id": opt["doctor"]["id"],
            "day": opt["day"],
            "start_minute": opt["start_minute"],
        },
    )
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "slot_unavailable"


def test_concurrent_holds_on_one_slot_admit_exactly_one(
    client: TestClient, session: Session, session_factory: sessionmaker[Session]
) -> None:
    doctor = add_doctor(session, "Dr Rao")
    request_ids = [
        client.post("/booking-requests", json=request_body(email=f"p{i}@example.com")).json()[
            "request_id"
        ]
        for i in range(6)
    ]
    outcomes: list[str] = []
    barrier = threading.Barrier(len(request_ids))

    def attempt(request_id: int) -> None:
        with session_factory() as s:
            barrier.wait()
            try:
                booking_service.hold(
                    s,
                    request_id=request_id,
                    doctor_id=doctor.id,
                    day=MONDAY,
                    start_minute=10 * 60,
                    now=START_OF_DAY,
                )
                outcomes.append("ok")
            except SlotUnavailable:
                outcomes.append("taken")

    threads = [threading.Thread(target=attempt, args=(rid,)) for rid in request_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 1
    assert outcomes.count("taken") == len(request_ids) - 1


def test_expired_hold_cannot_be_confirmed(
    client: TestClient, session: Session, fake_clock: FakeClock
) -> None:
    add_doctor(session, "Dr Rao")
    options = client.post("/booking-requests", json=request_body()).json()
    held = hold_option(client, options)
    fake_clock.advance(minutes=6)
    response = client.post(f"/bookings/{held['code']}/confirm", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "hold_expired"


def _mark(session: Session, code: str, status: BookingStatus) -> None:
    booking = session.scalar(select(Booking).where(Booking.code == code))
    assert booking is not None
    booking.status = status
    session.commit()


def test_repeat_no_shows_require_a_deposit_which_settles_on_outcome(
    client: TestClient, session: Session, fake_clock: FakeClock
) -> None:
    add_doctor(session, "Dr Rao", hours=[(9 * 60, 17 * 60)])
    for _ in range(2):
        _mark(session, str(book(client)["code"]), BookingStatus.NO_SHOW)

    options = client.post("/booking-requests", json=request_body()).json()
    assert options["policy"]["tier"] == "all"
    assert all(o["deposit_required"] for o in options["options"])

    held = hold_option(client, options)
    unpaid = client.post(f"/bookings/{held['code']}/confirm", json={"deposit_paid": False})
    assert unpaid.status_code == 402
    paid = client.post(f"/bookings/{held['code']}/confirm", json={"deposit_paid": True}).json()
    assert paid["deposit_status"] == "held"

    booking = booking_row(session, held["code"])
    fake_clock.current = booking.starts_at
    done = client.post(f"/doctors/bookings/{booking.id}/outcome", json={"action": "complete"})
    assert done.json()["deposit_status"] == "refunded"


def test_no_show_cannot_be_marked_before_the_call(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao")
    code = book(client)["code"]
    booking = booking_row(session, code)
    response = client.post(f"/doctors/bookings/{booking.id}/outcome", json={"action": "no_show"})
    assert response.status_code == 409


def test_late_cancel_counts_as_half_a_strike(
    client: TestClient, session: Session, fake_clock: FakeClock
) -> None:
    add_doctor(session, "Dr Rao")
    booking = book(client, preferred=9 * 60)
    fake_clock.current = START_OF_DAY.replace(hour=8, minute=30)
    cancelled = client.post(f"/bookings/{booking['code']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["late_cancel"] is True

    early = book(client, preferred=12 * 60)
    cancelled_early = client.post(f"/bookings/{early['code']}/cancel").json()
    assert cancelled_early["late_cancel"] is False

    options = client.post("/booking-requests", json=request_body()).json()
    assert options["policy"]["strikes"] == 0.5


def test_full_range_offers_nearby_options_and_waitlist_fills_on_cancel(
    client: TestClient, session: Session
) -> None:
    add_doctor(session, "Dr Rao", hours=[(9 * 60, 10 * 60), (14 * 60, 15 * 60)])
    first = book(client, ranges=[(9 * 60, 10 * 60)], preferred=9 * 60, visit_type="new_consult")
    assert first["start_minute"] in (9 * 60, 9 * 60 + 15)

    options = client.post(
        "/booking-requests",
        json=request_body(
            email="ben@example.com",
            ranges=[(9 * 60, 10 * 60)],
            preferred=9 * 60,
            visit_type="new_consult",
        ),
    ).json()
    assert options["in_range"] is False  # nothing left inside 09:00-10:00
    assert options["options"] == []  # and nothing within reach outside it either

    entry = client.post(
        "/waitlist", json={"request_id": options["request_id"], "deposit_acknowledged": False}
    ).json()
    assert entry["status"] == "waiting"

    client.post(f"/bookings/{first['code']}/cancel")
    filled = client.get(f"/waitlist/{entry['code']}").json()
    assert filled["status"] == "filled"
    rebooked = client.get(f"/bookings/{filled['booking_code']}").json()
    assert rebooked["source"] == "waitlist"
    assert rebooked["status"] == "confirmed"


def test_search_ahead_finds_the_next_day(client: TestClient, session: Session) -> None:
    add_doctor(session, "Dr Rao", weekdays=range(1, 2))  # Tuesdays only
    body = request_body()
    body["search_ahead_days"] = 2
    data = client.post("/booking-requests", json=body).json()
    assert data["options"]
    assert {o["day"] for o in data["options"]} == {date(2026, 11, 3).isoformat()}
