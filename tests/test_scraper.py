from app.scraper import extract_page


def test_extract_page_removes_navigation_and_applies_content_format():
    page = extract_page(
        """
        <html lang='en'><head><title>Article</title><meta name='description' content='Summary'></head>
        <body><nav>Menu links</nav><article><h1>Hello</h1><p>Useful content.</p></article></body></html>
        """,
        "https://example.com/article",
        "markdown",
        1_000,
    )

    assert page.url == "https://example.com/article"
    assert page.title == "Article"
    assert page.description == "Summary"
    assert page.language == "en"
    assert page.markdown is not None
    assert "Useful content" in page.markdown
    assert page.text is None


def test_extract_page_marks_truncated_content():
    page = extract_page(
        "<html><body><article><p>" + "x" * 1_500 + "</p></article></body></html>",
        "https://example.com/article",
        "text",
        1_000,
    )

    assert page.truncated is True
    assert page.total_chars == 1_500
    assert page.text is not None
    assert len(page.text) == 1_000
