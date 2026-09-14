import httpx
import pytest
from uuid import uuid4

from app.github import GitHubRateLimitError
from app.main import app
from app.models import Page


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_health(client):
    response = await client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_website_uses_compatible_envelope(client, monkeypatch):
    async def fake_scrape(_):
        return [Page(url="https://example.com", markdown="# Example", title="Example")], [
            {"url": "https://example.com", "status": "returned"}
        ]

    monkeypatch.setattr("app.main.scrape_website", fake_scrape)
    response = await client.post(
        "/v1/scrape/website",
        headers={"Idempotency-Key": f"website-test-{uuid4()}"},
        json={"urls": "https://example.com", "contentFormat": "markdown"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["capability"] == "scrape.website"
    assert body["debitMicrousd"] == 0
    assert body["output"] == [{"url": "https://example.com", "markdown": "# Example", "title": "Example"}]
    assert body["urlOutcomes"] == [{"url": "https://example.com", "status": "returned"}]
    assert body["source"]["name"] == "public-website"
    assert body["source"]["urls"] == ["https://example.com"]
    assert body["source"]["collectionState"] == "complete"


async def test_dry_run_does_not_call_scraper(client, monkeypatch):
    async def unexpected_call(_):
        raise AssertionError("scraper must not run during dry run")

    monkeypatch.setattr("app.main.scrape_website", unexpected_call)
    response = await client.post("/v1/scrape/website", json={"urls": "https://example.com", "dryRun": True})

    assert response.status_code == 201
    assert response.json()["status"] == "dry_run"


@pytest.mark.parametrize(("path", "payload"), [
    ("/v1/scrape/twitter/search", {"query": "example"}),
    ("/v1/scrape/instagram/profile", {"usernames": ["example"]}),
    ("/v1/scrape/tiktok/search", {"query": "example"}),
    ("/v1/scrape/facebook/ads", {"query": "example"}),
    ("/v1/scrape/amazon/search", {"query": "example"}),
    ("/v1/scrape/google/places", {"search": "coffee"}),
    ("/v1/email/send", {"to": "person@example.com", "subject": "Hi", "text": "Draft"}),
    ("/v1/seo/rank", {"keyword": "example", "domain": "example.com"}),
    ("/v1/browser/act", {"task": "Find the contact email", "startUrl": "https://example.com"}),
    ("/v1/transcribe/uploads", {"filename": "sample.mp3", "sizeBytes": 10}),
    ("/v1/transcribe", {"uploadId": "local_audio_example.mp3"}),
    ("/v1/scrape/deep", {"query": "Example"}),
    ("/v1/email/domains", {"domain": "example.com"}),
    ("/v1/email/verify", {"email": "person@example.com"}),
])
async def test_local_adapters_support_free_dry_runs(client, path, payload):
    response = await client.post(path, json={**payload, "dryRun": True})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run"
    assert body["debitMicrousd"] == 0


async def test_external_adapters_emit_source_provenance(client, monkeypatch):
    async def fake_search(_, __):
        return [], None

    async def fake_github(_):
        return [{"login": "octocat"}]

    async def fake_places(_):
        return {"places": [{"name": "Coffee"}]}

    monkeypatch.setattr("app.main.search_web", fake_search)
    monkeypatch.setattr("app.main.github_profile", fake_github)
    monkeypatch.setattr("app.main.google_places", fake_places)

    search = await client.post(
        "/v1/search/web", headers={"Idempotency-Key": f"search-test-{uuid4()}"}, json={"query": "coffee"}
    )
    github = await client.post(
        "/v1/scrape/github/profile", headers={"Idempotency-Key": f"github-test-{uuid4()}"}, json={"usernames": ["octocat"]}
    )
    places = await client.post(
        "/v1/scrape/google/places", headers={"Idempotency-Key": f"places-test-{uuid4()}"}, json={"search": "coffee"}
    )

    assert search.json()["source"]["collectionState"] == "empty"
    assert github.json()["source"]["name"] == "github-public-rest"
    assert places.json()["source"]["name"] == "openstreetmap-nominatim"


async def test_github_list_resources_return_normalized_pagination(client, monkeypatch):
    async def fake_list(*_args, **_kwargs):
        return {
            "resourceType": "issue",
            "items": [{"resourceType": "issue", "number": 1, "title": "Example"}],
            "nextPageToken": "2",
        }

    monkeypatch.setattr("app.main.github_list_resource", fake_list)
    response = await client.post(
        "/v1/scrape/github/issues",
        headers={"Idempotency-Key": f"github-issues-{uuid4()}"},
        json={"repository": "octocat/Hello-World", "maxItems": 1},
    )

    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"]["resourceType"] == "issue"
    assert body["output"]["nextPageToken"] == "2"
    assert body["output"]["items"][0]["resourceType"] == "issue"


async def test_github_rate_limit_returns_retryable_error(client, monkeypatch):
    async def rate_limited(*_args, **_kwargs):
        raise GitHubRateLimitError(30)

    monkeypatch.setattr("app.main.github_list_resource", rate_limited)
    response = await client.post(
        "/v1/scrape/github/commits",
        headers={"Idempotency-Key": f"github-rate-{uuid4()}"},
        json={"repository": "octocat/Hello-World", "maxItems": 1},
    )

    body = response.json()
    assert response.status_code == 429
    assert body["error"]["code"] == "github_rate_limited"
    assert body["error"]["retryable"] is True
    assert body["error"]["retryAfterSecs"] == 30


async def test_capabilities_expose_truthful_support_metadata(client):
    response = await client.get("/v1/capabilities")

    assert response.status_code == 200
    capabilities = {item["slug"]: item for item in response.json()["output"]}
    assert capabilities["scrape.github"]["supportLevel"] == "structured"
    assert capabilities["scrape.amazon"]["supportLevel"] == "best_effort"
    assert "structured Amazon" in capabilities["scrape.amazon"]["limitations"][0]


async def test_capabilities_filter_returns_one_capability_with_metadata(client):
    response = await client.get("/v1/capabilities", params={"capability": "email.verify"})

    assert response.status_code == 200
    assert response.json()["output"] == {
        "slug": "email.verify",
        "supportLevel": "unavailable",
        "adapter": "syntax-check",
        "limitations": ["Mailbox deliverability verification is not implemented."],
        "evaluationSuite": "contact",
    }


async def test_email_draft_is_persisted_without_smtp(client):
    response = await client.post(
        "/v1/email/send",
        headers={"Idempotency-Key": f"email-test-{uuid4()}"},
        json={"to": "person@example.com", "subject": "Hi", "text": "Draft", "send": False},
    )

    assert response.status_code == 200
    assert response.json()["output"]["draft"]["draftId"].startswith("local_draft_")
