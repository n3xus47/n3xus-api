import json
from pathlib import Path

import httpx
import pytest

from app.capabilities import get_capability
from app.evaluate import evaluate, render_report, validate_cases

M1_SUITES = ("website", "search", "github", "youtube", "research", "places", "amazon", "social", "seo")


def case(**changes):
    return {"id": "example", "capability": "scrape.website", "route": "/v1/scrape/website",
            "payload": {"urls": "https://example.com"}, "required": ["output.*.url", "output.*.title"], **changes}


async def test_metrics_count_every_record_and_do_not_upgrade_support():
    keys = []
    def respond(request):
        keys.append(request.headers["Idempotency-Key"])
        return httpx.Response(200, json={"status": "succeeded", "capability": "scrape.amazon",
            "output": [{"url": "https://example.com", "title": "Example"}, {"url": "https://example.com"}],
            "source": {"collectionState": "complete"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://localhost") as client:
        results = await evaluate(client, [case(capability="scrape.amazon")]*2)
    assert results[0]["coverage"] == 0.75
    assert not results[0]["success"]
    assert results[0]["supportLevel"] == "best_effort"
    assert keys[0] != keys[1]
    assert "best_effort" in render_report(results)


@pytest.mark.parametrize("body, reason", [
    ({"status": "succeeded", "output": []}, "empty"),
    ({"status": "succeeded", "output": [{"url": "x", "title": "x"}], "source": {"collectionState": "blocked"}}, "blocked"),
    ({"status": "failed", "error": {"code": "search_request_failed"}}, "search_request_failed"),
])
async def test_failure_states(body, reason):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)), base_url="http://localhost") as client:
        result = (await evaluate(client, [case()]))[0]
    assert not result["success"]
    assert result["reason"] == reason


async def test_transport_and_invalid_json_failures_continue():
    def respond(request):
        if request.url.path.endswith("website"):
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(502, text="not JSON")
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), base_url="http://localhost") as client:
        results = await evaluate(client, [case(), case(route="/v1/search/web")])
    assert [r["reason"] for r in results] == ["ReadTimeout", "http_502"]
    assert all(r["coverage"] == 0 for r in results)
    assert "0.0%" in render_report(results)


@pytest.mark.parametrize("changes", [{"required": []}, {"payload": {"dryRun": True}}, {"route": "https://example.com"}, {"capability": "unknown"}])
def test_invalid_fixtures(changes):
    with pytest.raises(ValueError):
        validate_cases([case(**changes)])


def test_m1_corpus_has_ten_public_cases_per_suite():
    cases = validate_cases(json.loads(Path("evals/m1-corpus.json").read_text()))
    suites = {name: 0 for name in M1_SUITES}
    for item in cases:
        suite = get_capability(item["capability"]).evaluation_suite
        suites[suite] += 1
    assert len(cases) == 90
    assert suites == dict.fromkeys(M1_SUITES, 10)
