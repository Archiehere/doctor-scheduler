"""Doctor leave and blocks, and how existing bookings are re-placed."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import MONDAY, add_doctor, book


def test_leave_moves_booking_to_another_doctor_at_the_same_time(
    client: TestClient, session: Session
) -> None:
    rao = add_doctor(session, "Dr Rao")
    iyer = add_doctor(session, "Dr Iyer")
    booking = book(client, preferred=10 * 60)
    owner = rao.id if booking["doctor"]["id"] == rao.id else iyer.id

    response = client.post(
        f"/doctors/{owner}/time-off", json={"day": MONDAY.isoformat(), "kind": "leave"}
    )
    assert response.status_code == 201
    assert response.json()["reflow"]["moved_same_time"] == [booking["code"]]

    moved = client.get(f"/bookings/{booking['code']}").json()
    assert moved["doctor"]["id"] != owner
    assert moved["start_minute"] == booking["start_minute"]
    assert moved["source"] == "reassigned"
    assert moved["notice"]


def test_block_moves_booking_to_another_time_within_patient_ranges(
    client: TestClient, session: Session
) -> None:
    rao = add_doctor(session, "Dr Rao")
    booking = book(client, ranges=[(9 * 60, 12 * 60)], preferred=10 * 60)
    start = booking["start_minute"]
    assert isinstance(start, int)

    response = client.post(
        f"/doctors/{rao.id}/time-off",
        json={
            "day": MONDAY.isoformat(),
            "kind": "block",
            "start_minute": start,
            "end_minute": start + 60,
            "reason": "Ward round",
        },
    ).json()
    assert response["reflow"]["moved_new_time"] == [booking["code"]]
    moved = client.get(f"/bookings/{booking['code']}").json()
    assert moved["status"] == "confirmed"
    assert moved["start_minute"] >= 9 * 60 and moved["end_minute"] <= 12 * 60
    assert not (start <= moved["start_minute"] < start + 60)


def test_booking_needs_reschedule_when_no_capacity_then_patient_picks_new_time(
    client: TestClient, session: Session
) -> None:
    rao = add_doctor(session, "Dr Rao", hours=[(9 * 60, 17 * 60)])
    booking = book(client, ranges=[(10 * 60, 11 * 60)], preferred=10 * 60)
    client.post(
        f"/doctors/{rao.id}/time-off",
        json={"day": MONDAY.isoformat(), "kind": "block", "start_minute": 600, "end_minute": 660},
    )
    flagged = client.get(f"/bookings/{booking['code']}").json()
    assert flagged["status"] == "needs_reschedule"
    assert flagged["can_reschedule"] is True

    options = client.get(f"/bookings/{booking['code']}/reschedule-options").json()
    assert options["options"]
    pick = options["options"][0]
    rescheduled = client.post(
        f"/bookings/{booking['code']}/reschedule",
        json={
            "doctor_id": pick["doctor"]["id"],
            "day": pick["day"],
            "start_minute": pick["start_minute"],
        },
    ).json()
    assert rescheduled["status"] == "confirmed"
    assert rescheduled["notice"] is None


def test_removing_time_off_reopens_capacity(client: TestClient, session: Session) -> None:
    rao = add_doctor(session, "Dr Rao")
    created = client.post(
        f"/doctors/{rao.id}/time-off", json={"day": MONDAY.isoformat(), "kind": "leave"}
    ).json()
    schedule = client.get(f"/doctors/{rao.id}/schedule", params={"day": MONDAY.isoformat()}).json()
    assert schedule["stats"]["open_minutes"] == 0

    client.delete(f"/doctors/{rao.id}/time-off/{created['time_off']['id']}")
    schedule = client.get(f"/doctors/{rao.id}/schedule", params={"day": MONDAY.isoformat()}).json()
    assert schedule["stats"]["open_minutes"] == 4 * 60


def test_replacing_working_hours_flags_bookings_outside_new_hours(
    client: TestClient, session: Session
) -> None:
    rao = add_doctor(session, "Dr Rao")
    booking = book(client, ranges=[(12 * 60, 13 * 60)], preferred=12 * 60)
    hours = [{"weekday": wd, "start": 9 * 60, "end": 11 * 60} for wd in range(5)]
    summary = client.put(f"/doctors/{rao.id}/hours", json=hours).json()
    assert summary["needs_reschedule"] == [booking["code"]]
    assert len(client.get(f"/doctors/{rao.id}/hours").json()) == 5


def test_time_off_in_the_past_is_rejected(client: TestClient, session: Session) -> None:
    rao = add_doctor(session, "Dr Rao")
    response = client.post(
        f"/doctors/{rao.id}/time-off", json={"day": "2026-10-01", "kind": "leave"}
    )
    assert response.status_code == 422
