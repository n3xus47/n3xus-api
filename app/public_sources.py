"""Free, local adapters for public-source endpoints.

They deliberately return only data observed on public pages.  A blocked source is an
empty result, never invented profile, rating, price, or engagement data.
"""
from urllib.parse import quote_plus

import httpx

from app.amazon_adapter import amazon_product, amazon_reviews, amazon_search
from app.models import WebsiteScrapeRequest
from app.open_business import search_open_business
from app.scraper import scrape_website
from app.search import search_web


SOCIAL_HOSTS = {
    "twitter": "https://x.com/{name}",
    "instagram": "https://www.instagram.com/{name}/",
    "tiktok": "https://www.tiktok.com/@{name}",
    "youtube": "https://www.youtube.com/@{name}",
}


async def public_pages(urls: list[str], max_items: int = 10, max_chars: int = 100_000) -> dict:
    pages, _ = await scrape_website(
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
        return await amazon_product(payload)
    if resource == "reviews":
        return await amazon_reviews(payload)
    return await amazon_search(payload)


async def google_places(payload: dict) -> dict:
    return await search_open_business(payload)
