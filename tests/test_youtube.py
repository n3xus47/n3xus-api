from app import youtube as yt


def test_normalize_video_maps_flat_search_entry():
    record = yt.normalize_video(
        {
            "id": "abc123",
            "title": "Demo",
            "url": "https://www.youtube.com/watch?v=abc123",
            "duration": 120,
            "view_count": 42,
            "channel_id": "UCxyz",
            "channel": "Example Channel",
            "uploader_id": "examplechannel",
        }
    )
    assert record == {
        "id": "abc123",
        "title": "Demo",
        "url": "https://www.youtube.com/watch?v=abc123",
        "channelId": "UCxyz",
        "channel": "Example Channel",
        "channelHandle": "examplechannel",
        "duration": 120,
        "viewCount": 42,
        "isShort": False,
        "thumbnail": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
    }


def test_normalize_video_detects_shorts_url_and_sets_canonical_url():
    record = yt.normalize_video(
        {
            "id": "short1",
            "title": "Short clip",
            "webpage_url": "https://www.youtube.com/shorts/short1",
            "duration": 15,
        },
        channel_handle="Creator",
    )
    assert record["isShort"] is True
    assert record["url"] == "https://www.youtube.com/shorts/short1"
    assert record["channelHandle"] == "Creator"


def test_filter_entries_keeps_only_shorts_when_requested():
    entries = [
        {"id": "a", "title": "A", "url": "https://www.youtube.com/watch?v=a", "duration": 300},
        {"id": "b", "title": "B", "url": "https://www.youtube.com/shorts/b", "duration": 20},
        {"id": "c", "title": "C", "url": "https://www.youtube.com/watch?v=c", "duration": 45},
    ]
    shorts = yt.normalize_entries(entries, feed="shorts")
    assert [item["id"] for item in shorts] == ["b", "c"]


def test_filter_entries_excludes_shorts_from_channel_feed():
    entries = [
        {"id": "a", "title": "A", "url": "https://www.youtube.com/watch?v=a", "duration": 300},
        {"id": "b", "title": "B", "url": "https://www.youtube.com/shorts/b", "duration": 20},
    ]
    videos = yt.normalize_entries(entries, feed="videos")
    assert [item["id"] for item in videos] == ["a"]


async def test_channel_videos_merges_multiple_handles(monkeypatch):
    async def fake_batch(handle: str, shorts: bool, max_items: int):
        return {
            "videos": [yt.normalize_video({"id": handle, "title": handle, "url": f"https://www.youtube.com/watch?v={handle}"}, channel_handle=handle)],
            "sourceUrls": [f"https://www.youtube.com/@{handle}/videos"],
            "fallbackUsed": False,
        }

    monkeypatch.setattr(yt, "_channel_batch", fake_batch)
    result = await yt.channel_videos(["one", "two"], shorts=False, max_items=3)
    assert [video["channelHandle"] for video in result["videos"]] == ["one", "two"]
    assert len(result["sourceUrls"]) == 2
