import httpx
import pytest
from uuid import uuid4

from app.config import settings
from app.main import app
from app.meta_ads import MetaAdsError, normalize_ad, search_ads

SAMPLE_ROW = {
    "id": "1234567890",
    "ad_creation_time": "2024-01-01",
    "ad_delivery_start_time": "2024-01-02",
    "ad_delivery_stop_time": "2024-01-31",
    "ad_creative_bodies": ["Buy now"],
    "ad_creative_link_titles": ["Example"],
    "ad_creative_link_descriptions": ["Details"],
    "ad_creative_link_captions": ["example.com"],
    "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=1234567890",
    "page_id": "42",
    "page_name": "Example Page",
    "publisher_platforms": ["facebook", "instagram"],
    "eu_total_reach": 1000,
}


def test_normalize_ad_maps_public_fields():
    ad = normalize_ad(SAMPLE_ROW)
    assert ad["id"] == "1234567890"
    assert ad["copy"]["bodies"] == ["Buy now"]
    assert ad["creative"]["snapshotUrl"].startswith("https://")
    assert ad["landingUrl"] is None
    assert ad["dates"]["deliveryStart"] == "2024-01-02"
    assert ad["platforms"] == ["facebook", "instagram"]
    assert ad["transparency"]["eu_total_reach"] == 1000
    assert "1234567890" in ad["libraryUrl"]


async def test_search_ads_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "meta_ads_access_token", None)
    with pytest.raises(MetaAdsError):
        await search_ads({"query": "coffee"})


async def test_search_ads_parses_graph_response(monkeypatch):
    monkeypatch.setattr(settings, "meta_ads_access_token", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/ads_archive")
        assert request.url.params["search_terms"] == "coffee"
        assert request.url.params["ad_reached_countries"] == "US"
        return httpx.Response(200, json={"data": [SAMPLE_ROW], "paging": {"cursors": {"after": "cursor-1"}}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        kwargs["transport"] = transport
        return original_client(**kwargs)

    monkeypatch.setattr("app.meta_ads.httpx.AsyncClient", client_factory)
    result = await search_ads({"query": "coffee", "maxItems": 5})
    assert len(result["ads"]) == 1
    assert result["ads"][0]["copy"]["bodies"] == ["Buy now"]
    assert result["nextPageToken"] == "cursor-1"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_facebook_ads_endpoint_returns_structured_envelope(client, monkeypatch):
    monkeypatch.setattr(settings, "meta_ads_access_token", "test-token")

    async def fake_search(_):
        return {"ads": [normalize_ad(SAMPLE_ROW)], "nextPageToken": None}

    monkeypatch.setattr("app.public_sources.search_ads", fake_search)
    response = await client.post(
        "/v1/scrape/facebook/ads",
        headers={"Idempotency-Key": f"meta-ads-{uuid4()}"},
        json={"query": "coffee", "countries": ["US"]},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "succeeded"
    assert body["capability"] == "scrape.facebook.ads"
    assert body["source"]["name"] == "meta-ads-library-api"
    assert body["output"]["ads"][0]["platforms"] == ["facebook", "instagram"]
