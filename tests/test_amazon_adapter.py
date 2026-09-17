from pathlib import Path

import pytest

from app.amazon_adapter import (
    amazon_product,
    amazon_reviews,
    amazon_search,
    detect_blocked,
    parse_product_record,
    parse_review_records,
    parse_search_listings,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_detect_blocked_sample():
    assert detect_blocked(load("amazon_blocked_sample.html"))


def test_parse_search_listings_from_fixture():
    listings = parse_search_listings(load("amazon_search_sample.html"), "https://www.amazon.com/s?k=test", 10)

    assert len(listings) == 2
    assert listings[0]["asin"] == "B08N5WRWNW"
    assert listings[0]["title"] == "Test Product One"
    assert listings[0]["price"] == "$29.99"
    assert "url" in listings[0]


def test_parse_product_record_from_fixture():
    product = parse_product_record(load("amazon_product_sample.html"), "https://www.amazon.com/dp/B08N5WRWNW")

    assert product["asin"] == "B08N5WRWNW"
    assert product["title"] == "Sample Product Title"
    assert product["price"] == "$19.95"


def test_parse_review_records_from_fixture():
    reviews = parse_review_records(load("amazon_reviews_sample.html"), 10)

    assert len(reviews) == 2
    assert reviews[0]["body"] == "Great product for testing."
    assert reviews[0]["rating"] == "5.0 out of 5 stars"


async def test_amazon_search_blocked(monkeypatch):
    async def fake_fetch(_url):
        return load("amazon_blocked_sample.html"), "https://www.amazon.com/s?k=test"

    monkeypatch.setattr("app.amazon_adapter.fetch_html", fake_fetch)
    monkeypatch.setattr("app.browser.render_html", fake_fetch)

    output = await amazon_search({"query": "test"})

    assert output["collectionState"] == "blocked"
    assert output["listings"] == []
    assert "text" not in str(output)


async def test_amazon_search_returns_structured_listings(monkeypatch):
    async def fake_fetch(_url):
        return load("amazon_search_sample.html"), "https://www.amazon.com/s?k=test"

    monkeypatch.setattr("app.amazon_adapter.fetch_html", fake_fetch)

    output = await amazon_search({"query": "test", "maxItems": 5})

    assert output["collectionState"] == "complete"
    assert output["items"] == output["listings"]
    assert output["listings"][0]["title"] == "Test Product One"
