import json
from pathlib import Path

import httpx
import pytest

from app.evaluate import validate_cases
from app.github import (
    GitHubPage,
    GitHubRateLimitError,
    compact_issue,
    list_resource,
    next_page_token,
    normalize_contents,
    page_number,
    search,
    search_query,
)


def test_github_smoke_fixtures_validate():
    cases = json.loads(Path("evals/github-smoke.json").read_text())
    assert len(validate_cases(cases)) == 4


def test_page_number_accepts_string_and_int():
    assert page_number({}) == 1
    assert page_number({"pageToken": "2"}) == 2
    assert page_number({"pageToken": 3}) == 3


def test_page_number_rejects_invalid_token():
    with pytest.raises(Exception, match="pageToken"):
        page_number({"pageToken": "abc"})


def test_next_page_token_uses_link_header():
    link = '<https://api.github.com/repos/o/r/issues?page=2>; rel="next"'
    assert next_page_token(link, 1, 30, 30) == "2"


def test_next_page_token_absent_when_short_page():
    assert next_page_token(None, 1, 2, 30) is None


def test_issue_and_pr_resource_types():
    issue = compact_issue({"number": 1, "title": "Bug", "pull_request": {"url": "x"}})
    plain = compact_issue({"number": 2, "title": "Task"})
    assert issue["resourceType"] == "pull_request"
    assert plain["resourceType"] == "issue"


def test_search_query_adds_issue_and_pr_filters():
    assert "is:issue" in search_query({"query": "repo:o/r"}, "issues")
    assert "is:pr" in search_query({"query": "repo:o/r"}, "pull_requests")
    assert search_query({"query": "repo:o/r is:pr"}, "pull_requests") == "repo:o/r is:pr"


def test_normalize_contents_file_and_directory():
    file_payload = normalize_contents({"name": "README", "path": "README", "type": "file", "sha": "abc"})
    dir_payload = normalize_contents([{"name": "src", "path": "src", "type": "dir", "sha": "def"}])
    assert file_payload["resourceType"] == "file"
    assert file_payload["item"]["name"] == "README"
    assert dir_payload["resourceType"] == "directory"
    assert dir_payload["items"][0]["entryType"] == "dir"


async def test_list_resource_filters_pull_requests_from_issues(monkeypatch):
    async def fake_page(path, params):
        assert path.endswith("/issues")
        return GitHubPage(
            data=[
                {"number": 1, "title": "Issue", "state": "open"},
                {"number": 2, "title": "PR", "state": "open", "pull_request": {"url": "x"}},
            ],
            next_page_token=None,
        )

    monkeypatch.setattr("app.github.github_get_page", fake_page)
    result = await list_resource("octocat/Hello-World", "issues", {"maxItems": 10})
    assert result["resourceType"] == "issue"
    assert len(result["items"]) == 1
    assert result["items"][0]["resourceType"] == "issue"


async def test_search_returns_normalized_items_and_token(monkeypatch):
    async def fake_page(path, params):
        assert path == "/search/repositories"
        assert params["page"] == 2
        return GitHubPage(
            data={
                "total_count": 100,
                "incomplete_results": False,
                "items": [{"full_name": "octocat/Hello-World", "html_url": "https://github.com/octocat/Hello-World"}],
            },
            next_page_token="3",
        )

    monkeypatch.setattr("app.github.github_get_page", fake_page)
    result = await search({"query": "hello", "type": "repositories", "pageToken": "2", "maxItems": 1})
    assert result["resourceType"] == "repositories"
    assert result["items"][0]["full_name"] == "octocat/Hello-World"
    assert result["nextPageToken"] == "3"


async def test_github_rate_limit_maps_to_dedicated_error(monkeypatch):
    async def fake_get(*_args, **_kwargs):
        request = httpx.Request("GET", "https://api.github.com/rate_limit")
        return httpx.Response(429, request=request, headers={"Retry-After": "12"})

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return await fake_get()

    monkeypatch.setattr("app.github.httpx.AsyncClient", lambda **_kwargs: FakeClient())
    with pytest.raises(GitHubRateLimitError) as error:
        await list_resource("octocat/Hello-World", "commits", {"maxItems": 1})
    assert error.value.retry_after == 12
