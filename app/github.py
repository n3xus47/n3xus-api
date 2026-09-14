import base64
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import settings


class GitHubError(Exception):
    pass


class GitHubRateLimitError(GitHubError):
    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__("GitHub public API rate limit exceeded")


@dataclass(frozen=True)
class GitHubPage:
    data: object
    next_page_token: str | None


def page_number(payload: dict) -> int:
    token = payload.get("pageToken")
    if token is None:
        return 1
    if isinstance(token, int) and token >= 1:
        return token
    if isinstance(token, str) and token.isdigit() and int(token) >= 1:
        return int(token)
    raise GitHubError("pageToken must be a positive integer")


def next_page_token(link_header: str | None, page: int, item_count: int, per_page: int) -> str | None:
    if item_count < per_page:
        return None
    if link_header:
        for part in link_header.split(","):
            section = part.strip()
            if 'rel="next"' not in section:
                continue
            match = re.search(r"<([^>]+)>", section)
            if not match:
                continue
            query = parse_qs(urlparse(match.group(1)).query)
            next_page = query.get("page", [None])[0]
            if next_page and next_page.isdigit():
                return next_page
    return str(page + 1)


async def github_get_page(path: str, params: dict | None = None) -> GitHubPage:
    page = int((params or {}).get("page", 1))
    per_page = int((params or {}).get("per_page", 30))
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_secs,
            headers={"Accept": "application/vnd.github+json", "User-Agent": settings.user_agent},
        ) as client:
            response = await client.get(f"https://api.github.com{path}", params=params)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                parsed = int(retry_after) if retry_after and retry_after.isdigit() else None
                raise GitHubRateLimitError(parsed)
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else payload.get("items", [])
            count = len(rows) if isinstance(rows, list) else 0
            token = next_page_token(response.headers.get("Link"), page, count, per_page)
            return GitHubPage(data=payload, next_page_token=token)
    except GitHubRateLimitError:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise GitHubError("GitHub public API request failed") from error


async def github_get(path: str, params: dict | None = None) -> object:
    return (await github_get_page(path, params)).data


def compact_user(user: dict) -> dict:
    return {
        key: user.get(key)
        for key in (
            "login",
            "id",
            "type",
            "name",
            "company",
            "blog",
            "location",
            "email",
            "bio",
            "followers",
            "following",
            "public_repos",
            "html_url",
            "created_at",
            "updated_at",
        )
    }


def compact_issue(item: dict) -> dict:
    return {
        "resourceType": "pull_request" if item.get("pull_request") else "issue",
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "html_url": item.get("html_url"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "author": (item.get("user") or {}).get("login"),
    }


def compact_pull(item: dict) -> dict:
    return {
        "resourceType": "pull_request",
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "html_url": item.get("html_url"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "author": (item.get("user") or {}).get("login"),
        "merged_at": item.get("merged_at"),
    }


def compact_commit(item: dict) -> dict:
    commit = item.get("commit") or {}
    author = commit.get("author") or {}
    return {
        "resourceType": "commit",
        "sha": item.get("sha"),
        "html_url": item.get("html_url"),
        "message": commit.get("message"),
        "authorName": author.get("name"),
        "authorDate": author.get("date"),
    }


def compact_repo(item: dict) -> dict:
    return {
        "resourceType": "repository",
        "full_name": item.get("full_name"),
        "html_url": item.get("html_url"),
        "description": item.get("description"),
        "stargazers_count": item.get("stargazers_count"),
        "language": item.get("language"),
    }


def compact_code(item: dict) -> dict:
    repo = item.get("repository") or {}
    return {
        "resourceType": "code",
        "name": item.get("name"),
        "path": item.get("path"),
        "html_url": item.get("html_url"),
        "repository": repo.get("full_name"),
        "sha": item.get("sha"),
    }


def compact_content_entry(entry: dict) -> dict:
    return {
        "name": entry.get("name"),
        "path": entry.get("path"),
        "sha": entry.get("sha"),
        "size": entry.get("size"),
        "html_url": entry.get("html_url"),
        "entryType": entry.get("type"),
    }


def normalize_contents(data: object) -> dict:
    if isinstance(data, list):
        return {"resourceType": "directory", "items": [compact_content_entry(entry) for entry in data]}
    if isinstance(data, dict):
        return {"resourceType": data.get("type", "file"), "item": compact_content_entry(data)}
    raise GitHubError("Unexpected GitHub contents response")


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


async def list_resource(repository: str, resource: str, payload: dict) -> dict:
    page = page_number(payload)
    per_page = min(int(payload.get("maxItems", 30)), 100)
    params: dict[str, object] = {"per_page": per_page, "page": page}
    if resource == "issues":
        params["state"] = payload.get("state", "open")
    page_result = await github_get_page(f"/repos/{repository}/{resource}", params)
    rows = page_result.data
    if not isinstance(rows, list):
        raise GitHubError("Unexpected GitHub list response")
    if resource == "issues":
        items = [compact_issue(row) for row in rows if "pull_request" not in row]
        resource_type = "issue"
    elif resource == "pulls":
        items = [compact_pull(row) for row in rows]
        resource_type = "pull_request"
    else:
        items = [compact_commit(row) for row in rows]
        resource_type = "commit"
    return {"resourceType": resource_type, "items": items, "nextPageToken": page_result.next_page_token}


def search_query(payload: dict, kind: str) -> str:
    query = payload["query"]
    if language := payload.get("language"):
        query += f" language:{language}"
    if kind == "issues" and "is:issue" not in query and "is:pr" not in query:
        query += " is:issue"
    if kind == "pull_requests" and "is:pr" not in query:
        query += " is:pr"
    return query


async def search(payload: dict) -> dict:
    kind = payload.get("type", "repositories")
    query = search_query(payload, kind)
    endpoint = {"repositories": "repositories", "issues": "issues", "pull_requests": "issues", "code": "code"}.get(kind)
    if not endpoint:
        raise GitHubError("Unsupported GitHub search type")
    page = page_number(payload)
    per_page = min(int(payload.get("maxItems", 30)), 100)
    page_result = await github_get_page(
        f"/search/{endpoint}",
        {"q": query, "per_page": per_page, "page": page},
    )
    raw = page_result.data
    if not isinstance(raw, dict):
        raise GitHubError("Unexpected GitHub search response")
    items_raw = raw.get("items") or []
    normalizers = {
        "repositories": compact_repo,
        "issues": compact_issue,
        "pull_requests": compact_issue,
        "code": compact_code,
    }
    return {
        "resourceType": kind,
        "totalCount": raw.get("total_count"),
        "incompleteResults": raw.get("incomplete_results"),
        "items": [normalizers[kind](item) for item in items_raw],
        "nextPageToken": page_result.next_page_token,
    }


async def contents(payload: dict) -> dict:
    path = payload.get("path", "")
    params = {"ref": payload["ref"]} if payload.get("ref") else None
    data = await github_get(f"/repos/{payload['repository']}/contents/{path}", params)
    return normalize_contents(data)
