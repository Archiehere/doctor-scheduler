from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.db import get_session
from app.models import Doctor

SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(clock.now)]


def doctors_by_id(session: Session) -> dict[int, Doctor]:
    return {d.id: d for d in session.scalars(select(Doctor)).all()}
