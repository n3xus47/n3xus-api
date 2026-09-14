"""Policy-governed SEO adapters: approved sources only, no guessed commercial metrics."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from app.search import search_web

Approval = Literal["approved", "candidate"]
Configuration = Literal["built_in", "operator_supplied"]

COMMERCIAL_KEYWORD_FIELDS = frozenset({"monthlySearches", "cpc", "difficulty", "trend", "intent"})
COMMERCIAL_COMPETITOR_FIELDS = frozenset({"sharedKeywords", "gapKeywords"})

METRICS_UNAVAILABLE_REASON = "no_approved_commercial_source"
STRATEGY_DOC = "docs/seo-provider-strategy.md"

DEFAULT_SERP_ADAPTER_ID = "searxng-local-serp"


@dataclass(frozen=True)
class SeoAdapterDefinition:
    id: str
    approval: Approval
    configuration: Configuration
    license_summary: str
    rate_limits: str
    privacy_summary: str
    fields: frozenset[str]
    env_vars: tuple[str, ...] = ()


ADAPTERS: tuple[SeoAdapterDefinition, ...] = (
    SeoAdapterDefinition(
        id=DEFAULT_SERP_ADAPTER_ID,
        approval="approved",
        configuration="built_in",
        license_summary="AGPL-3.0 SearxNG instance; upstream engine ToS apply.",
        rate_limits="Depends on configured SearxNG engines; keep instance local.",
        privacy_summary="Search queries leave the host to configured engines; no SaaS API key.",
        fields=frozenset({"position", "results", "competitors", "domain", "keyword"}),
        env_vars=("N3XUS_API_SEARXNG_URL",),
    ),
    SeoAdapterDefinition(
        id="google-ads-keyword-planner",
        approval="candidate",
        configuration="operator_supplied",
        license_summary="Google Ads API Terms of Service.",
        rate_limits="Google developer token quotas.",
        privacy_summary="Keywords and Ads account metadata processed by Google.",
        fields=frozenset({"monthlySearches", "cpc", "difficulty", "competition"}),
        env_vars=(),
    ),
    SeoAdapterDefinition(
        id="dataforseo-keywords",
        approval="candidate",
        configuration="operator_supplied",
        license_summary="DataForSEO commercial API agreement.",
        rate_limits="Per-task billing; vendor concurrency caps.",
        privacy_summary="Keywords/domains sent to DataForSEO.",
        fields=frozenset({"monthlySearches", "cpc", "difficulty", "serp_features"}),
        env_vars=(),
    ),
    SeoAdapterDefinition(
        id="serpapi-organic",
        approval="candidate",
        configuration="operator_supplied",
        license_summary="SerpApi Terms of Service.",
        rate_limits="Monthly search allowance per subscription tier.",
        privacy_summary="Full queries processed by SerpApi.",
        fields=frozenset({"results", "featured_snippet", "people_also_ask"}),
        env_vars=(),
    ),
)

_ADAPTER_BY_ID = {item.id: item for item in ADAPTERS}
APPROVED_ADAPTER_IDS = frozenset(item.id for item in ADAPTERS if item.approval == "approved")


def adapter_definition(adapter_id: str) -> SeoAdapterDefinition | None:
    return _ADAPTER_BY_ID.get(adapter_id)


def list_adapters() -> list[dict]:
    return [
        {
            "id": item.id,
            "approval": item.approval,
            "configuration": item.configuration,
            "fields": sorted(item.fields),
            "envVars": list(item.env_vars),
            "licenseSummary": item.license_summary,
            "rateLimits": item.rate_limits,
            "privacySummary": item.privacy_summary,
        }
        for item in ADAPTERS
    ]


def provenance_name(adapter_id: str) -> str:
    return adapter_id if adapter_id in _ADAPTER_BY_ID else DEFAULT_SERP_ADAPTER_ID


def keyword_metrics(keywords: list[str]) -> dict:
    if not any(item.approval == "approved" and COMMERCIAL_KEYWORD_FIELDS <= item.fields for item in ADAPTERS):
        rows = [
            {
                "keyword": keyword,
                "monthlySearches": None,
                "cpc": None,
                "difficulty": None,
                "intent": None,
                "trend": None,
                "metricsSource": None,
                "metricsUnavailableReason": METRICS_UNAVAILABLE_REASON,
            }
            for keyword in keywords
        ]
        return {
            "keywords": rows,
            "adapterId": None,
            "policy": {"commercialMetricsApproved": False, "documentation": STRATEGY_DOC},
        }
    raise RuntimeError("Commercial keyword adapter misconfigured: approved adapter missing from registry.")


def hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


async def rank(keyword: str, domain: str, depth: int, adapter_id: str = DEFAULT_SERP_ADAPTER_ID) -> dict:
    if adapter_id not in APPROVED_ADAPTER_IDS:
        raise ValueError(f"SEO adapter {adapter_id!r} is not approved.")
    if adapter_id != DEFAULT_SERP_ADAPTER_ID:
        raise ValueError(f"SEO adapter {adapter_id!r} is not implemented.")
    results, _ = await search_web(keyword, min(depth, 100))
    rows = [item.model_dump(by_alias=True, exclude_none=True) for item in results]
    normalized_domain = domain.lower().removeprefix("www.")
    position = next(
        (index + 1 for index, item in enumerate(rows) if hostname(item["url"]).endswith(normalized_domain)),
        None,
    )
    return {
        "keyword": keyword,
        "domain": domain,
        "position": position,
        "results": rows,
        "adapterId": adapter_id,
    }


async def competitors(domain: str, limit: int, adapter_id: str = DEFAULT_SERP_ADAPTER_ID) -> dict:
    if adapter_id not in APPROVED_ADAPTER_IDS:
        raise ValueError(f"SEO adapter {adapter_id!r} is not approved.")
    if adapter_id != DEFAULT_SERP_ADAPTER_ID:
        raise ValueError(f"SEO adapter {adapter_id!r} is not implemented.")
    results, _ = await search_web(f"site:{domain}", max(limit * 3, 10))
    domains: list[str] = []
    for item in results:
        host = hostname(item.url)
        if host and host != domain and host not in domains:
            domains.append(host)
    return {
        "domain": domain,
        "competitors": [
            {
                "domain": item,
                "sharedKeywords": None,
                "gapKeywords": None,
                "overlapUnavailableReason": METRICS_UNAVAILABLE_REASON,
            }
            for item in domains[:limit]
        ],
        "adapterId": adapter_id,
    }
