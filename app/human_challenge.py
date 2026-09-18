"""Human-in-the-loop CAPTCHA and login detection.

The API never fills credentials or solves puzzles. The short-lived fallback
opens a headed browser and waits for the gate to clear; explicit, reusable
operator sessions live in :mod:`app.browser_session`.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from bs4 import BeautifulSoup

from app.config import settings
from app.scraper import looks_blocked_html

PROFILE_LOCK = asyncio.Lock()


def looks_like_human_gate(html: str, page_url: str | None = None) -> bool:
    if not isinstance(html, str):
        return False
    if looks_blocked_html(html, page_url):
        return True
    lowered = html.lower()
    if "robot check" in lowered or "validatecaptcha" in lowered:
        return True
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one('input[type="password"]'))


async def wait_until_cleared(page, *, timeout_secs: float, poll_secs: float = 1.0) -> str:
    """Poll until the visible page is no longer a CAPTCHA or login gate."""
    deadline = time.monotonic() + timeout_secs
    html = await page.content()
    while looks_like_human_gate(html, getattr(page, "url", None)):
        if time.monotonic() >= deadline:
            raise TimeoutError("Human challenge was not completed in time")
        await asyncio.sleep(poll_secs)
        html = await page.content()
    return html


def profile_dir() -> Path:
    path = Path(settings.data_dir) / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def chromium_args(*, headless: bool) -> list[str]:
    args = ["--disable-dev-shm-usage"]
    if Path("/.dockerenv").exists():
        args.append("--no-sandbox")
        if not headless:
            # Docker X11 has no GPU; default Chromium compositing paints a black window.
            args.extend(
                [
                    "--disable-gpu",
                    "--disable-gpu-compositing",
                    "--disable-accelerated-2d-canvas",
                    "--ozone-platform=x11",
                ]
            )
    return args


async def open_persistent_page(playwright, url: str, *, headless: bool):
    context = await playwright.chromium.launch_persistent_context(
        str(profile_dir()),
        headless=headless,
        args=chromium_args(headless=headless),
        user_agent=settings.user_agent,
        viewport={"width": 1280, "height": 900},
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=int(settings.request_timeout_secs * 1000))
    await page.wait_for_timeout(400)
    return context, page
