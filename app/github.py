import base64

import httpx

from app.config import settings


class GitHubError(Exception):
    pass


async def github_get(path: str, params: dict | None = None) -> object:
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_secs, headers={"Accept": "application/vnd.github+json", "User-Agent": settings.user_agent}) as client:
            response = await client.get(f"https://api.github.com{path}", params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise GitHubError("GitHub public API request failed") from error


def compact_user(user: dict) -> dict:
    return {key: user.get(key) for key in ("login", "id", "type", "name", "company", "blog", "location", "email", "bio", "followers", "following", "public_repos", "html_url", "created_at", "updated_at")}


async def profile(usernames: list[str]) -> list[dict]:
    return [compact_user(await github_get(f"/users/{username}")) for username in usernames]


async def repository(name: str) -> dict:
    repo = await github_get(f"/repos/{name}")
    languages = await github_get(f"/repos/{name}/languages")
    readme = None
    try:
        raw_readme = await github_get(f"/repos/{name}/readme")
        readme = base64.b64decode(raw_readme["content"]).decode("utf-8", errors="replace")
    except GitHubError:
        pass
    return {"repository": repo, "languages": languages, "readme": readme}


async def list_resource(repository: str, resource: str, payload: dict) -> object:
    params = {"state": payload.get("state", "open"), "per_page": min(payload.get("maxItems", 30), 100)}
    if payload.get("pageToken"):
        params["page"] = payload["pageToken"]
    return await github_get(f"/repos/{repository}/{resource}", params)


async def search(payload: dict) -> object:
    kind = payload.get("type", "repositories")
    query = payload["query"]
    if language := payload.get("language"):
        query += f" language:{language}"
    endpoint = {"repositories": "repositories", "issues": "issues", "pull_requests": "issues", "code": "code"}.get(kind)
    if not endpoint:
        raise GitHubError("Unsupported GitHub search type")
    return await github_get(f"/search/{endpoint}", {"q": query, "per_page": min(payload.get("maxItems", 30), 100)})


async def contents(payload: dict) -> object:
    path = payload.get("path", "")
    params = {"ref": payload["ref"]} if payload.get("ref") else None
    return await github_get(f"/repos/{payload['repository']}/contents/{path}", params)
