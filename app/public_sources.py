"""Free, local adapters for public-source endpoints.

They deliberately return only data observed on public pages.  A blocked source is an
empty result, never invented profile, rating, price, or engagement data.
"""
from urllib.parse import quote_plus

import httpx

from app.models import WebsiteScrapeRequest
from app.scraper import scrape_website
from app.search import search_web


SOCIAL_HOSTS = {
    "twitter": "https://x.com/{name}",
    "instagram": "https://www.instagram.com/{name}/",
    "tiktok": "https://www.tiktok.com/@{name}",
    "youtube": "https://www.youtube.com/@{name}",
}


async def public_pages(urls: list[str], max_items: int = 10, max_chars: int = 100_000) -> dict:
    pages, _, _ = await scrape_website(
        WebsiteScrapeRequest(urls=urls, contentFormat="markdown", maxPages=max_items, maxChars=max_chars)
    )
    return {
        "items": [page.model_dump(by_alias=True, exclude_none=True) for page in pages],
        "missingUrls": [url for url in urls if not any(page.url == url for page in pages)],
    }


async def social(provider: str, resource: str, payload: dict) -> dict:
    """Read public social pages without credentials or anti-bot bypasses."""
    if resource in {"comments", "replies", "transcript"}:
        url = payload.get("url")
        if not isinstance(url, str):
            raise ValueError("url is required")
        return await public_pages([url], int(payload.get("maxItems", 10)), int(payload.get("maxChars", 100_000)))

    names = payload.get("usernames") or payload.get("handles") or payload.get("channels")
    if provider == "twitter" and resource == "search" and isinstance(payload.get("query"), str):
        return await public_pages([f"https://x.com/search?q={quote_plus(payload['query'])}"], int(payload.get("maxItems", 10)))
    if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
        raise ValueError("usernames, handles, or channels must be a non-empty list")
    template = SOCIAL_HOSTS[provider]
    suffix = "/reels/" if resource == "hashtag" else ""
    return await public_pages([template.format(name=name) + suffix for name in names], int(payload.get("maxItems", 10)))


async def instagram_hashtag(payload: dict) -> dict:
    hashtags = payload.get("hashtags")
    if not isinstance(hashtags, list) or not hashtags or not all(isinstance(item, str) for item in hashtags):
        raise ValueError("hashtags must be a non-empty list")
    return await public_pages(
        [f"https://www.instagram.com/explore/tags/{quote_plus(tag.lstrip('#'))}/" for tag in hashtags],
        int(payload.get("maxItems", 10)),
    )


async def facebook(payload: dict, resource: str) -> dict:
    if resource == "groups":
        urls = payload.get("urls")
        if isinstance(urls, str):
            urls = [urls]
        if not isinstance(urls, list) or not urls or not all(isinstance(url, str) for url in urls):
            raise ValueError("urls must be a non-empty list")
        return await public_pages(urls, int(payload.get("maxItems", 20)))
    query = payload.get("query")
    if not isinstance(query, str) or not query:
        raise ValueError("query is required")
    results, _ = await search_web(f"site:facebook.com/ads/library {query}", int(payload.get("maxItems", 20)))
    return {"items": [item.model_dump(by_alias=True, exclude_none=True) for item in results]}


async def amazon(payload: dict, resource: str) -> dict:
    if resource == "product":
        url = payload.get("url")
        asin = payload.get("asin")
        marketplace = str(payload.get("marketplace", "US")).lower()
        hosts = {"us": "amazon.com", "uk": "amazon.co.uk", "de": "amazon.de"}
        if not url and isinstance(asin, str):
            url = f"https://www.{hosts.get(marketplace, 'amazon.com')}/dp/{asin}"
        if not isinstance(url, str):
            raise ValueError("asin or url is required")
        return await public_pages([url], 1)
    if resource == "reviews":
        asin = payload.get("asin")
        if not isinstance(asin, str):
            raise ValueError("asin is required")
        return await public_pages([f"https://www.amazon.com/product-reviews/{asin}"], int(payload.get("maxItems", 10)))
    query = payload.get("query")
    if not isinstance(query, str) or not query:
        raise ValueError("query is required")
    results, _ = await search_web(f"site:amazon.com {query}", int(payload.get("maxItems", 10)))
    return {"items": [item.model_dump(by_alias=True, exclude_none=True) for item in results]}


async def google_places(payload: dict) -> dict:
    search = payload.get("search")
    if not isinstance(search, str) or not search:
        raise ValueError("search is required")
    location = payload.get("location")
    query = f"{search}, {location}" if isinstance(location, str) else search
    try:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "n3xusAPI local tools"}) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": min(int(payload.get("maxItems", 10)), 50)},
            )
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("OpenStreetMap public geocoder is unavailable") from error
    return {"places": [{"name": row.get("display_name"), "address": row.get("display_name"), "latitude": row.get("lat"), "longitude": row.get("lon"), "category": row.get("type"), "sourceUrl": row.get("osm_url")} for row in rows]}
