import http.server
import json
import threading

import pytest

from shotwolf import ShotWolf, ShotWolfError, ShotWolfTimeoutError
from shotwolf._client import _urllib_transport


def fake_transport(responses):
    """Return (transport, calls). Each response: dict(status=, body=, headers=)."""
    calls = []
    state = {"i": 0}

    def transport(method, url, headers, body, timeout):
        calls.append({"method": method, "url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        spec = responses[min(state["i"], len(responses) - 1)]
        state["i"] += 1
        if spec.get("raise"):
            raise spec["raise"]
        payload = spec.get("body")
        raw = b"" if payload is None else json.dumps(payload).encode("utf-8")
        return spec["status"], spec.get("headers", {}), raw

    return transport, calls


def client(responses, **kw):
    transport, calls = fake_transport(responses)
    kw.setdefault("retry_backoff", 0)
    sw = ShotWolf("sw_live_test", transport=transport, **kw)
    return sw, calls


# --- construction --------------------------------------------------------

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("SHOTWOLF_API_KEY", raising=False)
    with pytest.raises(ShotWolfError):
        ShotWolf(transport=lambda *a: (200, {}, b"{}"))


def test_reads_env_key(monkeypatch):
    monkeypatch.setenv("SHOTWOLF_API_KEY", "sw_live_env")
    transport, calls = fake_transport([{"status": 200, "body": {"balance_cr": 5}}])
    ShotWolf(transport=transport).account()
    assert calls[0]["headers"]["Authorization"] == "Bearer sw_live_env"


# --- capture -------------------------------------------------------------

def test_capture_posts_json_and_returns_body():
    sw, calls = client([{"status": 201, "body": {"id": 42, "status": "done", "image_url": "https://cdn/x.png"}}])
    res = sw.capture(url="https://example.com", full_page=True)

    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://shotwolf.com/api/v1/captures"
    assert calls[0]["headers"]["Authorization"] == "Bearer sw_live_test"
    assert calls[0]["headers"]["Content-Type"] == "application/json"
    assert json.loads(calls[0]["body"]) == {"url": "https://example.com", "full_page": True}
    assert res == {"id": 42, "status": "done", "image_url": "https://cdn/x.png"}


def test_custom_base_url():
    sw, calls = client([{"status": 201, "body": {"id": 1}}], base_url="http://localhost:6300/")
    sw.capture(url="https://e.com")
    assert calls[0]["url"] == "http://localhost:6300/api/v1/captures"


def test_idempotency_key_header():
    sw, calls = client([{"status": 201, "body": {"id": 1}}])
    sw.capture(url="https://e.com", idempotency_key="abc-123")
    assert calls[0]["headers"]["Idempotency-Key"] == "abc-123"


# --- errors --------------------------------------------------------------

def test_error_envelope_raises():
    sw, _ = client([{"status": 402, "body": {"error": {"type": "insufficient_credits", "message": "Broke"}}}])
    with pytest.raises(ShotWolfError) as exc:
        sw.capture(url="https://e.com")
    assert exc.value.type == "insufficient_credits"
    assert exc.value.status == 402
    assert exc.value.message == "Broke"


def test_error_carries_request_id():
    sw, _ = client([{"status": 400, "body": {"error": {"type": "invalid_params", "message": "bad"}}, "headers": {"x-request-id": "req_9"}}])
    with pytest.raises(ShotWolfError) as exc:
        sw.capture(url="x")
    assert exc.value.request_id == "req_9"


# --- retries -------------------------------------------------------------

def test_retries_on_429_then_succeeds():
    sw, calls = client([
        {"status": 429, "body": {"error": {"type": "rate_limited", "message": "slow"}}},
        {"status": 201, "body": {"id": 7, "status": "done"}},
    ])
    res = sw.capture(url="https://e.com")
    assert len(calls) == 2
    assert res["id"] == 7


def test_gives_up_after_max_retries():
    sw, calls = client([{"status": 503, "body": {"error": {"type": "render_failed", "message": "down"}}}], max_retries=1)
    with pytest.raises(ShotWolfError) as exc:
        sw.capture(url="https://e.com")
    assert exc.value.status == 503
    assert len(calls) == 2


def test_no_retry_on_400():
    sw, calls = client([{"status": 400, "body": {"error": {"type": "invalid_params", "message": "no"}}}])
    with pytest.raises(ShotWolfError):
        sw.capture(url="x")
    assert len(calls) == 1


def test_retries_on_transport_error():
    sw, calls = client([
        {"status": 0, "raise": OSError("boom")},
        {"status": 201, "body": {"id": 3}},
    ])
    res = sw.capture(url="https://e.com")
    assert res["id"] == 3
    assert len(calls) == 2


# --- get_screenshot + wait_for ------------------------------------------

def test_get_screenshot_is_get_no_body():
    sw, calls = client([{"status": 200, "body": {"id": 5, "status": "queued"}}])
    sw.get_screenshot(5)
    assert calls[0]["url"] == "https://shotwolf.com/api/v1/screenshots/5"
    assert calls[0]["method"] == "GET"
    assert calls[0]["body"] is None


def test_wait_for_polls_until_done():
    sw, calls = client([
        {"status": 200, "body": {"id": 5, "status": "processing"}},
        {"status": 200, "body": {"id": 5, "status": "processing"}},
        {"status": 200, "body": {"id": 5, "status": "done", "image_url": "https://cdn/y.png"}},
    ])
    res = sw.wait_for(5, interval=0.001, timeout=5)
    assert res["status"] == "done"
    assert len(calls) == 3


def test_wait_for_raises_on_failed():
    sw, _ = client([{"status": 200, "body": {"id": 5, "status": "failed"}}])
    with pytest.raises(ShotWolfError) as exc:
        sw.wait_for(5, interval=0.001, timeout=5)
    assert exc.value.type == "render_failed"


def test_wait_for_times_out():
    sw, _ = client([{"status": 200, "body": {"id": 5, "status": "processing"}}])
    with pytest.raises(ShotWolfTimeoutError):
        sw.wait_for(5, interval=0.01, timeout=0.001)


# --- other endpoints -----------------------------------------------------

@pytest.mark.parametrize("method,kwargs,path", [
    ("mockup", {"url": "https://e.com", "frame": "iphone_15_pro"}, "https://shotwolf.com/api/v1/mockups"),
    ("og", {"template": "blog_card"}, "https://shotwolf.com/api/v1/og"),
    ("pdf", {"url": "https://e.com"}, "https://shotwolf.com/api/v1/pdf"),
    ("diff", {"before_url": "https://a.com", "after_url": "https://b.com"}, "https://shotwolf.com/api/v1/diffs"),
    ("batch", {"url": "https://e.com", "devices": ["default", "iphone_15_pro"]}, "https://shotwolf.com/api/v1/capture/batch"),
    ("capture_async", {"url": "https://e.com"}, "https://shotwolf.com/api/v1/captures/async"),
])
def test_endpoint_paths(method, kwargs, path):
    sw, calls = client([{"status": 201, "body": {"id": 1}}])
    getattr(sw, method)(**kwargs)
    assert calls[0]["url"] == path


def test_account_get():
    sw, calls = client([{"status": 200, "body": {"email_address": "a@b.co", "balance_cr": 5}}])
    acc = sw.account()
    assert calls[0]["url"] == "https://shotwolf.com/api/v1/account"
    assert acc["balance_cr"] == 5


# urllib follows redirects by default and carries every header to the new host,
# Authorization included - so one 30x anywhere in the chain hands the
# customer's sw_live_... key to whoever answered. The other three SDKs are
# clean: PHP never sets FOLLOWLOCATION, Net::HTTP does not follow at all, and
# fetch strips the header itself on a cross-origin redirect. This runs two real
# servers rather than a stub, because the behaviour under test lives inside
# urllib and a stub would only test the stub.
class _Redirector(http.server.BaseHTTPRequestHandler):
    target = ""

    def do_POST(self):
        self.send_response(302)
        self.send_header("Location", self.target)
        self.end_headers()

    def log_message(self, *args):
        pass


class _Destination(http.server.BaseHTTPRequestHandler):
    seen = []

    def _record(self):
        _Destination.seen.append(dict(self.headers))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    # urllib turns a followed POST into a GET, so both have to be recorded or
    # the test would miss the very thing it is watching for.
    do_POST = _record
    do_GET = _record

    def log_message(self, *args):
        pass


def _serve(handler):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_transport_does_not_carry_the_key_through_a_redirect():
    _Destination.seen = []
    destination = _serve(_Destination)
    _Redirector.target = f"http://127.0.0.1:{destination.server_port}/"
    redirector = _serve(_Redirector)

    try:
        status, headers, _body = _urllib_transport(
            "POST",
            f"http://127.0.0.1:{redirector.server_port}/api/v1/captures",
            {"Authorization": "Bearer sw_live_secret", "Content-Type": "application/json"},
            b"{}",
            5.0,
        )
    finally:
        redirector.shutdown()
        destination.shutdown()

    assert _Destination.seen == [], "the api key was sent to the redirect target"
    assert status == 302
    assert headers["location"].startswith("http://127.0.0.1:")
