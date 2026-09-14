from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.config import settings
from app.scraper import ScrapeError, assert_public_url


async def render_html(url: str) -> tuple[str, str]:
    """Render a public page when httpx is blocked or returned too little extractable content."""
    await assert_public_url(url)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=settings.user_agent)
                await page.goto(url, wait_until="domcontentloaded", timeout=int(settings.request_timeout_secs * 1000))
                await page.wait_for_timeout(500)
                final_url = page.url
                await assert_public_url(final_url)
                return await page.content(), final_url
            finally:
                await browser.close()
    except PlaywrightTimeoutError as error:
        raise ScrapeError("Browser render timed out") from error
    except PlaywrightError as error:
        raise ScrapeError("Browser render failed") from error
