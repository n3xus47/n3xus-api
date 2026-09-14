from app.models import SearchResult
from app.search import (
    apply_site_restriction,
    filter_results_by_site_host,
    parse_site_restriction,
    search_web_fused,
)


def test_parse_site_restriction_strips_operator():
    text, host = parse_site_restriction("carbonara site:jamieoliver.com")
    assert host == "jamieoliver.com"
    assert text == "carbonara"


def test_parse_site_restriction_no_operator():
    text, host = parse_site_restriction("python asyncio")
    assert host is None
    assert text == "python asyncio"


def test_filter_results_by_site_host_includes_subdomains():
    jamie = SearchResult(title="Recipe", url="https://www.jamieoliver.com/recipes/carbonara/", snippet=None)
    other = SearchResult(title="Other", url="https://example.com/carbonara", snippet=None)
    sub = SearchResult(title="Sub", url="https://recipes.jamieoliver.com/carbonara", snippet=None)
    filtered = filter_results_by_site_host([other, jamie, sub], "jamieoliver.com")
    assert [r.url for r in filtered] == [jamie.url, sub.url]


def test_apply_site_restriction_empty_when_no_host_match():
    junk = SearchResult(title="Zara", url="https://www.zara.com/top", snippet=None)
    ranked = apply_site_restriction("carbonara site:jamieoliver.com", [junk])
    assert ranked == []


async def test_search_web_fused_applies_site_filter(monkeypatch):
    async def mixed_searxng(_query, _max):
        return (
            [
                SearchResult(title="Jamie", url="https://www.jamieoliver.com/recipes/carbonara/", snippet=""),
                SearchResult(title="Zara", url="https://www.zara.com/", snippet=""),
            ],
            None,
        )

    async def empty_ddg(_query, _max):
        return []

    monkeypatch.setattr("app.search._searxng_search_optional", mixed_searxng)
    monkeypatch.setattr("app.search._ddg_search_optional", empty_ddg)

    outcome = await search_web_fused("carbonara site:jamieoliver.com", 5, variant_limit=1)
    assert len(outcome.results) == 1
    assert "jamieoliver.com" in outcome.results[0].url
