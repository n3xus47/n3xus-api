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


def _entry_url(entry: dict) -> str:
    return entry.get("webpage_url") or entry.get("url") or ""


def _entry_identifier(entry: dict) -> str | None:
    if entry.get("id"):
        return str(entry["id"])
    url = _entry_url(entry)
    if "/shorts/" in url:
        return url.rstrip("/").split("/shorts/")[-1].split("?")[0] or None
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        return parsed.path.strip("/") or None
    value = parse_qs(parsed.query).get("v", [None])[0]
    return str(value) if value else None


def is_short_entry(entry: dict) -> bool:
    url = _entry_url(entry)
    if "/shorts/" in url:
        return True
    duration = entry.get("duration")
    return isinstance(duration, (int, float)) and 0 < duration <= 60


def normalize_video(entry: dict, channel_handle: str | None = None) -> dict:
    identifier = _entry_identifier(entry)
    url = _entry_url(entry)
    short = is_short_entry(entry)
    if identifier and not url:
        url = f"https://www.youtube.com/shorts/{identifier}" if short else f"https://www.youtube.com/watch?v={identifier}"
    channel = entry.get("channel") or entry.get("uploader")
    handle = channel_handle or entry.get("uploader_id") or entry.get("channel_id")
    return {
        "id": identifier,
        "title": entry.get("title"),
        "url": url or None,
        "channelId": entry.get("channel_id"),
        "channel": channel,
        "channelHandle": handle,
        "duration": entry.get("duration"),
        "viewCount": entry.get("view_count"),
        "isShort": short,
        "thumbnail": entry.get("thumbnail") or (f"https://i.ytimg.com/vi/{identifier}/hqdefault.jpg" if identifier else None),
    }


def normalize_entries(entries: list[dict], *, feed: str = "videos", channel_handle: str | None = None) -> list[dict]:
    normalized = [normalize_video(entry, channel_handle=channel_handle) for entry in entries]
    if feed == "shorts":
        normalized = [item for item in normalized if item.get("isShort")]
    elif feed == "videos":
        normalized = [item for item in normalized if not item.get("isShort")]
    return [item for item in normalized if item.get("id")]


def _metadata(target: str, flat: bool = False) -> dict:
    options = {"quiet": True, "skip_download": True, "extract_flat": flat, "noplaylist": not flat}
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(target, download=False)


async def _extract_entries(target: str) -> list[dict]:
    result = await asyncio.to_thread(_metadata, target, True)
    entries = result.get("entries") or [result]
    return [entry for entry in entries if isinstance(entry, dict)]


async def _channel_batch(handle: str, shorts: bool, max_items: int) -> dict:
    tab = "shorts" if shorts else "videos"
    primary = f"https://www.youtube.com/@{handle}/{tab}"
    source_urls = [primary]
    fallback_used = False
    try:
        entries = await _extract_entries(primary)
    except Exception as error:
        if not shorts:
            raise YouTubeError("YouTube metadata request failed") from error
        entries = []
    if shorts and not entries:
        fallback = f"https://www.youtube.com/@{handle}/videos"
        source_urls.append(fallback)
        fallback_used = True
        try:
            entries = await _extract_entries(fallback)
        except Exception as error:
            raise YouTubeError("YouTube metadata request failed") from error
    videos = normalize_entries(entries, feed="shorts" if shorts else "videos", channel_handle=handle)[:max_items]
    return {"videos": videos, "sourceUrls": source_urls, "fallbackUsed": fallback_used}


async def channel_videos(channels: list[str], shorts: bool, max_items: int) -> dict:
    if not channels:
        return {"videos": [], "sourceUrls": [], "collectionState": "empty", "fallbackUsed": False}
    per_channel = max(1, max_items // len(channels))
    collected: list[dict] = []
    source_urls: list[str] = []
    fallback_used = False
    for handle in channels:
        if len(collected) >= max_items:
            break
        batch = await _channel_batch(handle, shorts, per_channel)
        collected.extend(batch["videos"])
        source_urls.extend(batch["sourceUrls"])
        fallback_used = fallback_used or batch["fallbackUsed"]
    videos = collected[:max_items]
    state = "complete" if videos else "empty"
    if fallback_used and videos:
        state = "partial"
    return {"videos": videos, "sourceUrls": source_urls, "collectionState": state, "fallbackUsed": fallback_used}


async def search_videos(query: str, max_items: int) -> dict:
    target = f"ytsearch{max_items}:{query}"
    try:
        entries = await _extract_entries(target)
    except Exception as error:
        raise YouTubeError("YouTube metadata request failed") from error
    videos = normalize_entries(entries, feed="any")[:max_items]
    return {
        "videos": videos,
        "sourceUrls": [target],
        "collectionState": "complete" if videos else "empty",
        "fallbackUsed": False,
    }


async def transcript(url: str, include_segments: bool, max_chars: int) -> dict:
    identifier = video_id(url)
    try:
        entries = await asyncio.to_thread(YouTubeTranscriptApi().fetch, identifier, languages=["pl", "en"])
    except Exception as error:
        raise YouTubeError("No public transcript is available") from error
    segments = [{"text": item.text, "start": item.start, "duration": item.duration} for item in entries]
    text = " ".join(item["text"] for item in segments)
    output = {"text": text[:max_chars], "truncated": len(text) > max_chars, "videoId": identifier, "sourceUrl": url}
    if include_segments:
        output["segments"] = segments
    return output


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
    return {"image": f"data:image/jpeg;base64,{encoded}", "thumbnail": source, "videoId": identifier, "sourceUrl": url}
