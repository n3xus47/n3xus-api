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


async def test_search_web_fused_merge_prefers_on_topic_ddg_over_searxng_noise(monkeypatch):
    query = "Gordon Ramsay scrambled eggs recipe"
    noise = [
        SearchResult(title="Zara top", url="https://www.zara.com/", snippet="Fashion"),
        SearchResult(
            title="Anthony Gordon",
            url="https://www.transfermarkt.com/anthony-gordon/profil/spieler/1",
            snippet="Footballer",
        ),
    ]
    recipe = SearchResult(
        title="Gordon Ramsay scrambled eggs",
        url="https://www.bbcgoodfood.com/recipes/gordon-ramsays-scrambled-eggs",
        snippet="Classic scrambled eggs recipe",
    )

    async def searxng_noise(_query, _max):
        return noise, None

    async def ddg_recipe(_query, max_results):
        return [recipe][:max_results]

    monkeypatch.setattr("app.search._searxng_search_optional", searxng_noise)
    monkeypatch.setattr("app.search._ddg_search_optional", ddg_recipe)

    outcome = await search_web_fused(query, 5, variant_limit=1)
    assert outcome.results
    assert outcome.results[0].url == recipe.url
    assert outcome.providers == ("searxng", "duckduckgo")


async def test_searxng_http_json_fused_with_mocked_ddg(monkeypatch):
    """Contract: real SearxNG JSON parse + DDG batch merge without network."""
    import app.search as search_mod

    query = "Gordon Ramsay scrambled eggs recipe"
    recipe = SearchResult(
        title="Gordon Ramsay scrambled eggs",
        url="https://www.bbcgoodfood.com/recipes/gordon-ramsays-scrambled-eggs",
        snippet="Classic scrambled eggs recipe",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("format") == "json"
        payload = {
            "results": [
                {
                    "title": "Zara top",
                    "url": "https://www.zara.com/",
                    "content": "Fashion picks",
                }
            ]
        }
        return httpx.Response(200, json=payload, request=request)

    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(handler))
        return real_async_client(**kwargs)

    def fake_ddg_sync(_query, max_results):
        return [recipe][:max_results]

    monkeypatch.setattr(search_mod.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(search_mod, "_ddg_search_sync", fake_ddg_sync)

    outcome = await search_web_fused(query, 5, variant_limit=1)
    assert outcome.results[0].url == recipe.url
    assert "searxng" in outcome.providers
    assert "duckduckgo" in outcome.providers

