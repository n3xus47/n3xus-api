import json
from urllib.parse import urlparse

from app.llm import LlmError, generate
from app.models import Page, SearchResult, WebsiteScrapeRequest
from app.scraper import scrape_website
from app.search import build_search_variants, search_web_fused

MAX_EVIDENCE_PAGES = 6
MAX_RESULTS_PER_QUERY = 5


async def plan_search_queries(query: str, context: str | None) -> list[str]:
    prompt = f"""Plan 2 to 4 diverse web searches to research a public question from different angles.
Return JSON only: {{"queries":["..."]}}. Each query must be concise and distinct.
Question: {query}
Context: {context or ""}"""
    try:
        payload = json.loads(await generate(prompt, json_mode=True))
        queries = payload.get("queries")
        if isinstance(queries, list):
            cleaned = [item.strip() for item in queries if isinstance(item, str) and item.strip()]
            if 2 <= len(cleaned) <= 4 and len(set(cleaned)) == len(cleaned):
                return cleaned
    except (json.JSONDecodeError, TypeError, LlmError):
        pass
    cleaned = query.strip()
    if cleaned:
        return build_search_variants(cleaned, limit=4)
    return [query]


def _registrable_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def merge_search_hits(planned_queries: list[str], batches: list[tuple[str, list[SearchResult]]]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for search_query, results in batches:
        if search_query not in planned_queries:
            continue
        for result in results:
            item = by_url.setdefault(
                result.url,
                {"url": result.url, "title": result.title, "snippet": result.snippet, "searchQueries": []},
            )
            if search_query not in item["searchQueries"]:
                item["searchQueries"].append(search_query)
    return list(by_url.values())


def pick_source_urls(candidates: list[dict], limit: int = MAX_EVIDENCE_PAGES) -> list[str]:
    if not candidates:
        return []
    ranked = sorted(candidates, key=lambda item: (-len(item["searchQueries"]), item["url"]))
    chosen: list[str] = []
    seen_domains: set[str] = set()
    for item in ranked:
        domain = _registrable_domain(item["url"])
        if domain in seen_domains and len(chosen) >= 2:
            continue
        chosen.append(item["url"])
        seen_domains.add(domain)
        if len(chosen) >= limit:
            return chosen
    for item in ranked:
        if item["url"] not in chosen:
            chosen.append(item["url"])
        if len(chosen) >= limit:
            break
    return chosen


def assess_completeness(
    *,
    planned_queries: int,
    queries_with_results: int,
    selected_urls: int,
    pages_with_content: int,
    distinct_domains: int,
) -> str:
    if pages_with_content == 0:
        return "empty"
    if queries_with_results < planned_queries or pages_with_content < selected_urls or distinct_domains < 2:
        return "partial"
    return "complete"


def _page_text(page: Page) -> str:
    return (page.markdown or page.text or "").strip()


def _page_has_content(page: Page) -> bool:
    return bool(_page_text(page))


def _collection_state(text: str, status: str) -> str:
    if text and status == "returned":
        return "complete"
    if text:
        return "partial"
    return "empty"


def build_evidence(
    pages: list[Page],
    url_outcomes: list[dict[str, str]] | None,
    hits: list[dict],
) -> list[dict]:
    hit_by_url = {item["url"]: item for item in hits}
    outcome_by_url = {item["url"]: item["status"] for item in (url_outcomes or [])}
    evidence: list[dict] = []
    for index, page in enumerate(pages, start=1):
        hit = hit_by_url.get(page.url, {})
        text = _page_text(page)
        status = outcome_by_url.get(page.url, "returned" if text else "not_returned")
        collection_state = _collection_state(text, status)
        evidence.append(
            {
                "index": index,
                "url": page.url,
                "title": page.title or hit.get("title"),
                "searchQueries": hit.get("searchQueries", []),
                "excerpt": text[:500] if text else hit.get("snippet"),
                "collectionState": collection_state,
            }
        )
    return evidence


async def research(query: str, context: str | None) -> dict:
    search_plan = await plan_search_queries(query, context)
    batches: list[tuple[str, list[SearchResult]]] = []
    queries_with_results = 0
    for search_query in search_plan:
        try:
            fusion = await search_web_fused(search_query, MAX_RESULTS_PER_QUERY)
            results = fusion.results
        except Exception:
            results = []
        if results:
            queries_with_results += 1
        batches.append((search_query, results))

    hits = merge_search_hits(search_plan, batches)
    selected_urls = pick_source_urls(hits)
    pages: list[Page] = []
    outcomes: list[dict[str, str]] | None = None
    if selected_urls:
        pages, outcomes, _ = await scrape_website(
            WebsiteScrapeRequest(urls=selected_urls, contentFormat="markdown", maxChars=20_000)
        )

    evidence = build_evidence(pages, outcomes, hits)
    pages_with_content = sum(1 for page in pages if _page_has_content(page))
    distinct_domains = len({_registrable_domain(page.url) for page in pages if _page_has_content(page)})
    completeness = assess_completeness(
        planned_queries=len(search_plan),
        queries_with_results=queries_with_results,
        selected_urls=len(selected_urls),
        pages_with_content=pages_with_content,
        distinct_domains=distinct_domains,
    )

    numbered = "\n\n".join(
        f"[{item['index']}] {item['url']}\n{item.get('excerpt') or ''}" for item in evidence if item.get("excerpt")
    )
    synthesis_prompt = (
        "Answer the research question using only the numbered evidence below. "
        "Every factual claim must cite one or more evidence numbers like [1]. "
        "If the evidence is insufficient, say so explicitly and do not invent facts.\n"
        f"Question: {query}\nContext: {context or ''}\n\nEvidence:\n{numbered or '(no evidence collected)'}"
    )
    try:
        answer = await generate(synthesis_prompt)
    except LlmError:
        if not evidence:
            answer = "No public evidence could be collected for this question with the current search configuration."
        else:
            answer = (
                "Local LLM is unavailable; summarized evidence only:\n\n"
                + numbered
                + "\n\nConfigure Ollama and pull the model named in N3XUS_API_OLLAMA_MODEL for a synthesized answer."
            )

    sources = [{"url": item["url"], "title": item.get("title")} for item in evidence]
    return {
        "answer": answer,
        "sources": sources,
        "searchPlan": search_plan,
        "evidence": evidence,
        "completeness": completeness,
    }
