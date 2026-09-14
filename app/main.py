from hashlib import sha256
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from app.capabilities import get_capability, list_capabilities
from app.config import settings
from app.image import ImageError, generate_image
from app.contact import company as enrich_company, find_email, verify_email
from app.browser_act import BrowserTaskError, act as browser_act
from app.email import EmailError, dns_has_token, domain_token, send_email
from app.github import (
    GitHubError,
    GitHubRateLimitError,
    collection_state as github_collection_state,
    contents as github_contents,
    list_resource as github_list_resource,
    profile as github_profile,
    repository as github_repository,
    search as github_search,
)
from app.models import Envelope, WebSearchRequest, WebsiteScrapeRequest
from app.provenance import provenance, strip_collection_state
from app.pdf import PdfError, extract_pdf
from app.instagram_public import instagram_collect
from app.meta_ads import MetaAdsError, provenance_library_urls
from app.open_business import search_open_business
from app.public_sources import amazon, facebook, google_places, instagram_hashtag, public_pages, social
from app.llm import LlmError, extract_json
from app.research import research as deep_research
from app.scraper import scrape_website, website_collection_state
from app.search import SearchError, search_web
from app.seo import competitors as seo_competitors, rank as seo_rank
from app.seo_adapters import keyword_metrics as seo_keyword_metrics, provenance_name as seo_provenance_name
from app.store import (create_email_domain, create_email_identity, delete_email_domain, delete_memory,
                       find_idempotent, get_email_domain, get_email_draft, get_memory, list_email_domains,
                       list_email_drafts, list_email_identities, list_email_messages, list_memory, list_requests,
                       remove_email_draft, save_email_draft, save_request, set_email_domain_verified,
                       update_email_identity, write_memory)
from app.youtube import (
    PROVENANCE_NAME as YOUTUBE_PROVENANCE,
    YouTubeError,
    channel_videos as youtube_channel_videos,
    envelope_parts_from_action as youtube_envelope_parts,
    search_videos as youtube_search_videos,
    thumbnail as youtube_thumbnail,
    transcript as youtube_transcript,
)
from app.transcribe import AudioError, create_upload, transcribe, write_upload
from app.vm import VmError, is_localhost_client, output_file as vm_output_file, run as vm_run

app = FastAPI(title="n3xusAPI", version="0.2.0", description="Local real-world tools API")

def envelope(*, route: str, capability: str, output: object = None, status: str = "succeeded", **kwargs: object) -> dict:
    return Envelope(
        requestId=f"local_{uuid4().hex}", route=route, capability=capability, status=status, output=output, **kwargs
    ).model_dump(by_alias=True, exclude_none=True)


def failure(
    route: str,
    capability: str,
    code: str,
    hint: str,
    status_code: int,
    *,
    output: object = None,
) -> JSONResponse:
    body = Envelope(
        route=route,
        capability=capability,
        status="failed",
        debitMicrousd=None,
        output=output,
        error={"code": code, "retryable": False, "retryAfterSecs": None, "hint": hint},
    ).model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(status_code=status_code, content=body)


@app.middleware("http")
async def local_api_key(request: Request, call_next):
    if settings.api_key and request.url.path != "/v1/health":
        expected = f"Bearer {settings.api_key}"
        if request.headers.get("authorization") != expected:
            return failure(request.url.path, None, "invalid_api_key", "Set the local API key.", 401)
    return await call_next(request)


async def replay_or_require_key(request: Request, route: str, capability: str, dry_run: bool) -> JSONResponse | None:
    if dry_run:
        return None
    key = request.headers.get("idempotency-key")
    if not key:
        return failure(route, capability, "missing_idempotency_key", "Send a unique Idempotency-Key.", 400)
    replay = find_idempotent(key)
    if replay:
        replay["replayed"] = True
        return JSONResponse(status_code=200, content=replay)
    return None


def persist(route: str, request: Request, body: dict, dry_run: bool) -> dict:
    if not dry_run:
        save_request(body["requestId"], route, request.headers.get("idempotency-key"), body)
    return body


@app.exception_handler(LlmError)
async def llm_error_handler(_: Request, error: LlmError) -> JSONResponse:
    return failure("/v1/research/deep", "research.deep", "capability_not_configured", str(error), 501)


@app.exception_handler(PdfError)
async def pdf_error_handler(_: Request, error: PdfError) -> JSONResponse:
    code = "pdf_too_large" if "50 MB" in str(error) else "pdf_not_readable"
    return failure("/v1/scrape/pdf", "scrape.website", code, str(error), 422)


@app.exception_handler(YouTubeError)
async def youtube_error_handler(_: Request, error: YouTubeError) -> JSONResponse:
    return failure("/v1/scrape/youtube", "scrape.youtube", "scrape_request_failed", str(error), 502)


@app.exception_handler(GitHubRateLimitError)
async def github_rate_limit_handler(_: Request, error: GitHubRateLimitError) -> JSONResponse:
    body = Envelope(
        route="/v1/scrape/github",
        capability="scrape.github",
        status="failed",
        debitMicrousd=None,
        output=None,
        error={
            "code": "github_rate_limited",
            "retryable": True,
            "retryAfterSecs": error.retry_after,
            "hint": str(error),
        },
    ).model_dump(by_alias=True, exclude_none=True)
    return JSONResponse(status_code=429, content=body)


@app.exception_handler(GitHubError)
async def github_error_handler(_: Request, error: GitHubError) -> JSONResponse:
    return failure("/v1/scrape/github", "scrape.github", "scrape_request_failed", str(error), 502)


@app.exception_handler(SearchError)
async def search_error_handler(_: Request, error: SearchError) -> JSONResponse:
    return failure("/v1/search/web", "search.web", "search_request_failed", str(error), 502)


@app.exception_handler(AudioError)
async def audio_error_handler(_: Request, error: AudioError) -> JSONResponse:
    return failure("/v1/transcribe", "audio.transcribe", "audio_not_readable", str(error), 422)


@app.exception_handler(BrowserTaskError)
async def browser_error_handler(_: Request, error: BrowserTaskError) -> JSONResponse:
    output = {"trace": error.trace} if error.trace else None
    return failure(
        "/v1/browser/act",
        "browser.act",
        "browser_task_failed",
        str(error),
        502,
        output=output,
    )


@app.exception_handler(ImageError)
async def image_error_handler(_: Request, error: ImageError) -> JSONResponse:
    return failure("/v1/generate/image", "generate.image", "capability_not_configured", str(error), 501)


@app.exception_handler(VmError)
async def vm_error_handler(_: Request, error: VmError) -> JSONResponse:
    return failure("/v1/vm/run", "vm.run", "vm_run_request_failed", str(error), 502)


@app.get("/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/scrape/website", status_code=201)
async def website(request: WebsiteScrapeRequest, raw: Request):
    replay = await replay_or_require_key(raw, "/v1/scrape/website", "scrape.website", request.dry_run)
    if replay:
        return replay
    if request.dry_run:
        return envelope(route="/v1/scrape/website", capability="scrape.website", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    pages, outcomes, crawl_meta = await scrape_website(request)
    list_meta: dict[str, object] = {"listState": "has_results" if pages else "no_results"}
    if crawl_meta is not None:
        list_meta["crawl"] = crawl_meta
    return persist("/v1/scrape/website", raw, envelope(
        route="/v1/scrape/website", capability="scrape.website",
        output=[page.model_dump(by_alias=True, exclude_none=True) for page in pages],
        list=list_meta, urlOutcomes=outcomes,
        source=provenance(
            "public-website",
            [page.url for page in pages] or request.url_list(),
            website_collection_state(pages, outcomes or []),
        ),
    ), False)


@app.post("/v1/search/web")
async def search(request: WebSearchRequest, raw: Request):
    replay = await replay_or_require_key(raw, "/v1/search/web", "search.web", request.dry_run)
    if replay:
        return replay
    if request.dry_run:
        return envelope(route="/v1/search/web", capability="search.web", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    results, answer = await search_web(request.query, request.max_results)
    output = {"results": [result.model_dump(by_alias=True, exclude_none=True) for result in results]}
    if answer:
        output["answer"] = answer
    return persist("/v1/search/web", raw, envelope(
        route="/v1/search/web", capability="search.web", output=output,
        source=provenance("searxng", [result.url for result in results], "complete" if results else "empty"),
    ), False)


async def github_response(route: str, payload: dict, raw: Request, action):
    replay = await replay_or_require_key(raw, route, "scrape.github", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=route, capability="scrape.github", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    result = await action()
    return persist(route, raw, envelope(
        route=route, capability="scrape.github", output=result,
        source=provenance("github-public-rest", state=github_collection_state(result)),
    ), False)


@app.post("/v1/scrape/github/profile")
@app.post("/v1/scrape/github")
async def github_profiles(payload: dict, raw: Request):
    usernames = payload.get("usernames")
    if not isinstance(usernames, list) or not usernames:
        return failure(raw.url.path, "scrape.github", "invalid_request", "usernames must be a non-empty list.", 400)
    return await github_response(raw.url.path, payload, raw, lambda: github_profile(usernames))


@app.post("/v1/scrape/github/repo")
async def github_repo(payload: dict, raw: Request):
    repository = payload.get("repository")
    if not isinstance(repository, str):
        return failure(raw.url.path, "scrape.github", "invalid_request", "repository is required.", 400)
    return await github_response(raw.url.path, payload, raw, lambda: github_repository(repository))


@app.post("/v1/scrape/github/{resource}")
async def github_resources(resource: str, payload: dict, raw: Request):
    if resource == "search":
        if not isinstance(payload.get("query"), str):
            return failure(raw.url.path, "scrape.github", "invalid_request", "query is required.", 400)
        return await github_response(raw.url.path, payload, raw, lambda: github_search(payload))
    if resource == "contents":
        if not isinstance(payload.get("repository"), str):
            return failure(raw.url.path, "scrape.github", "invalid_request", "repository is required.", 400)
        return await github_response(raw.url.path, payload, raw, lambda: github_contents(payload))
    if resource not in {"issues", "pulls", "commits"} or not isinstance(payload.get("repository"), str):
        return failure(raw.url.path, "scrape.github", "unknown_capability", "Unsupported GitHub resource.", 404)
    return await github_response(raw.url.path, payload, raw, lambda: github_list_resource(payload["repository"], resource, payload))


async def youtube_response(route: str, payload: dict, raw: Request, action):
    replay = await replay_or_require_key(raw, route, "scrape.youtube", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=route, capability="scrape.youtube", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    result = await action()
    output, source_urls, state = youtube_envelope_parts(result)
    source = provenance(YOUTUBE_PROVENANCE, source_urls, state)
    return persist(route, raw, envelope(route=route, capability="scrape.youtube", output=output, source=source), False)


@app.post("/v1/research/deep")
async def research_endpoint(payload: dict, raw: Request):
    if not isinstance(payload.get("query"), str):
        return failure(raw.url.path, "research.deep", "invalid_request", "query is required.", 400)
    replay = await replay_or_require_key(raw, raw.url.path, "research.deep", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=raw.url.path, capability="research.deep", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    output = await deep_research(payload["query"], payload.get("context"))
    return persist(raw.url.path, raw, envelope(route=raw.url.path, capability="research.deep", output=output), False)


@app.post("/v1/scrape/extract")
async def extract_endpoint(payload: dict, raw: Request):
    urls = payload.get("urls")
    if isinstance(urls, str):
        urls = [urls]
    if not isinstance(urls, list) or not urls or len(urls) > 10 or not (payload.get("schema") or payload.get("prompt")):
        return failure(raw.url.path, "scrape.extract", "invalid_request", "Supply 1-10 URLs and schema or prompt.", 400)
    replay = await replay_or_require_key(raw, raw.url.path, "scrape.extract", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=raw.url.path, capability="scrape.extract", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    pages, _, _ = await scrape_website(WebsiteScrapeRequest(urls=urls, contentFormat="markdown", maxChars=payload.get("maxChars", 250_000)))
    schema = payload.get("schema") or {"type": "object"}
    output = []
    for page in pages:
        output.append({"url": page.url, "data": await extract_json(page.markdown or page.text or "", schema, payload.get("prompt"))})
    return persist(raw.url.path, raw, envelope(route=raw.url.path, capability="scrape.extract", output=output), False)


@app.post("/v1/scrape/pdf")
async def pdf_endpoint(payload: dict, raw: Request):
    if not isinstance(payload.get("url"), str):
        return failure(raw.url.path, "scrape.website", "invalid_request", "url is required.", 400)
    replay = await replay_or_require_key(raw, raw.url.path, "scrape.website", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=raw.url.path, capability="scrape.website", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    output = await extract_pdf(payload["url"], payload.get("maxPages"), payload.get("maxChars", 250_000))
    return persist(raw.url.path, raw, envelope(route=raw.url.path, capability="scrape.website", output=output), False)


@app.post("/v1/scrape/youtube/transcript")
async def youtube_transcript_endpoint(payload: dict, raw: Request):
    if not isinstance(payload.get("url"), str):
        return failure(raw.url.path, "scrape.youtube", "invalid_request", "url is required.", 400)
    return await youtube_response(raw.url.path, payload, raw, lambda: youtube_transcript(payload["url"], payload.get("includeSegments", True), payload.get("maxChars", 250_000)))


@app.post("/v1/scrape/youtube/thumbnail")
async def youtube_thumbnail_endpoint(payload: dict, raw: Request):
    if not isinstance(payload.get("url"), str):
        return failure(raw.url.path, "scrape.youtube", "invalid_request", "url is required.", 400)
    return await youtube_response(raw.url.path, payload, raw, lambda: youtube_thumbnail(payload["url"]))


@app.post("/v1/scrape/youtube/{resource}")
async def youtube_resources(resource: str, payload: dict, raw: Request):
    max_items = min(payload.get("maxItems", 5), 100)
    if resource == "search" and isinstance(payload.get("query"), str):
        return await youtube_response(raw.url.path, payload, raw, lambda: youtube_search_videos(payload["query"], max_items))
    if resource in {"channel", "shorts"} and isinstance(payload.get("channels"), list):
        channels = [item for item in payload["channels"] if isinstance(item, str) and item]
        return await youtube_response(raw.url.path, payload, raw, lambda: youtube_channel_videos(channels, resource == "shorts", max_items))
    return failure(raw.url.path, "scrape.youtube", "invalid_request", "Use query or channels as required by this endpoint.", 400)


async def public_source_response(route: str, capability: str, payload: dict, raw: Request, action):
    replay = await replay_or_require_key(raw, route, capability, payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=route, capability=capability, status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    try:
        output = await action()
    except ValueError as error:
        return failure(route, capability, "invalid_request", str(error), 400)
    except EmailError as error:
        return failure(route, capability, "email_not_configured", str(error), 503)
    except MetaAdsError as error:
        return failure(route, capability, "meta_ads_not_configured", str(error), 503)
    except RuntimeError as error:
        return failure(route, capability, "request_failed", str(error), 502)
    output, collection_state = strip_collection_state(output)
    source_name = {
        "scrape.google": "openstreetmap-nominatim",
        "scrape.open-business": "openstreetmap-nominatim",
        "scrape.amazon": "public-amazon-structured",
        "scrape.twitter": "public-x-pages",
        "scrape.instagram": "instagram-public-og",
        "scrape.facebook": "public-facebook-pages",
        "scrape.facebook.ads": "meta-ads-library-api",
        "scrape.tiktok": "public-tiktok-pages",
        "scrape.threads": "public-threads-pages",
    }.get(capability)
    if capability == "scrape.facebook.ads" and isinstance(output, dict) and source_name:
        urls = provenance_library_urls(output)
        source = provenance(source_name, urls, "complete" if urls else "empty")
    elif source_name:
        source = provenance(source_name, state=collection_state)
    elif capability == "seo.read" and isinstance(output, dict):
        adapter_id = output.get("adapterId")
        source = provenance(
            seo_provenance_name(adapter_id) if isinstance(adapter_id, str) else "seo-policy",
            state=collection_state,
        )
    elif capability == "email.verify" and isinstance(output, dict):
        syntax = output.get("syntax") if isinstance(output.get("syntax"), dict) else {}
        adapter_id = syntax.get("adapterId")
        source = provenance(adapter_id if isinstance(adapter_id, str) else "email-verification-policy", state=collection_state)
    else:
        source = None
    return persist(route, raw, envelope(route=route, capability=capability, output=output, source=source), False)


@app.post("/v1/scrape/twitter")
async def twitter_alias(payload: dict, raw: Request):
    return await public_source_response(raw.url.path, "scrape.twitter", payload, raw, lambda: social("twitter", "search", payload))


@app.post("/v1/scrape/instagram/hashtag")
async def instagram_hashtag_endpoint(payload: dict, raw: Request):
    return await public_source_response(raw.url.path, "scrape.instagram", payload, raw, lambda: instagram_hashtag(payload))


@app.post("/v1/scrape/google/places")
async def google_places_endpoint(payload: dict, raw: Request):
    return await public_source_response(raw.url.path, "scrape.google", payload, raw, lambda: google_places(payload))


@app.post("/v1/scrape/open-business/search")
async def open_business_search_endpoint(payload: dict, raw: Request):
    return await public_source_response(raw.url.path, "scrape.open-business", payload, raw, lambda: search_open_business(payload))


@app.post("/v1/scrape/threads/posts")
async def threads_posts(payload: dict, raw: Request):
    urls = payload.get("urls")
    if isinstance(urls, str):
        urls = [urls]
    return await public_source_response(
        raw.url.path, "scrape.threads", payload, raw,
        lambda: public_pages(urls, int(payload.get("maxItems", 10))) if isinstance(urls, list) and urls else (_ for _ in ()).throw(ValueError("urls must be a non-empty list")),
    )


@app.post("/v1/scrape/{provider}/{resource}")
async def public_source_endpoint(provider: str, resource: str, payload: dict, raw: Request):
    supported = {
        "twitter": {"search", "user", "replies"},
        "instagram": {"profile", "posts", "comments"},
        "facebook": {"ads", "groups"},
        "tiktok": {"search", "profile", "posts", "comments", "transcript"},
        "amazon": {"reviews", "product", "search"},
    }
    if resource not in supported.get(provider, set()):
        return failure(raw.url.path, None, "unknown_capability", "Unsupported local public-source endpoint.", 404)
    if provider == "facebook" and resource == "ads":
        capability = "scrape.facebook.ads"
    else:
        capability = f"scrape.{provider}"
    if provider == "facebook":
        action = lambda: facebook(payload, resource)
    elif provider == "instagram":
        action = lambda: instagram_collect(resource, payload)
    elif provider == "amazon":
        action = lambda: amazon(payload, resource)
    elif provider == "tiktok" and resource == "search":
        query = payload.get("query")
        action = lambda: public_pages([f"https://www.tiktok.com/search?q={query}"], int(payload.get("maxItems", 10))) if isinstance(query, str) else (_ for _ in ()).throw(ValueError("query is required"))
    else:
        action = lambda: social(provider, resource, payload)
    return await public_source_response(raw.url.path, capability, payload, raw, action)


def default_identity() -> dict | None:
    identities = list_email_identities()
    return next((item for item in identities if item["default"]), None)


async def send_or_draft(payload: dict, *, force_send: bool = False) -> dict:
    recipient, subject, text = payload.get("to"), payload.get("subject"), payload.get("text")
    if not all(isinstance(value, str) and value for value in (recipient, subject, text)):
        raise ValueError("to, subject, and text are required")
    if not (force_send or payload.get("send", False)):
        return {"draft": save_email_draft(recipient, subject, text)}
    identity = default_identity()
    if not identity:
        raise EmailError("Create a local email identity first.")
    return {"message": await send_email(identity, recipient, subject, text)}


@app.post("/v1/generate/image")
async def image_generate(payload: dict, raw: Request):
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return failure(raw.url.path, "generate.image", "invalid_request", "prompt is required.", 400)
    return await public_source_response(raw.url.path, "generate.image", payload, raw, lambda: generate_image(prompt, payload))


@app.post("/v1/vm/run")
async def vm_run_endpoint(payload: dict, raw: Request):
    code, language = payload.get("code"), payload.get("language")
    if not isinstance(code, str) or not isinstance(language, str):
        return failure(raw.url.path, "vm.run", "invalid_request", "code and language are required.", 400)
    replay = await replay_or_require_key(raw, raw.url.path, "vm.run", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=raw.url.path, capability="vm.run", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    client_host = raw.client.host if raw.client else None
    if not is_localhost_client(client_host):
        return failure(
            raw.url.path,
            "vm.run",
            "vm_localhost_only",
            "VM execution accepts requests only from localhost clients.",
            403,
        )
    files, output_files = payload.get("files", []), payload.get("outputFiles", [])
    if not isinstance(files, list) or not isinstance(output_files, list) or not all(isinstance(item, dict) for item in files) or not all(isinstance(item, str) for item in output_files):
        return failure(raw.url.path, "vm.run", "invalid_request", "files and outputFiles must be arrays.", 400)
    request_id = f"local_{uuid4().hex}"
    output = await vm_run(request_id, code, language, files, output_files)
    body = Envelope(requestId=request_id, route=raw.url.path, capability="vm.run", status="succeeded", output=output).model_dump(by_alias=True, exclude_none=True)
    return persist(raw.url.path, raw, body, False)


@app.get("/v1/vm/files/{request_id}/{file_index}")
async def vm_file_download(request_id: str, file_index: int):
    path = vm_output_file(request_id, file_index)
    if not path:
        return failure(f"/v1/vm/files/{request_id}/{file_index}", "vm.files.download", "resource_not_found", "Output file does not exist.", 404)
    return FileResponse(path, filename=path.name)


@app.post("/v1/browser/act")
async def browser_act_endpoint(payload: dict, raw: Request):
    task, start_url = payload.get("task"), payload.get("startUrl")
    if not isinstance(task, str) or not isinstance(start_url, str):
        return failure(raw.url.path, "browser.act", "invalid_request", "task and startUrl are required.", 400)
    return await public_source_response(raw.url.path, "browser.act", payload, raw, lambda: browser_act(task, start_url))


@app.post("/v1/transcribe/uploads")
async def transcription_upload(payload: dict, raw: Request):
    filename, size = payload.get("filename"), payload.get("sizeBytes")
    if not isinstance(filename, str) or not isinstance(size, int):
        return failure(raw.url.path, "audio.transcribe", "invalid_request", "filename and sizeBytes are required.", 400)
    return await public_source_response(raw.url.path, "audio.transcribe", payload, raw, lambda: _create_upload(filename, size))


async def _create_upload(filename: str, size: int) -> dict:
    try:
        return create_upload(filename, size)
    except AudioError as error:
        raise ValueError(str(error)) from error


@app.put("/v1/transcribe/uploads/{upload_id}")
async def transcription_upload_bytes(upload_id: str, raw: Request):
    try:
        write_upload(upload_id, await raw.body())
    except AudioError as error:
        return failure(raw.url.path, "audio.transcribe", "audio_too_large", str(error), 413)
    return {"uploadId": upload_id, "uploaded": True}


@app.post("/v1/transcribe")
async def transcription(payload: dict, raw: Request):
    upload_id = payload.get("uploadId")
    if not isinstance(upload_id, str):
        return failure(raw.url.path, "audio.transcribe", "invalid_request", "uploadId is required.", 400)
    return await public_source_response(raw.url.path, "audio.transcribe", payload, raw, lambda: transcribe(upload_id))


@app.post("/v1/seo/keyword")
async def seo_keyword(payload: dict, raw: Request):
    keywords = payload.get("keywords")
    if not isinstance(keywords, list) or not keywords or len(keywords) > 100 or not all(isinstance(item, str) for item in keywords):
        return failure(raw.url.path, "seo.read", "invalid_request", "keywords must contain 1-100 strings.", 400)
    return await public_source_response(raw.url.path, "seo.read", payload, raw, lambda: seo_keyword_metrics(keywords))


@app.post("/v1/seo/rank")
async def seo_rank_endpoint(payload: dict, raw: Request):
    if not isinstance(payload.get("keyword"), str) or not isinstance(payload.get("domain"), str):
        return failure(raw.url.path, "seo.read", "invalid_request", "keyword and domain are required.", 400)
    return await public_source_response(raw.url.path, "seo.read", payload, raw, lambda: seo_rank(payload["keyword"], payload["domain"], int(payload.get("depth", 10))))


@app.post("/v1/seo/competitors")
async def seo_competitors_endpoint(payload: dict, raw: Request):
    if not isinstance(payload.get("domain"), str):
        return failure(raw.url.path, "seo.read", "invalid_request", "domain is required.", 400)
    return await public_source_response(raw.url.path, "seo.read", payload, raw, lambda: seo_competitors(payload["domain"], int(payload.get("limit", 10))))


@app.post("/v1/seo/optimize")
async def seo_optimize(payload: dict, raw: Request):
    keyword, text = payload.get("keyword"), payload.get("text")
    if not isinstance(keyword, str) or not isinstance(text, str):
        return failure(raw.url.path, "seo.read", "invalid_request", "keyword and text are required in local mode.", 400)
    async def action():
        advice = await extract_json(text, {"type": "object", "properties": {"score": {"type": "number"}, "edits": {"type": "array", "items": {"type": "string"}}}, "required": ["score", "edits"]}, f"Assess this text for the keyword '{keyword}' and list concrete SEO edits.")
        return advice
    return await public_source_response(raw.url.path, "seo.read", payload, raw, action)


@app.post("/v1/seo/audit")
async def seo_audit(payload: dict, raw: Request):
    keyword = payload.get("keyword")
    if not isinstance(keyword, str):
        return failure(raw.url.path, "seo.read", "invalid_request", "keyword is required.", 400)
    async def action():
        ranking = await seo_rank(keyword, payload.get("domain", ""), 10)
        return {"keyword": keyword, "ranking": ranking, "recommendations": None, "adapterId": ranking.get("adapterId")}
    return await public_source_response(raw.url.path, "seo.read", payload, raw, action)


@app.post("/v1/scrape/deep")
async def deep_scrape_endpoint(payload: dict, raw: Request):
    query = payload.get("query")
    if not isinstance(query, str) or not query:
        return failure(raw.url.path, "scrape.deep", "invalid_request", "query is required.", 400)
    return await public_source_response(raw.url.path, "scrape.deep", payload, raw, lambda: deep_research(query, None))


@app.post("/v1/email/find")
async def email_find(payload: dict, raw: Request):
    first_name, last_name = payload.get("firstName"), payload.get("lastName")
    domain = payload.get("domain") or payload.get("company")
    if not all(isinstance(value, str) and value for value in (first_name, last_name, domain)):
        return failure(raw.url.path, "email.find", "invalid_request", "firstName, lastName and domain are required in local mode.", 400)
    return await public_source_response(raw.url.path, "email.find", payload, raw, lambda: find_email(first_name, last_name, domain))


@app.post("/v1/email/verify")
async def email_verify(payload: dict, raw: Request):
    email = payload.get("email")
    if not isinstance(email, str):
        return failure(raw.url.path, "email.verify", "invalid_request", "email is required.", 400)
    async def action():
        return verify_email(email)
    return await public_source_response(raw.url.path, "email.verify", payload, raw, action)


@app.post("/v1/email/enrich")
async def email_enrich(payload: dict, raw: Request):
    email = payload.get("email")
    if not isinstance(email, str) or "@" not in email:
        return failure(raw.url.path, "email.enrich", "invalid_request", "email is required.", 400)
    async def action():
        return {"matchStatus": "not_found", "email": email, "reason": "Local mode does not use person-data brokers"}
    return await public_source_response(raw.url.path, "email.enrich", payload, raw, action)


@app.post("/v1/company/enrich")
async def company_enrich(payload: dict, raw: Request):
    domain = payload.get("domain")
    if not isinstance(domain, str):
        return failure(raw.url.path, "company.enrich", "invalid_request", "domain is required.", 400)
    return await public_source_response(raw.url.path, "company.enrich", payload, raw, lambda: enrich_company(domain))


@app.get("/v1/email/domains")
async def email_domains():
    return envelope(route="/v1/email/domains", capability="email.read", output=list_email_domains())


@app.post("/v1/email/domains")
async def email_domain_create(payload: dict, raw: Request):
    domain = payload.get("domain")
    if not isinstance(domain, str) or not domain or "/" in domain or "@" in domain:
        return failure(raw.url.path, "email.send", "invalid_request", "domain must be a hostname you control.", 400)
    async def action():
        try:
            return create_email_domain(domain.lower(), domain_token())
        except Exception as error:
            raise ValueError("domain already exists") from error
    return await public_source_response(raw.url.path, "email.send", payload, raw, action)


@app.post("/v1/email/domains/{domain_id}/verify")
async def email_domain_verify(domain_id: str, payload: dict, raw: Request):
    item = get_email_domain(domain_id)
    if not item:
        return failure(raw.url.path, "email.send", "email_domain_not_found", "List domains and use a returned domainId.", 404)
    async def action():
        if await dns_has_token(item["domain"], item["dnsRecords"][0]["value"]):
            return set_email_domain_verified(domain_id)
        return {**item, "verified": False}
    return await public_source_response(raw.url.path, "email.send", payload, raw, action)


@app.delete("/v1/email/domains/{domain_id}")
async def email_domain_delete(domain_id: str):
    if not delete_email_domain(domain_id):
        return failure(f"/v1/email/domains/{domain_id}", "email.send", "email_domain_not_found", "List domains and use a returned domainId.", 404)
    return envelope(route=f"/v1/email/domains/{domain_id}", capability="email.send", output={"deleted": True})


@app.get("/v1/email/identities")
async def email_identities():
    return envelope(route="/v1/email/identities", capability="email.read", output=list_email_identities())


@app.post("/v1/email/identities")
async def email_identity_create(payload: dict, raw: Request):
    replay = await replay_or_require_key(raw, raw.url.path, "email.send", payload.get("dryRun", False))
    if replay:
        return replay
    if payload.get("dryRun"):
        return envelope(route=raw.url.path, capability="email.send", status="dry_run", estimate={"maxDebitMicrousd": 0, "basis": "local"})
    email = payload.get("email") or settings.smtp_from
    if not email and isinstance(payload.get("username"), str) and isinstance(payload.get("domain"), str):
        email = f"{payload['username']}@{payload['domain']}"
    if not isinstance(email, str) or "@" not in email:
        return failure(raw.url.path, "email.send", "invalid_request", "Provide email, or username and domain.", 400)
    item = create_email_identity(email, payload.get("displayName") or email.split("@", 1)[0])
    return persist(raw.url.path, raw, envelope(route=raw.url.path, capability="email.send", output=item), False)


@app.patch("/v1/email/identities/{email_identity_id}")
async def email_identity_update(email_identity_id: str, payload: dict, raw: Request):
    display_name = payload.get("displayName")
    if not isinstance(display_name, str) or not display_name:
        return failure(raw.url.path, "email.send", "invalid_request", "displayName is required in local mode.", 400)
    async def action():
        item = update_email_identity(email_identity_id, display_name)
        if not item:
            raise ValueError("email identity does not exist")
        return item
    return await public_source_response(raw.url.path, "email.send", payload, raw, action)


@app.get("/v1/email/drafts")
async def email_drafts():
    return envelope(route="/v1/email/drafts", capability="email.read", output=list_email_drafts())


@app.get("/v1/email/messages")
async def email_messages():
    return envelope(route="/v1/email/messages", capability="email.read", output=list_email_messages())


@app.post("/v1/email/send")
async def email_send(payload: dict, raw: Request):
    return await public_source_response(raw.url.path, "email.send", payload, raw, lambda: send_or_draft(payload))


@app.post("/v1/email/drafts/{draft_id}/send")
async def email_draft_send(draft_id: str, payload: dict, raw: Request):
    draft = get_email_draft(draft_id)
    if not draft:
        return failure(raw.url.path, "email.send", "email_draft_not_found", "List drafts and use a returned draftId.", 404)
    async def action():
        result = await send_or_draft({"to": draft["to"], "subject": draft["subject"], "text": draft["text"], "send": True}, force_send=True)
        remove_email_draft(draft_id)
        return result
    return await public_source_response(raw.url.path, "email.send", payload, raw, action)


@app.get("/v1/memory")
async def memory_list() -> dict:
    files = list_memory()
    return envelope(route="/v1/memory", capability="memory.list", output={"files": files, "usage": {"files": len(files), "maxFiles": 200}})


@app.get("/v1/memory/{path:path}")
async def memory_read(path: str):
    item = get_memory(path)
    if not item:
        return failure(f"/v1/memory/{path}", "memory.read", "memory_file_not_found", "Create the file with POST.", 404)
    return envelope(route=f"/v1/memory/{path}", capability="memory.read", output=item)


@app.post("/v1/memory/{path:path}")
async def memory_write(path: str, payload: dict, raw: Request):
    replay = await replay_or_require_key(raw, f"/v1/memory/{path}", "memory.write", False)
    if replay:
        return replay
    content = payload.get("content")
    if not isinstance(content, str) or len(content.encode()) > 256 * 1024:
        return failure(f"/v1/memory/{path}", "memory.write", "invalid_request", "content must be text up to 256 KB.", 400)
    item, written = write_memory(path, content, payload.get("ifVersion"))
    if not written:
        return failure(f"/v1/memory/{path}", "memory.write", "memory_version_conflict", "Read and merge the latest version.", 409)
    return persist(f"/v1/memory/{path}", raw, envelope(route=f"/v1/memory/{path}", capability="memory.write", output=item), False)


@app.delete("/v1/memory/{path:path}")
async def memory_delete(path: str):
    if not delete_memory(path):
        return failure(f"/v1/memory/{path}", "memory.write", "memory_file_not_found", "File does not exist.", 404)
    return envelope(route=f"/v1/memory/{path}", capability="memory.write", output={"deleted": True})


@app.get("/v1/usage")
async def usage(sinceDays: int = 7) -> dict:
    return envelope(route="/v1/usage", capability="account.usage", output={"sinceDays": min(max(sinceDays, 1), 365), "debitMicrousd": 0, "byCapability": []})


@app.post("/v1/feedback")
async def feedback(payload: dict, raw: Request):
    if not isinstance(payload.get("message"), str) or not payload["message"]:
        return failure(raw.url.path, "feedback.send", "invalid_request", "message is required.", 400)
    return await public_source_response(raw.url.path, "feedback.send", payload, raw, lambda: _feedback(payload))


async def _feedback(payload: dict) -> dict:
    return {"accepted": True, "category": payload.get("category", "idea"), "local": True}


@app.get("/v1/requests")
async def requests_list(limit: int = 20) -> dict:
    return envelope(route="/v1/requests", capability="request.list", output=list_requests(min(max(limit, 1), 100)))


@app.get("/v1/requests/{request_id}")
async def request_status(request_id: str):
    response = get_request(request_id)
    if not response:
        return failure(f"/v1/requests/{request_id}", "request.status", "request_not_found", "Check requestId.", 404)
    return response


@app.get("/v1/balance")
async def balance() -> dict:
    return envelope(route="/v1/balance", capability="account.balance", output={"availableMicrousd": None, "currency": "local"})


@app.get("/v1/me")
async def me() -> dict:
    return envelope(route="/v1/me", capability="account.info", output={"apiKey": {"local": True, "rateLimitPerMinute": 60}, "workspace": {"rateLimitPerMinute": 300}})


@app.get("/v1/capabilities")
async def capabilities(capability: str | None = None):
    if capability:
        item = get_capability(capability)
        if not item:
            return failure("/v1/capabilities", "account.capabilities", "unknown_capability", "Unknown capability.", 404)
        return envelope(route="/v1/capabilities", capability="account.capabilities", output=item.output())
    return envelope(route="/v1/capabilities", capability="account.capabilities", output=list_capabilities())
