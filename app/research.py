from app.llm import generate
from app.models import WebsiteScrapeRequest
from app.scraper import scrape_website
from app.search import search_web


async def research(query: str, context: str | None) -> dict:
    results, _ = await search_web(query, 5)
    pages, _, _ = await scrape_website(
        WebsiteScrapeRequest(urls=[result.url for result in results[:5]], contentFormat="markdown", maxChars=20_000)
    )
    sources = [{"url": page.url, "title": page.title} for page in pages]
    evidence = "\n\n".join(f"[{index + 1}] {page.url}\n{page.markdown or page.text}" for index, page in enumerate(pages))
    answer = await generate(
        f"Answer this research question using only the numbered evidence. Cite claims with [n]. "
        f"State uncertainty or conflicting sources.\nQuestion: {query}\nContext: {context or ''}\n\nEvidence:\n{evidence}"
    )
    return {"answer": answer, "sources": sources, "completeness": "complete" if pages else "partial"}
