"""Application errors use one envelope. They are not stack traces."""

from __future__ import annotations

from typing import Any


class HaloError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class CapabilityError(HaloError):
    def __init__(self, message: str) -> None:
        super().__init__(
            501,
            "CAPABILITY_UNAVAILABLE",
            message,
            details={"retryable": False},
        )
