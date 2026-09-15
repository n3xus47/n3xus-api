from typing import Literal, List

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebsiteScrapeRequest(StrictModel):
    urls: str | list[str]
    max_items: int | None = Field(default=None, ge=1, alias="maxItems")
    max_pages: int | None = Field(default=None, ge=1, alias="maxPages")
    max_depth: int | None = Field(default=None, ge=0, alias="maxDepth")
    include_urls: str | list[str] | None = Field(default=None, alias="includeUrls")
    exclude_urls: str | list[str] | None = Field(default=None, alias="excludeUrls")
    content_format: Literal["markdown", "text"] | None = Field(default=None, alias="contentFormat")
    max_chars: int = Field(default=250_000, ge=1_000, le=1_000_000, alias="maxChars")
    dry_run: bool = Field(default=False, alias="dryRun")

    @field_validator("urls")
    @classmethod
    def public_http_urls(cls, value: str | list[str]) -> str | list[str]:
        urls = [value] if isinstance(value, str) else value
        if not urls:
            raise ValueError("at least one URL is required")
        for url in urls:
            if not url.startswith(("http://", "https://")):
                raise ValueError("URLs must use http or https")
        return value

    def url_list(self) -> list[str]:
        return [self.urls] if isinstance(self.urls, str) else self.urls


class WebSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=10, ge=1, le=100, alias="maxResults")
    dry_run: bool = Field(default=False, alias="dryRun")


class Page(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    markdown: str | None = None
    text: str | None = None
    title: str | None = None
    description: str | None = None
    language: str | None = None
    truncated: bool | None = None
    total_chars: int | None = Field(default=None, alias="totalChars")
    structured_data: list[dict] | None = Field(default=None, alias="structuredData")
    recipe: dict | None = None


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    date_text: str | None = Field(default=None, alias="dateText")


class Envelope(BaseModel):
    request_id: str | None = Field(default=None, alias="requestId")
    route: str | None = None
    capability: str | None = None
    status: Literal["succeeded", "failed", "dry_run"]
    replayed: bool = False
    cost_final: bool = Field(default=True, alias="costFinal")
    debit_microusd: int | None = Field(default=0, alias="debitMicrousd")
    output: object | None = None
    balance: None = None
    next: None = None
    error: object | None = None
    skill_version: str = Field(default="local-0.1", alias="skillVersion")
    list: dict | None = None
    url_outcomes: List[dict[str, str]] | None = Field(default=None, alias="urlOutcomes")
    estimate: dict | None = None
    source: dict | None = None
