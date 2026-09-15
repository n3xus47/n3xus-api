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


def test_looks_blocked_html_does_not_flag_wikipedia_captcha_in_csp():
    html = """
    <html><head><meta http-equiv="Content-Security-Policy" content="script-src captcha.example"></head>
    <body><div id="mw-content-text"><p>Hypertext Transfer Protocol (HTTP) is an application layer protocol.</p></div></body></html>
    """
    assert not looks_blocked_html(html, "https://en.wikipedia.org/wiki/HTTP")


def test_website_collection_state():
    assert website_collection_state([], [{"url": "https://a", "status": "blocked"}]) == "blocked"
    assert website_collection_state([], [{"url": "https://a", "status": "fetch_error"}]) == "empty"
    assert website_collection_state([extract_page("<html><body><p>x</p></body></html>", "https://a", "text", 1000)], [{"url": "https://a", "status": "returned"}]) == "complete"


def test_extract_page_prefers_full_main_over_thin_readability_snippet():
    html = """
    <html lang='en'><head><title>RFC Editor</title></head>
    <body>
      <div id="sidebar">Cookie banner</div>
      <main>
        <h1>Request for Comments</h1>
        <p>The RFC Editor publishes RFCs and related documents for the IETF.</p>
        <p>Search the RFC series, errata, and publication process here.</p>
      </main>
    </body></html>
    """
    page = extract_page(html, "https://www.rfc-editor.org/", "text", 50_000)
    assert page.title == "RFC Editor"
    assert "IETF" in (page.text or "")
    assert len(page.text or "") > 80


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


async def test_fetch_html_uses_html_body_when_redirect_has_no_location(monkeypatch):
    class Response:
        is_redirect = True
        status_code = 300
        headers = {"content-type": "text/html"}
        text = "<html><head><title>Choices</title></head><body><p>Mirror list for dummy file.</p></body></html>"
        url = "https://www.w3.org/dummy.html"

        def raise_for_status(self):
            return None

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

    html, final = await fetch_html("https://www.w3.org/dummy.html")
    assert "Mirror list" in html
    assert final.endswith("dummy.html")


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


async def test_scrape_website_playwright_fallback_when_httpx_blocked(monkeypatch):
    wiki_html = """
    <html lang='en'><head><title>HTTP - Wikipedia</title></head>
    <body><main><h1>Hypertext Transfer Protocol</h1>
    <p>HTTP is an application layer protocol for distributed hypermedia information systems.</p></main></body></html>
    """

    async def fake_fetch(_url: str):
        raise FetchFailure("blocked", "HTTP 403")

    async def fake_render(url: str):
        assert url == "https://en.wikipedia.org/wiki/HTTP"
        return (wiki_html, url)

    monkeypatch.setattr("app.scraper.fetch_html", fake_fetch)
    monkeypatch.setattr("app.scraper.settings.browser_fallback", True)
    monkeypatch.setattr("app.browser.render_html", fake_render)

    pages, outcomes, _ = await scrape_website(
        WebsiteScrapeRequest(urls="https://en.wikipedia.org/wiki/HTTP", contentFormat="text")
    )

    assert len(pages) == 1
    assert "Hypertext Transfer Protocol" in (pages[0].text or "")
    assert outcomes == [
        {"url": "https://en.wikipedia.org/wiki/HTTP", "status": "returned", "detail": "js_rendered"}
    ]


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
