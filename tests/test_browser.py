from unittest.mock import AsyncMock, MagicMock

from app.browser import render_html


async def test_render_html_opens_headed_wait_when_headless_shows_captcha(monkeypatch):
    monkeypatch.setattr("app.browser.assert_public_url", AsyncMock())
    monkeypatch.setattr("app.browser.settings.human_challenge", True)

    loads = [
        ("<html><body>Just a moment...</body></html>", "https://example.com/a"),
        (
            "<html><body><article><p>Hypertext Transfer Protocol is documented here.</p></article></body></html>",
            "https://example.com/a",
        ),
    ]
    seen: list[tuple[bool, bool]] = []

    async def fake_load(_playwright, _url, *, headless, wait_human=False):
        seen.append((headless, wait_human))
        return loads.pop(0)

    monkeypatch.setattr("app.browser._load", fake_load)
    playwright = MagicMock()
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.browser.async_playwright", lambda: playwright)

    html, url = await render_html("https://example.com/a")
    assert "Hypertext Transfer Protocol" in html
    assert url.endswith("/a")
    assert seen == [(True, False), (False, True)]
