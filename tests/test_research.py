import json

import pytest

from app.models import Page, SearchResult
from app.research import (
    assess_completeness,
    merge_search_hits,
    pick_source_urls,
    plan_search_queries,
    research,
)


async def test_plan_search_queries_returns_multiple_distinct_queries(monkeypatch):
    async def fake_generate(_prompt, json_mode=False):
        return json.dumps({"queries": ["asyncio python tutorial", "python asyncio official docs", "asyncio use cases"]})

    monkeypatch.setattr("app.research.generate", fake_generate)
    plan = await plan_search_queries("What is asyncio?", None)
    assert len(plan) == 3
    assert all("asyncio" in item.lower() for item in plan)


def test_merge_search_hits_dedupes_urls_and_keeps_query_provenance():
    hits = merge_search_hits(
        ["a", "b"],
        [
            ("a", [SearchResult(title="One", url="https://a.example/1", snippet="s1")]),
            ("b", [SearchResult(title="One", url="https://a.example/1", snippet="s1"), SearchResult(title="Two", url="https://b.example/2", snippet=None)]),
        ],
    )
    assert len(hits) == 2
    by_url = {item["url"]: item for item in hits}
    assert by_url["https://a.example/1"]["searchQueries"] == ["a", "b"]


def test_pick_source_urls_prefers_distinct_domains():
    candidates = [
        {"url": "https://a.example/1", "searchQueries": ["q"]},
        {"url": "https://a.example/2", "searchQueries": ["q"]},
        {"url": "https://b.example/1", "searchQueries": ["q"]},
        {"url": "https://c.example/1", "searchQueries": ["q"]},
    ]
    urls = pick_source_urls(candidates, limit=3)
    assert len(urls) == 3
    assert len({url.split("/")[2] for url in urls}) >= 2


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"planned_queries": 3, "queries_with_results": 0, "selected_urls": 0, "pages_with_content": 0, "distinct_domains": 0}, "empty"),
        ({"planned_queries": 3, "queries_with_results": 2, "selected_urls": 2, "pages_with_content": 1, "distinct_domains": 1}, "partial"),
        ({"planned_queries": 3, "queries_with_results": 3, "selected_urls": 2, "pages_with_content": 2, "distinct_domains": 2}, "complete"),
        ({"planned_queries": 3, "queries_with_results": 3, "selected_urls": 3, "pages_with_content": 3, "distinct_domains": 1}, "partial"),
    ],
)
def test_assess_completeness_is_honest(kwargs, expected):
    assert assess_completeness(**kwargs) == expected


async def test_research_pipeline_returns_plan_evidence_and_completeness(monkeypatch):
    async def fake_plan(_query, _context):
        return ["q1", "q2"]

    from app.search import SearchFusionOutcome

    async def fake_search(query, _max):
        if query == "q1":
            return SearchFusionOutcome(
                [SearchResult(title="A", url="https://a.example/page", snippet="sa")], None, ("searxng",)
            )
        return SearchFusionOutcome(
            [SearchResult(title="B", url="https://b.example/page", snippet="sb")], None, ("searxng",)
        )

    async def fake_scrape(_request):
        return [
            Page(url="https://a.example/page", markdown="# A", title="A"),
            Page(url="https://b.example/page", markdown="# B", title="B"),
        ], [
            {"url": "https://a.example/page", "status": "returned"},
            {"url": "https://b.example/page", "status": "returned"},
        ], None

    async def fake_generate(prompt, json_mode=False):
        if json_mode:
            raise AssertionError("synthesis should not use json mode")
        assert "[1]" in prompt
        return "Asyncio is a concurrency library [1][2]."

    monkeypatch.setattr("app.research.plan_search_queries", fake_plan)
    monkeypatch.setattr("app.research.search_web_fused", fake_search)
    monkeypatch.setattr("app.research.scrape_website", fake_scrape)
    monkeypatch.setattr("app.research.generate", fake_generate)

    output = await research("What is asyncio?", None)
    assert output["searchPlan"] == ["q1", "q2"]
    assert output["completeness"] == "complete"
    assert len(output["evidence"]) == 2
    assert output["evidence"][0]["index"] == 1
    assert output["evidence"][0]["searchQueries"]
    assert output["sources"][0]["url"].startswith("https://")
