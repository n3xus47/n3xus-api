import asyncio
from io import BytesIO

import httpx
from pypdf import PdfReader

from app.config import settings
from app.scraper import ScrapeError, assert_public_url


class PdfError(Exception):
    pass


async def extract_pdf(url: str, max_pages: int | None, max_chars: int) -> dict:
    try:
        await assert_public_url(url)
        async with httpx.AsyncClient(timeout=settings.request_timeout_secs, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        if len(response.content) > 50 * 1024 * 1024:
            raise PdfError("PDF exceeds 50 MB")
        reader = await asyncio.to_thread(PdfReader, BytesIO(response.content))
        pages = reader.pages[:max_pages] if max_pages else reader.pages
        text = "\n".join(page.extract_text() or "" for page in pages).strip()
        if not text:
            raise PdfError("PDF has no readable text layer")
        metadata = reader.metadata or {}
        return {
            "text": text[:max_chars], "title": metadata.title, "author": metadata.author,
            "pageCount": len(reader.pages), "truncated": len(text) > max_chars or (max_pages is not None and len(reader.pages) > max_pages),
        }
    except (httpx.HTTPError, ScrapeError) as error:
        raise PdfError("PDF fetch failed") from error
