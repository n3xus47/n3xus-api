"""Truthful local capability metadata exposed by ``GET /v1/capabilities``."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Capability:
    slug: str
    support_level: str
    adapter: str
    limitations: tuple[str, ...]
    evaluation_suite: str | None = None

    def output(self) -> dict:
        value = asdict(self)
        value["supportLevel"] = value.pop("support_level")
        value["evaluationSuite"] = value.pop("evaluation_suite")
        value["limitations"] = list(value["limitations"])
        return {key: item for key, item in value.items() if item is not None}


REGISTRY = (
    Capability("scrape.website", "structured", "readability-playwright", ("JavaScript fallback is best-effort.",), "website"),
    Capability("search.web", "best_effort", "searxng", ("Results depend on configured SearxNG engines.",), "search"),
    Capability(
        "research.deep",
        "experimental",
        "searxng-ollama",
        (
            "Runs a multi-query search plan, dedupes diverse public sources, and returns numbered evidence with provenance.",
            "Completeness is empty, partial, or complete based on collected evidence—not model confidence.",
        ),
        "research",
    ),
    Capability("scrape.github", "structured", "github-public-rest", ("Unauthenticated GitHub rate limits apply.",), "github"),
    Capability("scrape.youtube", "structured", "yt-dlp-youtube-transcript", ("Availability depends on public video metadata and captions.",), "youtube"),
    Capability("scrape.pdf", "structured", "pypdf-public-url", ("Scanned PDFs without a text layer are unsupported.",), "pdf"),
    Capability("scrape.twitter", "best_effort", "public-page-fetch", ("This is not a structured X data collector.",), "social"),
    Capability("scrape.instagram", "best_effort", "public-page-fetch", ("This is not a structured Instagram data collector.",), "social"),
    Capability("scrape.facebook", "best_effort", "public-page-fetch-search", ("This is not a structured Meta Ads or group-post collector.",), "social"),
    Capability("scrape.tiktok", "best_effort", "public-page-fetch", ("This is not a structured TikTok data collector.",), "social"),
    Capability("scrape.amazon", "best_effort", "public-page-fetch-search", ("This is not a structured Amazon product or review collector.",), "amazon"),
    Capability("scrape.google", "best_effort", "openstreetmap-nominatim", ("Returns OpenStreetMap geocoding data, not Google Places data.",), "places"),
    Capability("scrape.threads", "best_effort", "public-page-fetch", ("This is not a structured Threads post collector.",), "social"),
    Capability("scrape.extract", "experimental", "readability-ollama", ("Extraction quality depends on the local model.",), "extract"),
    Capability("scrape.deep", "experimental", "searxng-ollama", ("This is a local research dossier, not a dedicated entity-data source.",), "research"),
    Capability(
        "email.send",
        "structured",
        "local-smtp",
        (
            "Sending requires user-configured SMTP; draft-first when SMTP is absent.",
            "Successful sends record relay handoff metadata, not inbox lifecycle events.",
        ),
        "email",
    ),
    Capability("email.read", "structured", "local-sqlite", ("Only messages sent or drafted through n3xusAPI are stored.",), "email"),
    Capability("email.find", "best_effort", "public-company-pages", ("Only explicitly published addresses are returned; addresses are never guessed.",), "contact"),
    Capability("email.verify", "unavailable", "syntax-check", ("Mailbox deliverability verification is not implemented.",), "contact"),
    Capability("email.enrich", "unavailable", "none", ("Person-data enrichment is not implemented.",), "contact"),
    Capability(
        "company.enrich",
        "best_effort",
        "public-company-pages",
        (
            "Collects homepage, about, and contact pages on the same domain only.",
            "Each populated field includes provenance; absent fields stay omitted rather than inferred.",
        ),
        "company-enrich",
    ),
    Capability("seo.read", "best_effort", "searxng-ollama", ("Keyword volume, CPC, difficulty and trend data are unavailable.",), "seo"),
    Capability(
        "browser.act",
        "experimental",
        "playwright-ollama",
        (
            "Public pages only; bounded to eight safe browser steps.",
            "Returns a plan/execute safe-action trace for audit; unsafe actions are blocked before execution.",
        ),
        "browser-act",
    ),
    Capability("audio.transcribe", "structured", "faster-whisper", ("CPU inference is the default and can be slow.",), "transcribe"),
    Capability("vm.run", "structured", "local-docker", ("Requires Docker socket access; localhost only.",), "vm"),
    Capability("generate.image", "experimental", "automatic1111", ("Requires a user-configured local Stable Diffusion server.",), "image"),
    Capability("memory.read", "structured", "local-sqlite", (), "memory"),
    Capability("memory.write", "structured", "local-sqlite", (), "memory"),
    Capability("request.list", "structured", "local-sqlite", (), None),
    Capability("request.status", "structured", "local-sqlite", (), None),
    Capability("account.balance", "structured", "local", ("Local execution has no credit balance.",), None),
    Capability("account.info", "structured", "local", ("Local execution has no hosted workspace or scopes.",), None),
)

_BY_SLUG = {capability.slug: capability for capability in REGISTRY}


def get_capability(slug: str) -> Capability | None:
    return _BY_SLUG.get(slug)


def list_capabilities() -> list[dict]:
    return [capability.output() for capability in REGISTRY]
