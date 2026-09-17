"""Normalized Amazon public-page adapter (US/UK/DE marketplaces, no credentials)."""
import re
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from app.scraper import ScrapeError, fetch_html

MARKETPLACES = {
    "us": {"host": "amazon.com", "label": "US"},
    "uk": {"host": "amazon.co.uk", "label": "UK"},
    "de": {"host": "amazon.de", "label": "DE"},
}

BLOCKED_MARKERS = (
    "type the characters you see in this image",
    "validatecaptcha",
    "sorry! something went wrong",
    "robot check",
)


def marketplace_config(marketplace: str) -> dict:
    key = str(marketplace or "US").lower()
    return MARKETPLACES.get(key, MARKETPLACES["us"])


def marketplace_coverage() -> list[dict]:
    return [{"code": code, "host": info["host"], "label": info["label"]} for code, info in MARKETPLACES.items()]


def detect_blocked(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in BLOCKED_MARKERS)


def _clean_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _parse_price(node) -> str | None:
    if not node:
        return None
    offscreen = node.select_one(".a-offscreen")
    if offscreen:
        return _clean_text(offscreen.get_text())
    return _clean_text(node.get_text())


def _review_star_label(rating_node) -> str | None:
    if not rating_node:
        return None
    aria_label = rating_node.get("aria-label")
    if isinstance(aria_label, str) and aria_label:
        return _clean_text(aria_label)
    return _clean_text(rating_node.get_text())


async def _fetch_page(url: str) -> tuple[str, str]:
    from app.browser import render_html
    from app.human_challenge import looks_like_human_gate

    html: str | None = None
    final_url = url
    try:
        html, final_url = await fetch_html(url)
        gated = detect_blocked(html) or looks_like_human_gate(html, final_url)
    except ScrapeError:
        gated = True
    if gated:
        try:
            html, final_url = await render_html(url)
        except ScrapeError as error:
            if html is None:
                raise RuntimeError(str(error)) from error
    if html is None:
        raise RuntimeError("Amazon page fetch failed")
    return html, final_url


def parse_search_listings(html: str, page_url: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[dict] = []
    seen: set[str] = set()
    for card in soup.select('[data-component-type="s-search-result"][data-asin]'):
        asin = _clean_text(card.get("data-asin"))
        if not asin or asin in seen:
            continue
        title_node = card.select_one("h2 a span") or card.select_one("h2 span")
        title = _clean_text(title_node.get_text() if title_node else None)
        if not title:
            continue
        link = card.select_one("h2 a")
        href = link.get("href") if link else None
        url = urljoin(page_url, href) if isinstance(href, str) else f"{page_url.split('/s?')[0]}/dp/{asin}"
        price = _parse_price(card.select_one(".a-price"))
        rating_label = card.select_one('[aria-label*="out of 5 stars"]')
        rating = _clean_text(rating_label.get("aria-label") if rating_label else None)
        review_count_node = card.select_one('[aria-label*="ratings"]')
        review_count = _clean_text(review_count_node.get("aria-label") if review_count_node else None)
        record = {"asin": asin, "title": title, "url": url, "marketplaceUrl": url}
        if price:
            record["price"] = price
        if rating:
            record["rating"] = rating
        if review_count:
            record["reviewCount"] = review_count
        listings.append(record)
        seen.add(asin)
        if len(listings) >= limit:
            break
    return listings


def parse_product_record(html: str, page_url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("#productTitle")
    title = _clean_text(title_node.get_text()) if title_node else None
    asin_input = soup.select_one("#ASIN")
    asin = _clean_text(asin_input.get("value") if asin_input else None)
    if not asin:
        match = re.search(r"/dp/([A-Z0-9]{10})", page_url)
        asin = match.group(1) if match else None
    if not title or not asin:
        return None
    record = {"asin": asin, "title": title, "url": page_url}
    price = _parse_price(soup.select_one("#corePriceDisplay_desktop_feature_div .a-price") or soup.select_one(".a-price"))
    if price:
        record["price"] = price
    rating = soup.select_one("#acrPopover")
    if rating and rating.get("title"):
        record["rating"] = _clean_text(rating.get("title"))
    review_text = soup.select_one("#acrCustomerReviewText")
    if review_text:
        record["reviewCount"] = _clean_text(review_text.get_text())
    return record


def parse_review_records(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    reviews: list[dict] = []
    for card in soup.select('[data-hook="review"]'):
        body_node = card.select_one('[data-hook="review-body"] span') or card.select_one('[data-hook="review-body"]')
        body = _clean_text(body_node.get_text() if body_node else None)
        if not body:
            continue
        rating = _review_star_label(card.select_one('[data-hook="review-star-rating"]'))
        date_node = card.select_one('[data-hook="review-date"]')
        record = {"body": body}
        if rating:
            record["rating"] = rating
        if date_node:
            record["reviewedAt"] = _clean_text(date_node.get_text())
        review_id = card.get("id")
        if isinstance(review_id, str) and review_id:
            record["reviewId"] = review_id
        reviews.append(record)
        if len(reviews) >= limit:
            break
    return reviews


def _response(resource: str, marketplace: dict, collection_state: str, **payload: object) -> dict:
    return {
        "resource": resource,
        "marketplace": marketplace["label"],
        "marketplaceHost": marketplace["host"],
        "coverage": marketplace_coverage(),
        "collectionState": collection_state,
        **payload,
    }


async def amazon_search(payload: dict) -> dict:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    marketplace = marketplace_config(payload.get("marketplace", "US"))
    limit = min(int(payload.get("maxItems", 10)), 30)
    url = f"https://www.{marketplace['host']}/s?k={quote_plus(query.strip())}"
    html, final_url = await _fetch_page(url)
    if detect_blocked(html):
        return _response("search", marketplace, "blocked", query=query.strip(), listings=[], items=[])
    listings = parse_search_listings(html, final_url, limit)
    state = "complete" if listings else "empty"
    return _response("search", marketplace, state, query=query.strip(), listings=listings, items=listings)


async def amazon_product(payload: dict) -> dict:
    marketplace = marketplace_config(payload.get("marketplace", "US"))
    url = payload.get("url")
    asin = payload.get("asin")
    if not url and isinstance(asin, str):
        url = f"https://www.{marketplace['host']}/dp/{asin.strip()}"
    if not isinstance(url, str) or not url.strip():
        raise ValueError("asin or url is required")
    parsed = urlparse(url)
    if parsed.hostname and marketplace["host"] not in parsed.hostname:
        raise ValueError(f"url must target marketplace host {marketplace['host']}")
    html, final_url = await _fetch_page(url.strip())
    if detect_blocked(html):
        return _response("product", marketplace, "blocked", product=None)
    product = parse_product_record(html, final_url)
    state = "complete" if product else "empty"
    return _response("product", marketplace, state, product=product)


async def amazon_reviews(payload: dict) -> dict:
    asin = payload.get("asin")
    if not isinstance(asin, str) or not asin.strip():
        raise ValueError("asin is required")
    marketplace = marketplace_config(payload.get("marketplace", "US"))
    limit = min(int(payload.get("maxItems", 10)), 30)
    url = f"https://www.{marketplace['host']}/product-reviews/{asin.strip()}"
    html, final_url = await _fetch_page(url)
    if detect_blocked(html):
        return _response("reviews", marketplace, "blocked", asin=asin.strip(), reviews=[])
    reviews = parse_review_records(html, limit)
    state = "complete" if reviews else "empty"
    return _response("reviews", marketplace, state, asin=asin.strip(), reviews=reviews)
