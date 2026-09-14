from uuid import uuid4

import httpx
import pytest

from app.instagram_public import collection_state, parse_instagram_post, parse_instagram_profile
from app.main import app

PROFILE_HTML = """
<html><head>
<meta property="og:title" content="NASA (&#064;nasa) &#x2022; Instagram photos and videos">
<meta property="og:description" content="104M Followers, 95 Following, 4,920 Posts - See Instagram photos and videos from NASA (&#064;nasa)">
<meta property="og:url" content="https://www.instagram.com/nasa/">
<meta property="og:image" content="https://cdn.example/avatar.jpg">
</head><body></body></html>
"""

POST_HTML = """
<html><head>
<meta property="og:title" content="NASA on Instagram: &quot;Making the impossible possible.&quot;">
<meta property="og:description" content="12K likes, 120 comments - NASA on January 1, 2024: Making the impossible possible.">
<meta property="og:url" content="https://www.instagram.com/p/ABC123xyz/">
<meta property="og:image" content="https://cdn.example/post.jpg">
</head><body></body></html>
"""

LOGIN_HTML = """
<html><head>
<meta property="og:title" content="Login &#x2022; Instagram">
<meta property="og:description" content="Welcome back to Instagram.">
</head><body></body></html>
"""


def test_parse_instagram_profile_from_open_graph():
    profile = parse_instagram_profile(PROFILE_HTML, "nasa", "https://www.instagram.com/nasa/")

    assert profile["username"] == "nasa"
    assert profile["displayName"] == "NASA"
    assert profile["followerCount"] == 104_000_000
    assert profile["followingCount"] == 95
    assert profile["postCount"] == 4920
    assert profile["profileUrl"] == "https://www.instagram.com/nasa/"
    assert profile["avatarUrl"] == "https://cdn.example/avatar.jpg"


def test_parse_instagram_post_from_open_graph():
    post = parse_instagram_post(POST_HTML, "https://www.instagram.com/p/ABC123xyz/")

    assert post["id"] == "ABC123xyz"
    assert post["url"] == "https://www.instagram.com/p/ABC123xyz/"
    assert post["authorUsername"] == "nasa"
    assert "impossible" in post["caption"].lower()
    assert post["mediaUrl"] == "https://cdn.example/post.jpg"


def test_collection_state_blocked_on_login_wall():
    assert collection_state(LOGIN_HTML, profiles=[], posts=[]) == "blocked"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_instagram_profile_endpoint_returns_structured_records(client, monkeypatch):
    async def fake_fetch(_resource, payload):
        return {
            "profiles": [parse_instagram_profile(PROFILE_HTML, payload["usernames"][0], "https://www.instagram.com/nasa/")],
            "posts": [],
            "sourceUrls": ["https://www.instagram.com/nasa/"],
            "collectionState": "partial",
        }

    monkeypatch.setattr("app.main.instagram_collect", fake_fetch)
    response = await client.post(
        "/v1/scrape/instagram/profile",
        headers={"Idempotency-Key": f"ig-profile-{uuid4()}"},
        json={"usernames": ["nasa"]},
    )

    body = response.json()
    assert body["status"] == "succeeded"
    assert body["capability"] == "scrape.instagram"
    assert body["output"]["profiles"][0]["username"] == "nasa"
    assert body["source"]["name"] == "instagram-public-og"
    assert body["source"]["collectionState"] == "partial"


async def test_capabilities_mark_instagram_structured(client):
    response = await client.get("/v1/capabilities", params={"capability": "scrape.instagram"})
    capability = response.json()["output"]
    assert capability["supportLevel"] == "structured"
    assert capability["adapter"] == "instagram-public-og"
