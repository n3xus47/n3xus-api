"""Privacy-preserving contact helpers based only on public company pages.

No broker data, mailbox probing, or guessed addresses are used.
"""
import re
from urllib.parse import urlparse

from app.models import WebsiteScrapeRequest
from app.scraper import scrape_website

def normalise_domain(value: str) -> str:
    candidate = value if "://" in value else f"https://{value}"
    domain = urlparse(candidate).hostname
    if not domain:
        raise ValueError("domain must be a public hostname or URL")
    return domain.lower()


async def company(domain: str) -> dict:
    hostname = normalise_domain(domain)
    pages, _ = await scrape_website(WebsiteScrapeRequest(urls=f"https://{hostname}", contentFormat="markdown", maxChars=20_000))
    if not pages:
        return {"matchStatus": "not_found", "domain": hostname}
    page = pages[0]
    return {"matchStatus": "partial", "domain": hostname, "name": page.title, "description": page.description, "website": page.url}


async def find_email(first_name: str, last_name: str, domain: str) -> dict:
    hostname = normalise_domain(domain)
    pages, _ = await scrape_website(WebsiteScrapeRequest(urls=[f"https://{hostname}", f"https://{hostname}/contact"], contentFormat="text", maxPages=2, maxChars=50_000))
    expected = {f"{first_name}.{last_name}".lower(), f"{first_name}{last_name}".lower(), f"{first_name[0]}{last_name}".lower()}
    for page in pages:
        matches = re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", page.text or "", re.I)
        for address in matches:
            local, found_domain = address.lower().rsplit("@", 1)
            if found_domain == hostname and local.replace("_", ".") in expected:
                return {"email": address, "confidence": "public_page_match", "acceptAll": False, "sources": [{"url": page.url}]}
    return {"email": None, "confidence": None, "acceptAll": False, "sources": []}


def verify_email(email: str) -> dict:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return {"email": email, "verdict": "undeliverable", "score": 0, "reason": "invalid_syntax"}
    return {"email": email, "verdict": "unknown", "score": 0, "reason": "Local mode does not probe mailboxes"}
