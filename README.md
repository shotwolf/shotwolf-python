# ShotWolf Python SDK

Official Python client for the [ShotWolf](https://shotwolf.com) API - capture screenshots, render device mockups, generate Open Graph cards, convert HTML to PDF, and run pixel-level visual regression diffs through a single JSON HTTP API.

- Zero dependencies (standard-library only, Python 3.8+)
- Typed (ships `py.typed`, `TypedDict` params and `Literal` enums)
- Built-in retries with backoff, idempotency keys, and an async polling helper

## Install

```bash
pip install shotwolf
```

## Quick start

Get an API key at [shotwolf.com/dashboard/api_keys](https://shotwolf.com/dashboard/api_keys).

```python
from shotwolf import ShotWolf

sw = ShotWolf()  # reads SHOTWOLF_API_KEY, or pass ShotWolf("sw_live_...")

shot = sw.capture(url="https://example.com", full_page=True, dismiss_cookies=True)
print(shot["image_url"])
```

## Usage

### Screenshots

```python
# Sync - returns the image URL inline (~1-4s)
shot = sw.capture(url="https://stripe.com", device="iphone_15_pro")

# Async - queue and poll (or pass webhook_url for a callback)
queued = sw.capture_async(url="https://stripe.com")
done = sw.wait_for(queued["id"])  # polls until status is done

# Batch - one page, many viewports (cheaper than N calls)
batch = sw.batch(url="https://stripe.com", devices=["default", "iphone_15_pro", "ipad_pro_12_9"])
```

### Device & social mockups

```python
mockup = sw.mockup(url="https://stripe.com", frame="macbook_air", bg="gradient")
```

### Open Graph cards

```python
og = sw.og(template="blog_card", variables={"title": "Ship faster", "author": "Jane Doe"})
```

### HTML / URL to PDF

```python
pdf = sw.pdf(html="<h1>Invoice #42</h1>", page_format="A4", print_background=True)
```

### Visual regression diff

```python
diff = sw.diff(
    before_url="https://staging.example.com",
    after_url="https://example.com",
    ignore_regions=[{"x": 0, "y": 0, "width": 1280, "height": 80}],  # mask a dynamic header
)
if not diff["passed"]:
    print(f"{diff['diff_ratio'] * 100:.2f}% changed", diff["diff_image_url"])
```

### Account balance

```python
account = sw.account()
print(account["balance_cr"], account["tier"]["name"])
```

## Idempotency

Pass `idempotency_key` to make money-charging POSTs safe to retry. A repeat with
the same key and body within 24h replays the original response instead of
charging again.

```python
import uuid
sw.capture(url="https://example.com", idempotency_key=str(uuid.uuid4()))
```

## Error handling

Any non-2xx response raises `ShotWolfError` carrying the API error `type`, HTTP
`status`, and `message`.

```python
from shotwolf import ShotWolfError

try:
    sw.capture(url="https://example.com")
except ShotWolfError as err:
    if err.type == "insufficient_credits":
        ...  # top up at https://shotwolf.com/pricing
    print(err.status, err.type, err.message, err.request_id)
```

## Configuration

```python
sw = ShotWolf(
    "sw_live_xxx",
    base_url="https://shotwolf.com",  # override for self-host / testing
    timeout=60.0,                     # per-request timeout in seconds
    max_retries=2,                    # retries on 429 / 5xx
    retry_backoff=0.5,                # base backoff, doubled per attempt
)
```

Retries honor the `Retry-After` header on `429` responses. `4xx` responses
other than `429` are never retried.

## API coverage

| Method | Endpoint |
| --- | --- |
| `capture(**params)` | `POST /api/v1/captures` |
| `capture_async(**params)` | `POST /api/v1/captures/async` |
| `batch(**params)` | `POST /api/v1/capture/batch` |
| `mockup(**params)` | `POST /api/v1/mockups` |
| `og(**params)` | `POST /api/v1/og` |
| `pdf(**params)` | `POST /api/v1/pdf` |
| `diff(**params)` | `POST /api/v1/diffs` |
| `get_screenshot(id)` | `GET /api/v1/screenshots/:id` |
| `wait_for(id)` | polls `get_screenshot` until `done`/`failed` |
| `account()` | `GET /api/v1/account` |

Full parameter reference: [shotwolf.com/docs](https://shotwolf.com/docs).

## License

MIT
