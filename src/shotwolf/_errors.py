from __future__ import annotations

from typing import Optional


class ShotWolfError(Exception):
    """Raised for any non-2xx API response.

    ``type`` mirrors the API error envelope (``invalid_params``,
    ``insufficient_credits``, ``rate_limited``, ...). ``status`` is the HTTP
    status code (0 for client-side/transport errors).
    """

    def __init__(
        self,
        message: str,
        *,
        type: str = "unknown",
        status: int = 0,
        request_id: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.type = type
        self.status = status
        self.request_id = request_id
        self.retry_after = retry_after


class ShotWolfTimeoutError(ShotWolfError):
    """Raised when a request exceeds the configured timeout."""

    def __init__(self, timeout: float) -> None:
        super().__init__(f"Request timed out after {timeout}s", type="timeout", status=0)
