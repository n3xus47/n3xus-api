"""Sequential, secret-free public-data evaluation against a local API."""
import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from time import perf_counter
from uuid import uuid4
from urllib.parse import urlsplit

import httpx

from app.capabilities import get_capability


def validate_cases(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError("Fixtures must be a non-empty JSON array")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in ids:
            raise ValueError("Each fixture needs a unique string id")
        ids.add(case["id"])
        if not get_capability(case.get("capability")):
            raise ValueError("Unknown fixture capability")
        route = case.get("route", "")
        if not route.startswith(("/v1/scrape/", "/v1/search/", "/v1/research/", "/v1/seo/", "/v1/browser/", "/v1/company/")) or "?" in route or "#" in route:
            raise ValueError("Fixtures must target local public-data routes")
        if not isinstance(case.get("payload"), dict) or case["payload"].get("dryRun"):
            raise ValueError("Fixtures require a payload and must execute real work")
        required = case.get("required")
        if not isinstance(required, list) or not required or not all(isinstance(p, str) and p.startswith("output.") for p in required):
            raise ValueError("Specify non-empty required output paths")
        count = case.get("resultCheckCount", 3)
        if not isinstance(count, int) or count < 1:
            raise ValueError("resultCheckCount must be a positive integer")
        pattern = case.get("expectUrlPattern")
        if pattern is not None and not isinstance(pattern, str):
            raise ValueError("expectUrlPattern must be a string regex")
        keywords = case.get("expectKeywords")
        if keywords is not None:
            if not isinstance(keywords, list) or not keywords or not all(isinstance(k, str) and k for k in keywords):
                raise ValueError("expectKeywords must be a non-empty list of strings")
    return cases


def _top_results(body, limit):
    output = body.get("output")
    if not isinstance(output, dict):
        return []
    results = output.get("results")
    if not isinstance(results, list):
        return []
    return [r for r in results[:limit] if isinstance(r, dict)]


def _case_expects_relevance(case):
    return bool(case.get("expectUrlPattern") or case.get("expectKeywords"))


def _row_relevance_text(row):
    return f"{row.get('url') or ''} {row.get('title') or ''}".casefold()


def check_result_relevance(case, body):
    """Optional topical checks on the first N search results."""
    limit = case.get("resultCheckCount", 3)
    rows = _top_results(body, limit)
    if not rows:
        return "missing_results_for_relevance"
    pattern = case.get("expectUrlPattern")
    if pattern:
        compiled = re.compile(pattern, re.I)
        if not any(compiled.search(str(row.get("url") or "")) for row in rows):
            return "url_pattern_mismatch"
    keywords = case.get("expectKeywords")
    if keywords:
        lowered = [k.casefold() for k in keywords]
        if not any(any(k in _row_relevance_text(row) for k in lowered) for row in rows):
            return "keyword_mismatch"
    return ""


def field_counts(value, parts):
    if not parts:
        return (int(value is not None and value != "" and value != [] and value != {}), 1)
    key, *rest = parts
    if key == "*":
        if not isinstance(value, list) or not value:
            return 0, 1
        counts = [field_counts(item, rest) for item in value]
        return sum(c[0] for c in counts), sum(c[1] for c in counts)
    if not isinstance(value, dict) or key not in value:
        return 0, 1
    return field_counts(value[key], rest)


async def evaluate(client, cases):
    results = []
    for case in cases:
        capability = get_capability(case["capability"])
        started = perf_counter()
        coverage, reason, source = 0.0, "", None
        try:
            response = await client.post(case["route"], json=case["payload"], headers={"Idempotency-Key": f"eval-{uuid4().hex}"})
            if not response.is_success:
                reason = f"http_{response.status_code}"
            try:
                body = response.json()
            except ValueError:
                body = {}
                reason = reason or "invalid_json"
            if not isinstance(body, dict):
                body = {}
                reason = reason or "invalid_envelope"
            source = body.get("source")
            if not isinstance(source, dict) and isinstance(body.get("output"), dict):
                source = body["output"].get("source")
            counts = [field_counts(body, path.split(".")) for path in case["required"]]
            coverage = sum(c[0] for c in counts) / sum(c[1] for c in counts)
            error = body.get("error")
            if isinstance(error, dict) and error.get("code"):
                reason = str(error["code"])
            if not reason and body.get("status") != "succeeded":
                reason = "invalid_status"
            if not reason and not body.get("output"):
                reason = "empty"
            if not reason and isinstance(source, dict) and source.get("collectionState") in {"blocked", "empty", "partial"}:
                reason = source["collectionState"]
            if not reason and body.get("capability") != case["capability"]:
                reason = "capability_mismatch"
            if not reason and coverage < 1:
                reason = "missing_required_fields"
            if not reason and capability.support_level == "unavailable":
                reason = "unavailable"
            if not reason and _case_expects_relevance(case):
                reason = check_result_relevance(case, body)
        except httpx.HTTPError as error:
            reason = type(error).__name__
        results.append({"id": case["id"], "capability": case["capability"], "supportLevel": capability.support_level,
                        "success": not reason, "coverage": coverage, "latencyMs": (perf_counter()-started)*1000,
                        "reason": reason, "source": source})
    return results


def render_report(results):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("<", "&lt;")
    lines = ["# Local data-quality evaluation", "", f"Collected: {datetime.now(UTC).isoformat()}", "",
             "Success means a succeeded response with all required fields and no reported partial/blocked/empty state.",
             "Field presence does not prove factual accuracy. Support levels come from the registry and are never upgraded by this report.",
             "Missing provenance remains unknown; source records are retained in the adjacent JSON report.", "",
             "| Capability | Support | Cases | Success rate | Mean field coverage | Mean latency (ms) |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for slug in sorted({r["capability"] for r in results}):
        group = [r for r in results if r["capability"] == slug]
        n = len(group)
        lines.append(f"| {slug} | {group[0]['supportLevel']} | {n} | {sum(r['success'] for r in group)/n:.1%} | {sum(r['coverage'] for r in group)/n:.1%} | {sum(r['latencyMs'] for r in group)/n:.1f} |")
    lines += ["", "| Case | Success | Field coverage | Latency (ms) | Failure reason |", "| --- | --- | ---: | ---: | --- |"]
    for r in results:
        lines.append(f"| {cell(r['id'])} | {r['success']} | {r['coverage']:.1%} | {r['latencyMs']:.1f} | {cell(r['reason'] or '—')} |")
    return "\n".join(lines) + "\n"


async def run(args):
    cases = validate_cases(json.loads(Path(args.fixtures).read_text()))
    url = urlsplit(args.base_url)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise ValueError("base-url must be a local HTTP API origin without credentials")
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout, trust_env=False) as client:
        results = await evaluate(client, cases)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(results))
    output.with_suffix(".json").write_text(json.dumps({"fixtures": cases, "results": results}, indent=2) + "\n")
    print(f"Wrote {output}: {sum(r['success'] for r in results)}/{len(results)} cases succeeded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default="evals/smoke.json")
    parser.add_argument("--output", default="docs/evals/latest.md")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
