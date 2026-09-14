import asyncio
import fnmatch
import ipaddress
import socket
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from readability import Document

from app.config import settings
from app.models import Page, WebsiteScrapeRequest


class ScrapeError(Exception):
    pass


async def assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ScrapeError("URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ScrapeError("URLs with credentials are not supported")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        raise ScrapeError("Could not resolve URL host") from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ScrapeError("Private and local network URLs are not supported")


async def fetch_html(url: str) -> tuple[str, str]:
    current_url = url
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_secs,
        headers={"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    ) as client:
        for _ in range(6):
            await assert_public_url(current_url)
            response = await client.get(current_url)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ScrapeError("Redirect has no location")
                current_url = urljoin(current_url, location)
                continue
            response.raise_for_status()
            if "html" not in response.headers.get("content-type", ""):
                raise ScrapeError("URL did not return HTML")
            return response.text, str(response.url)
    raise ScrapeError("Too many redirects")


def extract_page(html: str, url: str, content_format: str | None, max_chars: int) -> Page:
    document = Document(html)
    article_html = document.summary(html_partial=True)
    source = BeautifulSoup(html, "html.parser")
    article = BeautifulSoup(article_html, "html.parser")
    title = document.short_title() or None
    description_tag = source.find("meta", attrs={"name": "description"})
    language = source.html.get("lang") if source.html else None
    text = article.get_text("\n", strip=True)
    markdown = markdownify(str(article), heading_style="ATX").strip()
    total_chars = max(len(text), len(markdown))
    truncated = total_chars > max_chars
    if truncated:
        text = text[:max_chars]
        markdown = markdown[:max_chars]

    return Page(
        url=url,
        markdown=markdown if content_format != "text" else None,
        text=text if content_format != "markdown" else None,
        title=title,
        description=description_tag.get("content") if description_tag else None,
        language=language,
        truncated=True if truncated else None,
        total_chars=total_chars if truncated else None,
    )


def links_from(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    for anchor in BeautifulSoup(html, "html.parser").select("a[href]"):
        url, _ = urldefrag(urljoin(base_url, anchor["href"]))
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"}:
            links.append(url)
    return links


def matches(url: str, patterns: list[str] | None) -> bool:
    return patterns is None or any(fnmatch.fnmatchcase(url, pattern) for pattern in patterns)


def to_list(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None
    return [value] if isinstance(value, str) else value


async def scrape_website(request: WebsiteScrapeRequest) -> tuple[list[Page], list[dict[str, str]] | None]:
    seeds = request.url_list()
    follows_links = request.max_depth is not None and request.max_depth > 0
    follows_links = follows_links or (
        request.max_depth is None
        and any(value is not None for value in (request.max_pages, request.include_urls, request.exclude_urls))
    )
    page_limit = request.max_pages or request.max_items or len(seeds)
    queue = deque((url, 0) for url in seeds)
    visited: set[str] = set()
    pages: list[Page] = []
    returned_urls: set[str] = set()
    include = to_list(request.include_urls)
    exclude = to_list(request.exclude_urls)

    while queue and len(pages) < page_limit:
        url, depth = queue.popleft()
        if url in visited or not matches(url, include) or (exclude and matches(url, exclude)):
            continue
        visited.add(url)
        try:
            html, final_url = await fetch_html(url)
            page = extract_page(html, final_url, request.content_format, request.max_chars)
            content = page.markdown or page.text or ""
            if settings.browser_fallback and len(content) < 200:
                from app.browser import render_html

                html, final_url = await render_html(url)
                page = extract_page(html, final_url, request.content_format, request.max_chars)
        except (httpx.HTTPError, ScrapeError):
            continue
        if page.markdown or page.text:
            pages.append(page)
            returned_urls.add(url)
        if follows_links and (request.max_depth is None or depth < request.max_depth):
            for link in links_from(html, final_url):
                if link not in visited:
                    queue.append((link, depth + 1))

    outcomes = None
    if not follows_links:
        outcomes = [
            {"url": url, "status": "returned" if url in returned_urls else "not_returned"}
            for url in seeds
        ]
    return pages, outcomes
