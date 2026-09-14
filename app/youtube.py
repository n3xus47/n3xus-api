import asyncio
import base64
from urllib.parse import parse_qs, urlparse

import httpx
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from app.config import settings


class YouTubeError(Exception):
    pass


def video_id(url: str) -> str:
    parsed = urlparse(url)
    value = parse_qs(parsed.query).get("v", [None])[0] if parsed.hostname != "youtu.be" else parsed.path.strip("/")
    if not value:
        raise YouTubeError("A valid YouTube video URL is required")
    return value


def _metadata(target: str, flat: bool = False) -> dict:
    options = {"quiet": True, "skip_download": True, "extract_flat": flat, "noplaylist": not flat}
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(target, download=False)


async def transcript(url: str, include_segments: bool, max_chars: int) -> dict:
    identifier = video_id(url)
    try:
        entries = await asyncio.to_thread(YouTubeTranscriptApi().fetch, identifier, languages=["pl", "en"])
    except Exception as error:
        raise YouTubeError("No public transcript is available") from error
    segments = [{"text": item.text, "start": item.start, "duration": item.duration} for item in entries]
    text = " ".join(item["text"] for item in segments)
    output = {"text": text[:max_chars], "truncated": len(text) > max_chars}
    if include_segments:
        output["segments"] = segments
    return output


async def metadata(target: str, shorts: bool = False, max_items: int = 5) -> object:
    try:
        result = await asyncio.to_thread(_metadata, target, True)
    except Exception as error:
        raise YouTubeError("YouTube metadata request failed") from error
    entries = result.get("entries") or [result]
    if shorts:
        entries = [entry for entry in entries if "/shorts/" in (entry.get("url") or entry.get("webpage_url") or "")]
    return entries[:max_items]


async def thumbnail(url: str) -> dict:
    identifier = video_id(url)
    source = f"https://i.ytimg.com/vi/{identifier}/maxresdefault.jpg"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_secs) as client:
            response = await client.get(source)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise YouTubeError("YouTube thumbnail request failed") from error
    encoded = base64.b64encode(response.content).decode()
    return {"image": f"data:image/jpeg;base64,{encoded}", "thumbnail": source}
