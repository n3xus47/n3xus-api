import httpx

from app.models import SearchResult
from app.search import (
    SEARCH_RELEVANCE_FLOOR,
    SEARXNG_ENGINE_CHAIN,
    apply_relevance_floor,
    build_search_variants,
    merge_search_results,
    rank_search_results,
    relevance_score,
    search_web_fused,
)


def test_searxng_engine_chain_is_free_local_default():
    assert "bing" in SEARXNG_ENGINE_CHAIN


def test_build_search_variants_deduplicates_and_caps():
    variants = build_search_variants("asyncio python", limit=5)
    assert variants[0] == "asyncio python"
    assert len(variants) == len(set(variants))
    assert len(variants) <= 5


def test_merge_search_results_dedupes_by_url():
    a = SearchResult(title="A", url="https://a.example/1", snippet="s1")
    b = SearchResult(title="B", url="https://b.example/2", snippet=None)
    a2 = SearchResult(title="A2", url="https://a.example/1", snippet="s2 longer")
    merged = merge_search_results([[a, b], [a2]], 10)
    assert len(merged) == 2
    assert merged[0].snippet == "s2 longer"


def test_relevance_prefers_matching_phrase_over_partial_token():
    football = SearchResult(
        title="Anthony Gordon footballer",
        url="https://en.wikipedia.org/wiki/Anthony_Gordon_(footballer)",
        snippet="English footballer",
    )
    recipe = SearchResult(
        title="Gordon Ramsay scrambled eggs",
        url="https://www.bbcgoodfood.com/recipes/gordon-ramsays-scrambled-eggs",
        snippet="Classic scrambled eggs recipe",
    )
    query = "Gordon Ramsay scrambled eggs recipe"
    assert relevance_score(query, recipe) > relevance_score(query, football)
    ranked = rank_search_results(query, [football, recipe])
    assert ranked[0].url == recipe.url


def test_apply_relevance_floor_drops_junk_when_top_score_below_floor():
    query = "Gordon Ramsay scrambled eggs recipe"
    football = SearchResult(
        title="Anthony Gordon footballer",
        url="https://en.wikipedia.org/wiki/Anthony_Gordon_(footballer)",
        snippet="English footballer",
    )
    zara = SearchResult(title="Top fashion", url="https://www.zara.com/", snippet="Shop")
    ranked = rank_search_results(query, [zara, football])
    assert relevance_score(query, ranked[0]) < SEARCH_RELEVANCE_FLOOR
    assert apply_relevance_floor(query, ranked) == []


def test_apply_relevance_floor_keeps_on_topic_results():
    query = "Gordon Ramsay scrambled eggs recipe"
    football = SearchResult(
        title="Anthony Gordon footballer",
        url="https://en.wikipedia.org/wiki/Anthony_Gordon_(footballer)",
        snippet="English footballer",
    )
    recipe = SearchResult(
        title="Gordon Ramsay scrambled eggs",
        url="https://www.bbcgoodfood.com/recipes/gordon-ramsays-scrambled-eggs",
        snippet="Classic scrambled eggs recipe",
    )
    ranked = rank_search_results(query, [football, recipe])
    kept = apply_relevance_floor(query, ranked)
    assert len(kept) == 1
    assert kept[0].url == recipe.url


async def test_search_web_fused_falls_back_to_ddg_when_searxng_empty(monkeypatch):
    async def empty_searxng(_query, _max):
        return [], None

    async def ddg_results(query, max_results):
        return [
            SearchResult(title="Asyncio docs", url="https://docs.python.org/3/library/asyncio.html", snippet=query)
        ][:max_results]

    monkeypatch.setattr("app.search._searxng_search_optional", empty_searxng)
    monkeypatch.setattr("app.search._ddg_search_optional", ddg_results)

    outcome = await search_web_fused("python asyncio tutorial", 5, variant_limit=2)
    assert outcome.results
    assert "duckduckgo" in outcome.providers
    assert outcome.results[0].url.startswith("https://docs.python.org")


async def test_search_web_fused_ignores_searxng_variant_failures(monkeypatch):
    calls = {"n": 0}

    async def flaky_searxng(_query, _max):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadError("connection dropped")
        return (
            [
                SearchResult(
                    title="asyncio python tutorial",
                    url="https://docs.python.org/3/library/asyncio.html",
                    snippet="asyncio event loop",
                )
            ],
            None,
        )

    async def empty_ddg(_query, _max):
        return []

    monkeypatch.setattr("app.search._searxng_search_optional", flaky_searxng)
    monkeypatch.setattr("app.search._ddg_search_optional", empty_ddg)

    outcome = await search_web_fused("asyncio python", 5, variant_limit=2)
    assert outcome.results
    assert "searxng" in outcome.providers

