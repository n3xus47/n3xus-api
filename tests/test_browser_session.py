from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.browser_session import BrowserSessionNotReady
from app.main import app
from app.models import Page


@pytest.fixture
async def client():
    import httpx

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_browser_session_create_uses_idempotency_and_does_not_return_storage_state(client, monkeypatch):
    manager = AsyncMock()
    manager.create.return_value = {
        "sessionId": "local_browser_session_0123456789abcdef0123456789abcdef",
        "startUrl": "https://example.com/login",
        "currentUrl": "https://example.com/login",
        "status": "awaiting_operator",
        "ready": False,
    }
    monkeypatch.setattr("app.main.browser_sessions", manager)
    key = f"browser-session-test-{uuid4()}"

    response = await client.post(
        "/v1/browser/sessions",
        headers={"Idempotency-Key": key},
        json={"startUrl": "https://example.com/login"},
    )

    assert response.status_code == 201
    assert response.json()["output"]["sessionId"].startswith("local_browser_session_")
    assert "cookies" not in response.json()["output"]
    manager.create.assert_awaited_once_with("https://example.com/login")


async def test_website_scrape_passes_explicit_browser_session(client, monkeypatch):
    manager = AsyncMock()
    manager.require_ready.return_value = object()
    monkeypatch.setattr("app.main.browser_sessions", manager)

    async def fake_scrape(request):
        assert request.browser_session_id == "local_browser_session_0123456789abcdef0123456789abcdef"
        return [Page(url="https://example.com/private", text="Logged-in content")], [
            {"url": "https://example.com/private", "status": "returned", "detail": "js_rendered"}
        ], None

    monkeypatch.setattr("app.main.scrape_website", fake_scrape)
    response = await client.post(
        "/v1/scrape/website",
        headers={"Idempotency-Key": f"session-scrape-{uuid4()}"},
        json={
            "urls": "https://example.com/private",
            "contentFormat": "text",
            "browserSessionId": "local_browser_session_0123456789abcdef0123456789abcdef",
        },
    )

    assert response.status_code == 201
    assert response.json()["output"][0]["text"] == "Logged-in content"
    manager.require_ready.assert_awaited_once()


async def test_resume_uses_session_current_url_when_urls_omitted(client, monkeypatch):
    manager = AsyncMock()
    manager.get.return_value = {"currentUrl": "https://example.com/private"}
    manager.require_ready.return_value = object()
    monkeypatch.setattr("app.main.browser_sessions", manager)

    async def fake_scrape(request):
        assert request.url_list() == ["https://example.com/private"]
        assert request.browser_session_id == "local_browser_session_0123456789abcdef0123456789abcdef"
        return [Page(url="https://example.com/private", text="Content")], [
            {"url": "https://example.com/private", "status": "returned", "detail": "js_rendered"}
        ], None

    monkeypatch.setattr("app.main.scrape_website", fake_scrape)
    response = await client.post(
        "/v1/browser/sessions/local_browser_session_0123456789abcdef0123456789abcdef/resume",
        headers={"Idempotency-Key": f"session-resume-{uuid4()}"},
        json={"contentFormat": "text"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"


async def test_website_scrape_reports_session_not_ready(client, monkeypatch):
    manager = AsyncMock()
    manager.require_ready.side_effect = BrowserSessionNotReady(
        "local_browser_session_0123456789abcdef0123456789abcdef"
    )
    monkeypatch.setattr("app.main.browser_sessions", manager)
    response = await client.post(
        "/v1/scrape/website",
        headers={"Idempotency-Key": f"session-not-ready-{uuid4()}"},
        json={
            "urls": "https://example.com/private",
            "browserSessionId": "local_browser_session_0123456789abcdef0123456789abcdef",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "browser_session_not_ready"
