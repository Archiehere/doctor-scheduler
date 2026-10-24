from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import clock
from app.db import Base, get_session, make_engine
from app.main import app
from app.models import Booking, Doctor, WorkingHours

# Monday 2 November 2026, 08:00 clinic time.
MONDAY = date(2026, 11, 2)
START_OF_DAY = datetime(2026, 11, 2, 8, 0)


@dataclass
class FakeClock:
    current: datetime = START_OF_DAY

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(session_factory: sessionmaker[Session], fake_clock: FakeClock) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[clock.now] = fake_clock
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def add_doctor(
    session: Session,
    name: str,
    hours: list[tuple[int, int]] | None = None,
    weekdays: range = range(5),
) -> Doctor:
    """A doctor working ``hours`` (minute ranges) on each of ``weekdays``."""
    doctor = Doctor(name=name, specialty="General practice")
    session.add(doctor)
    session.flush()
    for wd in weekdays:
        for start, end in hours or [(9 * 60, 13 * 60)]:
            session.add(
                WorkingHours(doctor_id=doctor.id, weekday=wd, start_minute=start, end_minute=end)
            )
    session.commit()
    return doctor


def request_body(
    *,
    email: str = "asha@example.com",
    ranges: list[tuple[int, int]] | None = None,
    preferred: int = 10 * 60,
    visit_type: str = "follow_up",
    day: date = MONDAY,
) -> dict[str, object]:
    return {
        "name": "Asha Patel",
        "email": email,
        "visit_type": visit_type,
        "day": day.isoformat(),
        "ranges": [{"start": s, "end": e} for s, e in (ranges or [(9 * 60, 13 * 60)])],
        "preferred_minute": preferred,
    }


def hold_option(
    client: TestClient, options: dict[str, object], index: int = 0
) -> dict[str, object]:
    opt = options["options"][index]  # type: ignore[index]
    response = client.post(
        "/bookings",
        json={
            "request_id": options["request_id"],
            "doctor_id": opt["doctor"]["id"],
            "day": opt["day"],
            "start_minute": opt["start_minute"],
        },
    )
    assert response.status_code == 201, response.text
    held: dict[str, object] = response.json()
    return held


def book(client: TestClient, **kwargs: object) -> dict[str, object]:
    """Request options, hold the recommended one and confirm it."""
    options = client.post("/booking-requests", json=request_body(**kwargs)).json()  # type: ignore[arg-type]
    held = hold_option(client, options)
    confirmed = client.post(f"/bookings/{held['code']}/confirm", json={"deposit_paid": True})
    assert confirmed.status_code == 200, confirmed.text
    result: dict[str, object] = confirmed.json()
    return result


def booking_row(session: Session, code: object) -> Booking:
    """Read a booking and end the transaction, so the API is free to write."""
    booking = session.scalar(select(Booking).where(Booking.code == code))
    session.commit()
    assert booking is not None
    return booking
