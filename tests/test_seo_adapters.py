import httpx
import pytest

from app.main import app
from app.models import SearchResult
from app.seo_adapters import (
    APPROVED_ADAPTER_IDS,
    DEFAULT_SERP_ADAPTER_ID,
    METRICS_UNAVAILABLE_REASON,
    STRATEGY_DOC,
    competitors,
    keyword_metrics,
    list_adapters,
    rank,
)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


def test_registry_marks_single_approved_serp_adapter():
    adapters = list_adapters()
    approved = [item for item in adapters if item["approval"] == "approved"]
    assert len(approved) == 1
    assert approved[0]["id"] == DEFAULT_SERP_ADAPTER_ID
    assert DEFAULT_SERP_ADAPTER_ID in APPROVED_ADAPTER_IDS


def test_keyword_metrics_never_invent_commercial_fields():
    payload = keyword_metrics(["coffee shop", "espresso"])
    assert payload["adapterId"] is None
    assert payload["policy"]["commercialMetricsApproved"] is False
    assert payload["policy"]["documentation"] == STRATEGY_DOC
    for row in payload["keywords"]:
        assert row["monthlySearches"] is None
        assert row["cpc"] is None
        assert row["difficulty"] is None
        assert row["intent"] is None
        assert row["trend"] is None
        assert row["metricsSource"] is None
        assert row["metricsUnavailableReason"] == METRICS_UNAVAILABLE_REASON


async def test_rank_uses_approved_adapter(monkeypatch):
    sample = [
        SearchResult(title="Example", url="https://www.example.com/page", snippet="hi"),
        SearchResult(title="Other", url="https://other.test/", snippet=None),
    ]

    async def fake_search(_query: str, _max: int):
        return sample, None

    monkeypatch.setattr("app.seo_adapters.search_web", fake_search)
    result = await rank("example", "example.com", 10)
    assert result["adapterId"] == DEFAULT_SERP_ADAPTER_ID
    assert result["position"] == 1
    assert len(result["results"]) == 2


async def test_rank_rejects_unapproved_adapter():
    with pytest.raises(ValueError, match="not approved"):
        await rank("x", "example.com", 5, adapter_id="serpapi-organic")


async def test_competitors_keep_overlap_metrics_null(monkeypatch):
    sample = [
        SearchResult(title="A", url="https://competitor.test/a", snippet=None),
        SearchResult(title="B", url="https://example.com/b", snippet=None),
    ]

    async def fake_search(_query: str, _max: int):
        return sample, None

    monkeypatch.setattr("app.seo_adapters.search_web", fake_search)
    result = await competitors("example.com", 5)
    assert result["adapterId"] == DEFAULT_SERP_ADAPTER_ID
    assert len(result["competitors"]) == 1
    row = result["competitors"][0]
    assert row["sharedKeywords"] is None
    assert row["gapKeywords"] is None
    assert row["overlapUnavailableReason"] == METRICS_UNAVAILABLE_REASON


async def test_seo_keyword_endpoint_exposes_policy(client):
    response = await client.post(
        "/v1/seo/keyword",
        json={"keywords": ["test"], "dryRun": True},
        headers={"Idempotency-Key": "seo-keyword-dry"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dry_run"
