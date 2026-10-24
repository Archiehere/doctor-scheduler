from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import Base, engine
from app.errors import DomainError
from app.routers import analytics, doctors, patients


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Rounds API",
    description="Instant, demand-aware scheduling for doctor video calls.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return schema errors in the same shape as domain errors, with a readable message."""
    first = exc.errors()[0] if exc.errors() else {}
    field = str(first.get("loc", ("", "request"))[-1]).replace("_", " ")
    if first.get("type") == "string_pattern_mismatch":
        message = f"Enter a valid {field}"
    else:
        message = f"{field.capitalize()}: {first.get('msg', 'invalid value')}"
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation", "message": message}},
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(analytics.router)
