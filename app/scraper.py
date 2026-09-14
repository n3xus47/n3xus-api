import asyncio
import fnmatch
import ipaddress
import socket
from collections import deque
from typing import NamedTuple
from urllib.parse import urldefrag, urljoin, urlunparse, urlparse

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify
from readability import Document

from app.config import settings
from app.models import Page, WebsiteScrapeRequest

BLOCKED_HTTP_STATUSES = {401, 403, 429, 451}
BLOCKED_HTML_MARKERS = (
    "captcha",
    "access denied",
    "just a moment",
    "cf-browser-verification",
    "attention required",
    "enable javascript and cookies",
)
BROWSER_FALLBACK_MIN_EXTRACTABLE_CHARS = 200


class ScrapeError(Exception):
    pass


class FetchFailure(ScrapeError):
    def __init__(self, reason: str, message: str):
        self.reason = reason
        super().__init__(message)


def normalize_crawl_url(url: str) -> str:
    """Canonical URL for crawl deduplication; does not validate reachability."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return url
    host = parsed.hostname.lower()
    port = parsed.port
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))


def looks_blocked_html(html: str) -> bool:
    sample = html[:8_000].lower()
    return any(marker in sample for marker in BLOCKED_HTML_MARKERS)


def website_collection_state(pages: list[Page], seed_outcomes: list[dict[str, str]]) -> str:
    if pages:
        if not seed_outcomes:
            return "complete"
        returned = sum(1 for outcome in seed_outcomes if outcome.get("status") == "returned")
        if returned == len(seed_outcomes):
            return "complete"
        return "partial"
    if seed_outcomes and all(outcome.get("status") == "blocked" for outcome in seed_outcomes):
        return "blocked"
    return "empty"


async def assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FetchFailure("rejected", "URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise FetchFailure("rejected", "URLs with credentials are not supported")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        raise FetchFailure("fetch_error", "Could not resolve URL host") from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise FetchFailure("rejected", "Private and local network URLs are not supported")


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
                    raise FetchFailure("fetch_error", "Redirect has no location")
                current_url = urljoin(current_url, location)
                continue
            if response.status_code in BLOCKED_HTTP_STATUSES:
                raise FetchFailure("blocked", f"HTTP {response.status_code}")
            response.raise_for_status()
            if "html" not in response.headers.get("content-type", ""):
                raise FetchFailure("non_html", "URL did not return HTML")
            html = response.text
            if looks_blocked_html(html):
                raise FetchFailure("blocked", "Blocked or challenge page detected")
            return html, str(response.url)
    raise FetchFailure("fetch_error", "Too many redirects")


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


def _outcome(url: str, status: str, detail: str | None = None) -> dict[str, str]:
    outcome = {"url": url, "status": status}
    if detail:
        outcome["detail"] = detail
    return outcome


def _failure_reason(error: Exception) -> tuple[str, str]:
    if isinstance(error, FetchFailure):
        return error.reason, str(error)
    if isinstance(error, httpx.HTTPStatusError):
        status = "blocked" if error.response.status_code in BLOCKED_HTTP_STATUSES else "fetch_error"
        return status, f"HTTP {error.response.status_code}"
    if isinstance(error, ScrapeError):
        return "fetch_error", str(error)
    if isinstance(error, httpx.HTTPError):
        return "fetch_error", type(error).__name__
    return "fetch_error", type(error).__name__


def _failure_token(reason: str, detail: str | None) -> str:
    return reason if not detail else f"{reason}:{detail}"


def _split_failure_token(token: str) -> tuple[str, str | None]:
    reason, _, detail = token.partition(":")
    return reason, detail or None


class PageLoadResult(NamedTuple):
    page: Page | None
    final_url: str
    render_detail: str | None
    failure: str | None
    html: str | None


async def _browser_render(url: str) -> tuple[str, str, str]:
    from app.browser import render_html

    html, final_url = await render_html(url)
    if looks_blocked_html(html):
        raise FetchFailure("blocked", "Blocked or challenge page detected")
    return html, final_url, "js_rendered"


async def _load_page(url: str, content_format: str | None, max_chars: int) -> PageLoadResult:
    html: str | None = None
    final_url = url
    render_detail: str | None = None

    try:
        html, final_url = await fetch_html(url)
    except Exception as error:
        reason, detail = _failure_reason(error)
        if not settings.browser_fallback or reason != "blocked":
            return PageLoadResult(None, url, None, _failure_token(reason, detail), None)
        try:
            html, final_url, render_detail = await _browser_render(url)
        except Exception as browser_error:
            browser_reason, browser_detail = _failure_reason(browser_error)
            return PageLoadResult(
                None, url, None, _failure_token(browser_reason, browser_detail), None
            )

    page = extract_page(html, final_url, content_format, max_chars)
    content = page.markdown or page.text or ""
    needs_browser_for_thin_content = (
        settings.browser_fallback
        and render_detail is None
        and len(content) < BROWSER_FALLBACK_MIN_EXTRACTABLE_CHARS
    )
    if needs_browser_for_thin_content:
        try:
            html, final_url, render_detail = await _browser_render(final_url)
            page = extract_page(html, final_url, content_format, max_chars)
            content = page.markdown or page.text or ""
        except Exception as error:
            reason, detail = _failure_reason(error)
            if content:
                return PageLoadResult(page, final_url, render_detail, None, html)
            return PageLoadResult(None, final_url, None, _failure_token(reason, detail), None)

    if not content:
        return PageLoadResult(None, final_url, render_detail, "empty", html)
    return PageLoadResult(page, final_url, render_detail, None, html)


async def scrape_website(
    request: WebsiteScrapeRequest,
) -> tuple[list[Page], list[dict[str, str]], dict[str, int] | None]:
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
    seed_status: dict[str, dict[str, str]] = {}
    include = to_list(request.include_urls)
    exclude = to_list(request.exclude_urls)
    deduped_skips = 0
    seeds_by_canonical: dict[str, list[str]] = {}
    for seed in seeds:
        seeds_by_canonical.setdefault(normalize_crawl_url(seed), []).append(seed)

    def mark_seed(canonical: str, status: str, detail: str | None = None) -> None:
        for seed in seeds_by_canonical.get(canonical, []):
            seed_status.setdefault(seed, _outcome(seed, status, detail))

    def url_is_seed(original_url: str, canonical: str) -> bool:
        return original_url in seeds or canonical in seeds_by_canonical

    while queue and len(pages) < page_limit:
        url, depth = queue.popleft()
        canonical = normalize_crawl_url(url)
        is_seed = url_is_seed(url, canonical)
        if canonical in visited:
            deduped_skips += 1
            if is_seed and url in seeds:
                existing = next(
                    (seed_status[s] for s in seeds_by_canonical.get(canonical, []) if s in seed_status),
                    None,
                )
                if existing:
                    mark_seed(canonical, existing["status"], existing.get("detail"))
            continue
        if not matches(url, include) or (exclude and matches(url, exclude)):
            continue
        visited.add(canonical)

        loaded = await _load_page(url, request.content_format, request.max_chars)

        if loaded.failure:
            if is_seed:
                reason, detail = _split_failure_token(loaded.failure)
                mark_seed(canonical, reason, detail)
            continue

        if loaded.page and (loaded.page.markdown or loaded.page.text):
            pages.append(loaded.page)
            if is_seed:
                mark_seed(canonical, "returned", loaded.render_detail)
        elif is_seed:
            mark_seed(canonical, "empty", loaded.render_detail)

        if loaded.html and follows_links and (request.max_depth is None or depth < request.max_depth):
            for link in links_from(loaded.html, loaded.final_url):
                if normalize_crawl_url(link) not in visited:
                    queue.append((link, depth + 1))

    seed_outcomes = [_outcome(url, "not_returned") if url not in seed_status else seed_status[url] for url in seeds]
    crawl_meta = None
    if follows_links:
        crawl_meta = {
            "visitedCount": len(visited),
            "returnedCount": len(pages),
            "dedupedSkips": deduped_skips,
        }
    return pages, seed_outcomes, crawl_meta
