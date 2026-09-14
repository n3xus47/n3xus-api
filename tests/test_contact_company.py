from app.contact import build_company_profile, company_page_urls, published_emails, sourced
from app.models import Page


def test_sourced_omits_empty_values():
    assert sourced("  ", "https://example.com", "title") is None
    item = sourced("Example", "https://example.com", "title")
    assert item["value"] == "Example"
    assert item["provenance"]["field"] == "title"


def test_published_emails_only_keeps_same_domain_addresses():
    text = "Reach us at team@example.com or vendor@other.com"
    found = published_emails(text, "example.com", "https://example.com/contact")
    assert len(found) == 1
    assert found[0]["value"] == "team@example.com"


def test_build_company_profile_keeps_per_field_provenance():
    pages = [
        Page(url="https://example.com", title="Example Corp", description="About us", text="team@example.com"),
        Page(url="https://example.com/contact", title="Contact", text="team@example.com"),
    ]
    profile, sources = build_company_profile(pages, "example.com")
    assert profile["name"]["provenance"]["field"] == "document_title"
    assert profile["website"]["value"] == "https://example.com"
    assert len(profile["emails"]) == 1
    assert len(sources) == 2
    assert company_page_urls("example.com")[0] == "https://example.com"
