import httpx
import pytest

from app.models import WebsiteScrapeRequest
from app.scraper import (
    FetchFailure,
    extract_page,
    fetch_html,
    looks_blocked_html,
    normalize_crawl_url,
    scrape_website,
    website_collection_state,
)


def test_normalize_crawl_url_deduplicates_fragments_trailing_slash_and_host_case():
    assert normalize_crawl_url("HTTPS://Example.COM/path/") == "https://example.com/path"
    assert normalize_crawl_url("https://example.com/path#section") == "https://example.com/path"
    assert normalize_crawl_url("https://example.com:443/path") == "https://example.com/path"


def test_looks_blocked_html_detects_common_challenge_markers():
    assert looks_blocked_html("<html><body>Just a moment...</body></html>")
    assert not looks_blocked_html("<html><body><p>Article text</p></body></html>")


def test_website_collection_state():
    assert website_collection_state([], [{"url": "https://a", "status": "blocked"}]) == "blocked"
    assert website_collection_state([], [{"url": "https://a", "status": "fetch_error"}]) == "empty"
    assert website_collection_state([extract_page("<html><body><p>x</p></body></html>", "https://a", "text", 1000)], [{"url": "https://a", "status": "returned"}]) == "complete"


def test_extract_page_removes_navigation_and_applies_content_format():
    page = extract_page(
        """
        <html lang='en'><head><title>Article</title><meta name='description' content='Summary'></head>
        <body><nav>Menu links</nav><article><h1>Hello</h1><p>Useful content.</p></article></body></html>
        """,
        "https://example.com/article",
        "markdown",
        1_000,
    )

    assert page.url == "https://example.com/article"
    assert page.title == "Article"
    assert page.description == "Summary"
    assert page.language == "en"
    assert page.markdown is not None
    assert "Useful content" in page.markdown
    assert page.text is None


def test_extract_page_marks_truncated_content():
    page = extract_page(
        "<html><body><article><p>" + "x" * 1_500 + "</p></article></body></html>",
        "https://example.com/article",
        "text",
        1_000,
    )

    assert page.truncated is True
    assert page.total_chars == 1_500
    assert page.text is not None
    assert len(page.text) == 1_000


async def test_fetch_html_marks_http_403_as_blocked(monkeypatch):
    class Response:
        is_redirect = False
        status_code = 403
        headers = {"content-type": "text/html"}

        def raise_for_status(self):
            raise httpx.HTTPStatusError("blocked", request=None, response=self)

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, _url):
            return Response()

    monkeypatch.setattr("app.scraper.httpx.AsyncClient", lambda **kwargs: Client())
    async def public_ok(_url: str) -> None:
        return None

    monkeypatch.setattr("app.scraper.assert_public_url", public_ok)

    with pytest.raises(FetchFailure) as error:
        await fetch_html("https://example.com")
    assert error.value.reason == "blocked"


async def test_scrape_website_reports_seed_outcomes_and_deduplicates_crawl(monkeypatch):
    calls: list[str] = []

    async def fake_fetch(url: str):
        calls.append(url)
        if "example.com/dup" in url:
            return (
                "<html><body><a href='https://example.com/next'>next</a><p>seed one</p></body></html>",
                "https://example.com/dup",
            )
        if url.endswith("/next"):
            return ("<html><body><p>second page</p></body></html>", "https://example.com/next")
        return ("<html><body><p>seed one</p></body></html>", url)

    monkeypatch.setattr("app.scraper.fetch_html", fake_fetch)
    monkeypatch.setattr("app.scraper.settings.browser_fallback", False)

    pages, outcomes, crawl = await scrape_website(
        WebsiteScrapeRequest(
            urls=["https://example.com/dup/", "https://EXAMPLE.com/dup#frag"],
            contentFormat="text",
            maxPages=3,
            maxDepth=1,
        )
    )

    assert len(pages) == 2
    assert outcomes == [
        {"url": "https://example.com/dup/", "status": "returned"},
        {"url": "https://EXAMPLE.com/dup#frag", "status": "returned"},
    ]
    assert crawl == {"visitedCount": 2, "returnedCount": 2, "dedupedSkips": 1}
    assert calls.count("https://example.com/dup/") == 1


async def test_scrape_website_uses_js_rendered_final_url(monkeypatch):
    async def fake_fetch(url: str):
        return ("<html><body><div id='app'></div></body></html>", "https://example.com/landing")

    async def fake_render(url: str):
        assert url == "https://example.com/landing"
        return ("<html><body><article><p>Rendered article body text.</p></article></body></html>", url)

    monkeypatch.setattr("app.scraper.fetch_html", fake_fetch)
    monkeypatch.setattr("app.scraper.settings.browser_fallback", True)
    monkeypatch.setattr("app.browser.render_html", fake_render)

    pages, outcomes, _ = await scrape_website(
        WebsiteScrapeRequest(urls="https://example.com/start", contentFormat="text")
    )

    assert pages[0].text is not None
    assert outcomes == [{"url": "https://example.com/start", "status": "returned", "detail": "js_rendered"}]
