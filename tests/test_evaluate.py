import json
from collections import Counter
from pathlib import Path

import httpx
import pytest

from app.capabilities import get_capability
from app.evaluate import check_result_relevance, evaluate, render_report, validate_cases

M1_CORPUS_PATH = Path(__file__).resolve().parents[1] / "evals" / "m1-corpus.json"
M1_CASES_PER_SUITE = 10
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
    assert results[0]["supportLevel"] == "structured"
    assert keys[0] != keys[1]
    assert "structured" in render_report(results)


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
    cases = validate_cases(json.loads(M1_CORPUS_PATH.read_text()))
    by_suite = Counter(get_capability(item["capability"]).evaluation_suite for item in cases)
    expected = dict.fromkeys(M1_SUITES, M1_CASES_PER_SUITE)
    assert len(cases) == len(M1_SUITES) * M1_CASES_PER_SUITE
    assert by_suite == expected


def test_browser_act_fixtures_validate():
    cases = validate_cases([
        {
            "id": "browser-read",
            "capability": "browser.act",
            "route": "/v1/browser/act",
            "payload": {"task": "Read the heading", "startUrl": "https://example.com"},
            "required": ["output.trace", "output.trace.*.phase"],
        }
    ])
    assert cases[0]["capability"] == "browser.act"


def test_research_fixtures_validate():
    cases = validate_cases([
        {
            "id": "research-smoke",
            "capability": "research.deep",
            "route": "/v1/research/deep",
            "payload": {"query": "Example topic"},
            "required": ["output.searchPlan", "output.evidence", "output.completeness"],
        }
    ])
    assert cases[0]["route"] == "/v1/research/deep"


def test_search_agent_realism_fixture_validates():
    path = Path(__file__).resolve().parents[1] / "evals" / "search-agent-realism.json"
    cases = validate_cases(json.loads(path.read_text()))
    assert len(cases) >= 5
    assert all(
        c.get("expectUrlPattern")
        or c.get("expectKeywords")
        or c.get("expectEmpty")
        or c.get("rejectUrlPattern")
        for c in cases
    )


def test_check_result_relevance_expect_empty():
    body = {"source": {"collectionState": "empty"}, "output": {"results": []}}
    assert check_result_relevance({"expectEmpty": True}, body) == ""
    body_bad = {"source": {"collectionState": "complete"}, "output": {"results": [{"url": "https://zara.com", "title": "x"}]}}
    assert check_result_relevance({"expectEmpty": True}, body_bad) == "expected_empty_results"


def test_check_result_relevance_reject_url_pattern():
    body = {"output": {"results": [{"url": "https://www.zara.com/x", "title": "Fashion"}]}}
    assert check_result_relevance({"rejectUrlPattern": r"zara\.com"}, body) == "rejected_url_pattern"


def test_check_result_relevance_url_pattern_and_keywords():
    body = {"output": {"results": [
        {"url": "https://www.jamieoliver.com/recipes/pasta", "title": "Pasta"},
        {"url": "https://example.com", "title": "Other"},
    ]}}
    assert check_result_relevance({"expectUrlPattern": r"jamieoliver\.com", "resultCheckCount": 2}, body) == ""
    assert check_result_relevance({"expectUrlPattern": r"python\.org"}, body) == "url_pattern_mismatch"
    assert check_result_relevance({"expectKeywords": ["pasta", "jamie"]}, body) == ""
    assert check_result_relevance({"expectKeywords": ["quantum"]}, body) == "keyword_mismatch"


async def test_evaluate_applies_relevance_checks_after_field_coverage():
    body = {"status": "succeeded", "capability": "search.web",
            "output": {"results": [{"url": "https://example.com", "title": "Unrelated"}]},
            "source": {"collectionState": "complete"}}
    fixture = case(capability="search.web", route="/v1/search/web",
                   payload={"query": "test"},
                   required=["output.results.*.url", "output.results.*.title"],
                   expectUrlPattern=r"jamieoliver\.com")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)), base_url="http://localhost") as client:
        result = (await evaluate(client, [fixture]))[0]
    assert not result["success"]
    assert result["reason"] == "url_pattern_mismatch"
