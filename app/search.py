import httpx

from app.config import settings
from app.models import SearchResult


class SearchError(Exception):
    pass


async def search_web(query: str, max_results: int) -> tuple[list[SearchResult], str | None]:
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_secs) as client:
            response = await client.get(
                f"{settings.searxng_url.rstrip('/')}/search",
                params={"q": query, "format": "json", "categories": "general"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise SearchError("SearxNG is unavailable") from error

    results = [
        SearchResult(
            title=item.get("title") or item["url"],
            url=item["url"],
            snippet=item.get("content") or None,
            dateText=item.get("publishedDate") or None,
        )
        for item in payload.get("results", [])[:max_results]
        if item.get("url")
    ]
    answer = payload.get("answers", [None])
    return results, answer[0] if answer else None
