from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

from ._errors import ShotWolfError, ShotWolfTimeoutError

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://shotwolf.com"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF = 0.5
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# A transport takes (method, url, headers, body_bytes, timeout) and returns
# (status_code, response_headers, response_body_bytes). Injectable for tests.
Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, Dict[str, str], bytes]]


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Hands a 30x back to the caller instead of chasing it.

    urllib follows redirects by default and carries every header to the new
    host, ``Authorization`` included - so one redirect anywhere in the chain
    gives an API key to whoever answered. The API does not redirect; if it ever
    starts, that is our bug to fix, not the key's problem to survive.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirects)


def _urllib_transport(
    method: str, url: str, headers: Dict[str, str], body: Optional[bytes], timeout: float
) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as err:  # non-2xx, and 30x, still carry a body
        return err.code, {k.lower(): v for k, v in (err.headers or {}).items()}, err.read()


class ShotWolf:
    """Client for the ShotWolf API. Pass an API key (``sw_live_...``) or set
    the ``SHOTWOLF_API_KEY`` environment variable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        transport: Optional[Transport] = None,
    ) -> None:
        key = api_key or os.environ.get("SHOTWOLF_API_KEY")
        if not key:
            raise ShotWolfError(
                "Missing API key. Pass api_key= or set SHOTWOLF_API_KEY.",
                type="unauthorized",
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._transport: Transport = transport or _urllib_transport

    # --- endpoints -------------------------------------------------------

    def capture(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Capture a URL or HTML synchronously. POST /api/v1/captures"""
        return self._request("POST", "/api/v1/captures", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def capture_async(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Queue a capture and return immediately. POST /api/v1/captures/async"""
        return self._request("POST", "/api/v1/captures/async", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def batch(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Render one URL across 2-6 devices. POST /api/v1/capture/batch"""
        return self._request("POST", "/api/v1/capture/batch", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def mockup(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Render a URL inside a device/social mockup. POST /api/v1/mockups"""
        return self._request("POST", "/api/v1/mockups", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def og(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Generate an Open Graph card from a template. POST /api/v1/og"""
        return self._request("POST", "/api/v1/og", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def pdf(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Convert a URL or HTML string to PDF. POST /api/v1/pdf"""
        return self._request("POST", "/api/v1/pdf", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def diff(self, *, idempotency_key: Optional[str] = None, timeout: Optional[float] = None, **params: Any) -> Dict[str, Any]:
        """Pixel-diff two screenshots. POST /api/v1/diffs"""
        return self._request("POST", "/api/v1/diffs", body=params, idempotency_key=idempotency_key, timeout=timeout)

    def get_screenshot(self, screenshot_id: int, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Retrieve a single screenshot by ID. GET /api/v1/screenshots/:id"""
        return self._request("GET", "/api/v1/screenshots/{}".format(int(screenshot_id)), timeout=timeout)

    def account(self, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get balance, tier and webhook secret. GET /api/v1/account"""
        return self._request("GET", "/api/v1/account", timeout=timeout)

    def wait_for(self, screenshot_id: int, *, interval: float = 2.0, timeout: float = 120.0) -> Dict[str, Any]:
        """Poll ``get_screenshot`` until the shot is ``done`` or ``failed``.

        Returns the final screenshot dict; raises ``ShotWolfError`` on render
        failure or ``ShotWolfTimeoutError`` if the deadline passes.
        """
        deadline = time.monotonic() + timeout
        while True:
            shot = self.get_screenshot(screenshot_id)
            status = shot.get("status")
            if status == "done":
                return shot
            if status == "failed":
                raise ShotWolfError(
                    "Screenshot {} failed to render".format(screenshot_id),
                    type="render_failed",
                    status=422,
                )
            if time.monotonic() + interval > deadline:
                raise ShotWolfTimeoutError(timeout)
            time.sleep(interval)

    # --- internals -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        url = self.base_url + path
        req_timeout = timeout if timeout is not None else self.timeout
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Accept": "application/json",
            "User-Agent": "shotwolf-python/" + __version__,
        }
        payload: Optional[bytes] = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                status, resp_headers, resp_body = self._transport(method, url, headers, payload, req_timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                is_timeout = isinstance(err, (TimeoutError,)) or isinstance(getattr(err, "reason", None), TimeoutError)
                last_error = ShotWolfTimeoutError(req_timeout) if is_timeout else err
                if attempt < self.max_retries:
                    time.sleep(self._backoff(attempt))
                    continue
                raise last_error

            if 200 <= status < 300:
                if not resp_body:
                    return {}
                return json.loads(resp_body.decode("utf-8"))

            if status in RETRYABLE_STATUSES and attempt < self.max_retries:
                time.sleep(self._parse_retry_after(resp_headers) or self._backoff(attempt))
                continue

            raise self._to_error(status, resp_headers, resp_body)

        raise last_error or ShotWolfError("Request failed")

    def _backoff(self, attempt: int) -> float:
        return self.retry_backoff * (2 ** attempt)

    @staticmethod
    def _parse_retry_after(headers: Dict[str, str]) -> Optional[float]:
        raw = headers.get("retry-after")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _to_error(status: int, headers: Dict[str, str], body: bytes) -> ShotWolfError:
        err_type: Optional[str] = None
        message = "HTTP {}".format(status)
        try:
            data = json.loads(body.decode("utf-8"))
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                err_type = err.get("type")
                message = err.get("message") or message
        except (ValueError, AttributeError):
            pass
        retry_after = ShotWolf._parse_retry_after(headers)
        return ShotWolfError(
            message,
            type=err_type or "unknown",
            status=status,
            request_id=headers.get("x-request-id"),
            retry_after=retry_after,
        )
