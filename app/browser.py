from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.config import settings
from app.human_challenge import (
    PROFILE_LOCK,
    looks_like_human_gate,
    open_persistent_page,
    wait_until_cleared,
)
from app.scraper import FetchFailure, ScrapeError, assert_public_url


async def render_html(url: str) -> tuple[str, str]:
    """Render a public page when httpx is blocked or returned too little extractable content."""
    await assert_public_url(url)
    try:
        async with PROFILE_LOCK:
            async with async_playwright() as playwright:
                html, final_url = await _load(playwright, url, headless=True)
                if looks_like_human_gate(html, final_url) and settings.human_challenge:
                    html, final_url = await _load(playwright, url, headless=False, wait_human=True)
                if looks_like_human_gate(html, final_url):
                    raise FetchFailure("blocked", "Blocked or challenge page detected")
                return html, final_url
    except TimeoutError as error:
        raise FetchFailure("blocked", "Human challenge was not completed in time") from error
    except PlaywrightTimeoutError as error:
        raise ScrapeError("Browser render timed out") from error
    except PlaywrightError as error:
        raise ScrapeError("Browser render failed") from error


async def _load(playwright, url: str, *, headless: bool, wait_human: bool = False) -> tuple[str, str]:
    context, page = await open_persistent_page(playwright, url, headless=headless)
    try:
        if wait_human:
            html = await wait_until_cleared(page, timeout_secs=settings.human_challenge_timeout_secs)
        else:
            html = await page.content()
        final_url = page.url
        await assert_public_url(final_url)
        return html, final_url
    finally:
        await context.close()
