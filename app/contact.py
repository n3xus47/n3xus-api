"""Privacy-preserving contact helpers based only on public company pages.

No broker data, mailbox probing, or guessed addresses are used.
"""
import re
from urllib.parse import urlparse

from app.models import Page, WebsiteScrapeRequest
from app.scraper import scrape_website

COMPANY_PATHS = ("", "/about", "/about-us", "/contact", "/contact-us")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def normalise_domain(value: str) -> str:
    candidate = value if "://" in value else f"https://{value}"
    domain = urlparse(candidate).hostname
    if not domain:
        raise ValueError("domain must be a public hostname or URL")
    return domain.lower()


def company_page_urls(hostname: str) -> list[str]:
    return [f"https://{hostname}" if path == "" else f"https://{hostname}{path}" for path in COMPANY_PATHS]


def sourced(value: str | None, url: str, field: str) -> dict | None:
    if not value or not str(value).strip():
        return None
    return {"value": str(value).strip(), "provenance": {"url": url, "field": field}}


def sourced_value(field: object) -> str | None:
    if isinstance(field, dict):
        value = field.get("value")
        return str(value) if value is not None else None
    return None


def published_emails(text: str, hostname: str, page_url: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for address in EMAIL_PATTERN.findall(text or ""):
        _, email_domain = address.lower().rsplit("@", 1)
        if email_domain != hostname or address.lower() in seen:
            continue
        seen.add(address.lower())
        item = sourced(address, page_url, "published_text")
        if item:
            found.append(item)
    return found


def build_company_profile(pages: list[Page], hostname: str) -> tuple[dict, list[dict]]:
    homepage = pages[0]
    profile: dict[str, object] = {
        "name": sourced(homepage.title, homepage.url, "document_title"),
        "description": sourced(homepage.description, homepage.url, "meta_description"),
        "website": sourced(homepage.url, homepage.url, "canonical_page_url"),
        "emails": [],
    }
    emails: list[dict] = []
    seen_addresses: set[str] = set()
    for page in pages:
        for item in published_emails(page.text or "", hostname, page.url):
            key = item["value"].lower()
            if key in seen_addresses:
                continue
            seen_addresses.add(key)
            emails.append(item)
    profile["emails"] = emails
    sources = [{"url": page.url, "title": page.title} for page in pages]
    return profile, sources


async def company(domain: str) -> dict:
    hostname = normalise_domain(domain)
    pages, _ = await scrape_website(
        WebsiteScrapeRequest(urls=company_page_urls(hostname), contentFormat="text", maxChars=30_000)
    )
    if not pages:
        return {"matchStatus": "not_found", "domain": hostname, "profile": {}, "sources": []}

    profile, sources = build_company_profile(pages, hostname)
    return {
        "matchStatus": "partial",
        "domain": hostname,
        "name": sourced_value(profile.get("name")),
        "description": sourced_value(profile.get("description")),
        "website": sourced_value(profile.get("website")),
        "profile": profile,
        "sources": sources,
    }


async def find_email(first_name: str, last_name: str, domain: str) -> dict:
    hostname = normalise_domain(domain)
    pages, _ = await scrape_website(WebsiteScrapeRequest(urls=[f"https://{hostname}", f"https://{hostname}/contact"], contentFormat="text", maxPages=2, maxChars=50_000))
    expected = {f"{first_name}.{last_name}".lower(), f"{first_name}{last_name}".lower(), f"{first_name[0]}{last_name}".lower()}
    for page in pages:
        matches = EMAIL_PATTERN.findall(page.text or "")
        for address in matches:
            local, found_domain = address.lower().rsplit("@", 1)
            if found_domain == hostname and local.replace("_", ".") in expected:
                return {"email": address, "confidence": "public_page_match", "acceptAll": False, "sources": [{"url": page.url}]}
    return {"email": None, "confidence": None, "acceptAll": False, "sources": []}


def verify_email(email: str) -> dict:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return {"email": email, "verdict": "undeliverable", "score": 0, "reason": "invalid_syntax"}
    return {"email": email, "verdict": "unknown", "score": 0, "reason": "Local mode does not probe mailboxes"}
