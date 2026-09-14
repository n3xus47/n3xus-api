"""Structured Instagram records from public Open Graph metadata only."""
from __future__ import annotations

import html as html_lib
import re
import httpx

from app.config import settings
from app.scraper import scrape_website
from app.models import WebsiteScrapeRequest

_OG_TAG = re.compile(
    r'<meta\s+(?:property="og:([^"]+)"\s+content="([^"]*)"|content="([^"]*)"\s+property="og:([^"]+)")',
    re.IGNORECASE,
)
_PROFILE_TITLE = re.compile(r"^(.*?)\s+\(@([^)]+)\)\s+•", re.IGNORECASE)
_PROFILE_STATS = re.compile(
    r"^([\d,.]+[KMB]?)\s+Followers,\s+([\d,.]+[KMB]?)\s+Following,\s+([\d,.]+[KMB]?)\s+Posts",
    re.IGNORECASE,
)
_POST_ID = re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)")
_POST_AUTHOR = re.compile(r"^(.+?)\s+on Instagram:", re.IGNORECASE)


def _og_meta(page_html: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for match in _OG_TAG.finditer(page_html):
        key = match.group(1) or match.group(4)
        value = match.group(2) or match.group(3)
        if key:
            meta[key.lower()] = html_lib.unescape(value or "")
    return meta


def parse_count(raw: str) -> int | None:
    cleaned = raw.replace(",", "").strip().upper()
    if not cleaned:
        return None
    multiplier = 1
    if cleaned.endswith("K"):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith("M"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith("B"):
        multiplier = 1_000_000_000
        cleaned = cleaned[:-1]
    try:
        return int(float(cleaned) * multiplier)
    except ValueError:
        return None


def collection_state(page_html: str, *, profiles: list[dict], posts: list[dict]) -> str:
    title = _og_meta(page_html).get("title", "").lower()
    if "log in" in title or title.startswith("login"):
        return "blocked"
    if not profiles and not posts:
        return "empty"
    if posts:
        return "complete"
    return "partial"


def parse_instagram_profile(page_html: str, requested_username: str, profile_url: str) -> dict:
    og = _og_meta(page_html)
    title = og.get("title", "")
    display_name = requested_username
    username = requested_username.lstrip("@")
    if match := _PROFILE_TITLE.match(title):
        display_name, username = match.group(1).strip(), match.group(2).strip().lstrip("@")
    follower_count = following_count = post_count = None
    if match := _PROFILE_STATS.match(og.get("description", "")):
        follower_count = parse_count(match.group(1))
        following_count = parse_count(match.group(2))
        post_count = parse_count(match.group(3))
    return {
        "username": username,
        "displayName": display_name,
        "bio": None,
        "followerCount": follower_count,
        "followingCount": following_count,
        "postCount": post_count,
        "profileUrl": og.get("url") or profile_url,
        "avatarUrl": og.get("image"),
    }


def parse_instagram_post(page_html: str, post_url: str) -> dict:
    og = _og_meta(page_html)
    title = og.get("title", "")
    author = None
    caption = title
    if match := _POST_AUTHOR.match(title):
        author = match.group(1).strip().lower().replace(" ", "")
        caption = title.split(":", 1)[-1].strip().strip('"')
    shortcode = None
    if match := _POST_ID.search(og.get("url") or post_url):
        shortcode = match.group(1)
    return {
        "id": shortcode,
        "url": og.get("url") or post_url,
        "authorUsername": author,
        "caption": caption or og.get("description"),
        "publishedAt": None,
        "mediaUrl": og.get("image"),
    }


def _optional_url_list(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [url for url in raw if isinstance(url, str)]
    return []


def _collect_result(
    *,
    profiles: list[dict],
    posts: list[dict],
    source_urls: list[str],
    state_html: str,
) -> dict:
    return {
        "profiles": profiles,
        "posts": posts,
        "sourceUrls": source_urls,
        "collectionState": collection_state(state_html, profiles=profiles, posts=posts),
    }


async def _fetch_html(url: str) -> str:
    request = WebsiteScrapeRequest(urls=[url], contentFormat="text", maxPages=1, maxChars=500_000)
    pages, _ = await scrape_website(request)
    if not pages:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_secs,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    page = pages[0]
    return page.text or page.markdown or ""


def _require_usernames(payload: dict) -> list[str]:
    usernames = payload.get("usernames") or payload.get("handles")
    if not isinstance(usernames, list) or not usernames or not all(isinstance(name, str) for name in usernames):
        raise ValueError("usernames must be a non-empty list")
    return usernames


async def instagram_collect(resource: str, payload: dict) -> dict:
    if resource == "comments":
        url = payload.get("url")
        if not isinstance(url, str):
            raise ValueError("url is required")
        html = await _fetch_html(url)
        posts = [parse_instagram_post(html, url)]
        return _collect_result(profiles=[], posts=posts, source_urls=[url], state_html=html)

    if resource not in {"profile", "posts"}:
        raise ValueError("Unsupported Instagram resource")

    usernames = _require_usernames(payload)
    post_urls = _optional_url_list(payload.get("urls"))
    profiles: list[dict] = []
    source_urls: list[str] = []
    state_html = ""
    for name in usernames:
        profile_url = f"https://www.instagram.com/{name.lstrip('@')}/"
        state_html = await _fetch_html(profile_url)
        profiles.append(parse_instagram_profile(state_html, name, profile_url))
        source_urls.append(profile_url)
    posts: list[dict] = []
    for post_url in post_urls:
        post_html = await _fetch_html(post_url)
        posts.append(parse_instagram_post(post_html, post_url))
        source_urls.append(post_url)
    return _collect_result(profiles=profiles, posts=posts, source_urls=source_urls, state_html=state_html)
