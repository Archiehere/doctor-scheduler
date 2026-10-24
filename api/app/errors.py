"""Domain errors. Services raise these; ``app.main`` maps them to HTTP responses."""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class SlotUnavailable(DomainError):
    status_code = 409
    code = "slot_unavailable"


class HoldExpired(DomainError):
    status_code = 409
    code = "hold_expired"


class DepositRequired(DomainError):
    status_code = 402
    code = "deposit_required"


class InvalidTransition(DomainError):
    status_code = 409
    code = "invalid_transition"


class InvalidRequest(DomainError):
    status_code = 422
    code = "invalid_request"
