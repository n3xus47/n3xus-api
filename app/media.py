"""Fetch small public media resources for local, auditable import pipelines."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx

from app.config import settings
from app.scraper import BLOCKED_HTTP_STATUSES, FetchFailure, assert_public_url

MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


async def fetch_public_image(url: str) -> tuple[bytes, str, str]:
    """Fetch one public image while preserving SSRF and redirect protections."""

    current_url = url
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_secs,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "image/avif,image/webp,image/apng,image/*;q=0.8",
        },
        follow_redirects=False,
    ) as client:
        for _ in range(6):
            await assert_public_url(current_url)
            response = await client.get(current_url)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise FetchFailure("fetch_error", "Redirect has no location")
                current_url = urljoin(current_url, location)
                continue
            if response.status_code in BLOCKED_HTTP_STATUSES:
                raise FetchFailure("blocked", f"HTTP {response.status_code}")
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type == "application/octet-stream":
                suffix = urlparse(str(response.url)).path.lower().rsplit(".", 1)[-1]
                content_type = {
                    "avif": "image/avif",
                    "gif": "image/gif",
                    "jpeg": "image/jpeg",
                    "jpg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp",
                }.get(suffix, content_type)
            if content_type not in ALLOWED_IMAGE_TYPES:
                raise FetchFailure("non_image", "URL did not return a supported image")
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_IMAGE_BYTES:
                raise FetchFailure("too_large", "Image exceeds the 15 MB limit")
            body = response.content
            if not body:
                raise FetchFailure("empty", "Image response was empty")
            if len(body) > MAX_IMAGE_BYTES:
                raise FetchFailure("too_large", "Image exceeds the 15 MB limit")
            return body, content_type, str(response.url)
    raise FetchFailure("fetch_error", "Too many redirects")
