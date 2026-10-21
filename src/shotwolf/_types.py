"""Type hints mirroring config/openapi.yaml (ShotWolf API v1.0.0).

These are lightweight ``TypedDict`` / ``Literal`` aliases for editor support
and static checking. At runtime the client passes dicts straight through and
returns parsed JSON dicts - nothing here is enforced.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:  # Literal / TypedDict are in typing on 3.8+, fall back just in case
    from typing import Literal, TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import Literal, TypedDict  # type: ignore

Device = Literal["default", "iphone_15_pro", "pixel_8_pro", "macbook_air", "ipad_pro_12_9"]
ImageFormat = Literal["png", "jpg", "jpeg", "webp"]
CaptureFormat = Literal["png", "jpg", "jpeg", "webp", "gif", "mp4"]
MockupFrame = Literal[
    "iphone_15_pro",
    "pixel_8_pro",
    "macbook_air",
    "ipad_pro_12_9",
    "browser_macos",
    "browser_chrome",
    "instagram_post",
    "instagram_profile",
    "facebook_ad",
    "google_display_ad",
    "linkedin_ad",
]
MockupBg = Literal["black", "white", "grey", "lime", "orange", "blue", "pink", "purple", "gradient"]
OgTemplate = Literal["blog_card", "product_card", "quote_card", "minimal"]
PageFormat = Literal[
    "Letter", "Legal", "Tabloid", "Ledger", "A0", "A1", "A2", "A3", "A4", "A5", "A6"
]
Tier = Literal["cub", "pup", "wolf", "alpha", "pack"]


class CaptureParams(TypedDict, total=False):
    """At least one of ``url`` or ``html`` is required (mutually exclusive)."""

    url: str
    html: str
    device: Device
    format: CaptureFormat
    full_page: bool
    dark_mode: bool
    delay_ms: int
    wait_for_selector: str
    block_ads: bool
    block_cookies: bool
    dismiss_cookies: bool
    block_trackers: bool
    selector: str
    user_agent: str
    quality: int
    cache_ttl: int
    webhook_url: str
    on_action_error: Literal["fail", "continue"]
    duration: int
    fps: Literal[10, 15, 24]
    scroll: Literal["smooth", "none", "steps"]
    actions: List[Dict[str, Any]]
    storage: Literal["s3"]
    storage_endpoint: str
    storage_bucket: str
    storage_key: str
    storage_access_key_id: str
    storage_secret_access_key: str
    storage_region: str
    storage_acl: Literal["private", "public-read"]
    storage_class: str


class BatchParams(TypedDict, total=False):
    url: str
    devices: List[Device]
    format: ImageFormat
    full_page: bool
    dark_mode: bool
    delay_ms: int


class MockupParams(TypedDict, total=False):
    url: str
    frame: MockupFrame
    bg: MockupBg
    format: ImageFormat
    full_page: bool
    dark_mode: bool
    delay_ms: int


class OgParams(TypedDict, total=False):
    template: OgTemplate
    variables: Dict[str, str]
    format: ImageFormat


class PdfParams(TypedDict, total=False):
    url: str
    html: str
    page_format: PageFormat
    landscape: bool
    print_background: bool
    scale: float
    delay_ms: int
    margin: Dict[str, str]


class DiffParams(TypedDict, total=False):
    before_url: str
    after_url: str
    before_image_url: str
    after_image_url: str
    before_screenshot_id: int
    after_screenshot_id: int
    device: Device
    full_page: bool
    dark_mode: bool
    delay_ms: int
    wait_for_selector: str
    threshold: float
    include_aa_in_diff: bool
    ignore_regions: List[Dict[str, int]]


# Responses are returned as plain dicts; these document the shape.
CaptureResponse = Dict[str, Any]
BatchResponse = Dict[str, Any]
DiffResponse = Dict[str, Any]
AccountResponse = Dict[str, Any]

__all__ = [
    "Device",
    "ImageFormat",
    "CaptureFormat",
    "MockupFrame",
    "MockupBg",
    "OgTemplate",
    "PageFormat",
    "Tier",
    "CaptureParams",
    "BatchParams",
    "MockupParams",
    "OgParams",
    "PdfParams",
    "DiffParams",
    "CaptureResponse",
    "BatchResponse",
    "DiffResponse",
    "AccountResponse",
]
