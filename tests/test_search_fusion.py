from app.models import SearchResult
from app.search import (
    SEARXNG_ENGINE_CHAIN,
    build_search_variants,
    merge_search_results,
    rank_search_results,
    relevance_score,
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
