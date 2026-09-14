from urllib.parse import urlparse

from app.search import search_web


def hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


async def rank(keyword: str, domain: str, depth: int) -> dict:
    results, _ = await search_web(keyword, min(depth, 100))
    rows = [item.model_dump(by_alias=True, exclude_none=True) for item in results]
    position = next((index + 1 for index, item in enumerate(rows) if hostname(item["url"]).endswith(domain.lower().removeprefix("www."))), None)
    return {"keyword": keyword, "domain": domain, "position": position, "results": rows}


async def competitors(domain: str, limit: int) -> dict:
    results, _ = await search_web(f"site:{domain}", max(limit * 3, 10))
    domains: list[str] = []
    for item in results:
        host = hostname(item.url)
        if host and host != domain and host not in domains:
            domains.append(host)
    return {"domain": domain, "competitors": [{"domain": item, "sharedKeywords": None, "gapKeywords": None} for item in domains[:limit]], "dataSource": "local-search"}
