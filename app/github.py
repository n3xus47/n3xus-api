import base64
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import settings

_GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": settings.user_agent}
_SEARCH_ENDPOINT = {
    "repositories": "repositories",
    "issues": "issues",
    "pull_requests": "issues",
    "code": "code",
}


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


def max_per_page(payload: dict) -> int:
    return min(int(payload.get("maxItems", 30)), 100)


def parse_retry_after(header: str | None) -> int | None:
    if header and header.isdigit():
        return int(header)
    return None


def paginated_item_count(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        items = payload.get("items", [])
        return len(items) if isinstance(items, list) else 0
    return 0


def collection_state(result: object) -> str:
    if not result:
        return "empty"
    if isinstance(result, list):
        return "complete"
    if isinstance(result, dict):
        items = result.get("items")
        if isinstance(items, list):
            return "complete" if items else "empty"
        if result.get("item") or result.get("repository"):
            return "complete"
    return "complete"


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
        async with httpx.AsyncClient(timeout=settings.request_timeout_secs, headers=_GITHUB_HEADERS) as client:
            response = await client.get(f"https://api.github.com{path}", params=params)
            if response.status_code == 429:
                raise GitHubRateLimitError(parse_retry_after(response.headers.get("Retry-After")))
            response.raise_for_status()
            payload = response.json()
            token = next_page_token(
                response.headers.get("Link"), page, paginated_item_count(payload), per_page
            )
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


def _issue_like_fields(item: dict, resource_type: str, **extra: object) -> dict:
    fields = {
        "resourceType": resource_type,
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "html_url": item.get("html_url"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "author": (item.get("user") or {}).get("login"),
    }
    fields.update(extra)
    return fields


def compact_issue(item: dict) -> dict:
    resource_type = "pull_request" if item.get("pull_request") else "issue"
    return _issue_like_fields(item, resource_type)


def compact_pull(item: dict) -> dict:
    return _issue_like_fields(item, "pull_request", merged_at=item.get("merged_at"))


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


_LIST_RESOURCE: dict[str, tuple[str, Callable[[dict], dict], Callable[[dict], bool]]] = {
    "issues": ("issue", compact_issue, lambda row: "pull_request" not in row),
    "pulls": ("pull_request", compact_pull, lambda _row: True),
    "commits": ("commit", compact_commit, lambda _row: True),
}


async def list_resource(repository: str, resource: str, payload: dict) -> dict:
    resource_type, compact, include_row = _LIST_RESOURCE[resource]
    page = page_number(payload)
    per_page = max_per_page(payload)
    params: dict[str, object] = {"per_page": per_page, "page": page}
    if resource == "issues":
        params["state"] = payload.get("state", "open")
    page_result = await github_get_page(f"/repos/{repository}/{resource}", params)
    rows = page_result.data
    if not isinstance(rows, list):
        raise GitHubError("Unexpected GitHub list response")
    items = [compact(row) for row in rows if include_row(row)]
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


_SEARCH_COMPACT: dict[str, Callable[[dict], dict]] = {
    "repositories": compact_repo,
    "issues": compact_issue,
    "pull_requests": compact_issue,
    "code": compact_code,
}


async def search(payload: dict) -> dict:
    kind = payload.get("type", "repositories")
    endpoint = _SEARCH_ENDPOINT.get(kind)
    if not endpoint:
        raise GitHubError("Unsupported GitHub search type")
    query = search_query(payload, kind)
    page = page_number(payload)
    per_page = max_per_page(payload)
    page_result = await github_get_page(
        f"/search/{endpoint}",
        {"q": query, "per_page": per_page, "page": page},
    )
    raw = page_result.data
    if not isinstance(raw, dict):
        raise GitHubError("Unexpected GitHub search response")
    items_raw = raw.get("items") or []
    compact = _SEARCH_COMPACT[kind]
    return {
        "resourceType": kind,
        "totalCount": raw.get("total_count"),
        "incompleteResults": raw.get("incomplete_results"),
        "items": [compact(item) for item in items_raw],
        "nextPageToken": page_result.next_page_token,
    }


async def contents(payload: dict) -> dict:
    path = payload.get("path", "")
    params = {"ref": payload["ref"]} if payload.get("ref") else None
    data = await github_get(f"/repos/{payload['repository']}/contents/{path}", params)
    return normalize_contents(data)
