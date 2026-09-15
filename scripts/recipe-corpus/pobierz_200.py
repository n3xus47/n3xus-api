#!/usr/bin/env python3
"""200 przepisów (20 szefów × 10) przez lokalne n3xusAPI — scrape + search."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from urllib import error, request
from urllib.error import HTTPError

BASE = os.environ.get("N3XUS_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
MIN_MD = 400
TARGET_CHEFS = 20
RECIPES_PER_CHEF = 10

CHEFS = [
    {"slug": "gordon-ramsay", "name": "Gordon Ramsay", "seed_key": "gordon-ramsay"},
    {"slug": "jamie-oliver", "name": "Jamie Oliver", "seed_key": "jamie-oliver"},
    {"slug": "nigella-lawson", "name": "Nigella Lawson", "seed_key": "nigella-lawson"},
    {"slug": "wolfgang-puck", "name": "Wolfgang Puck"},
    {"slug": "yotam-ottolenghi", "name": "Yotam Ottolenghi"},
    {"slug": "heston-blumenthal", "name": "Heston Blumenthal"},
    {"slug": "thomas-keller", "name": "Thomas Keller"},
    {"slug": "massimo-bottura", "name": "Massimo Bottura"},
    {"slug": "alice-waters", "name": "Alice Waters"},
    {"slug": "alain-ducasse", "name": "Alain Ducasse"},
    {"slug": "rene-redzepi", "name": "René Redzepi"},
    {"slug": "daniel-boulud", "name": "Daniel Boulud"},
    {"slug": "dominique-crenn", "name": "Dominique Crenn"},
    {"slug": "nobu-matsuhisa", "name": "Nobu Matsuhisa"},
    {"slug": "ina-garten", "name": "Ina Garten"},
    {"slug": "pierre-herme", "name": "Pierre Hermé"},
    {"slug": "ferran-adria", "name": "Ferran Adrià"},
    {"slug": "guy-savoy", "name": "Guy Savoy"},
    {"slug": "mauro-colagreco", "name": "Mauro Colagreco"},
    {"slug": "anne-sophie-pic", "name": "Anne-Sophie Pic"},
]

RECIPE_URL_HINT = re.compile(
    r"(recipe|przepis|/gr/recipes/|jamieoliver\.com/recipes/|nigella\.com/recipes/)",
    re.I,
)


def api_post(route: str, body: dict) -> dict:
    payload = json.dumps(body).encode()
    req = request.Request(
        f"{BASE}{route}",
        data=payload,
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())},
        method="POST",
    )
    with request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:80] or "recipe"


def fetch_html(url: str) -> str:
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; n3xus-recipes/2.0)"})
    return request.urlopen(req, timeout=45).read().decode(errors="ignore")


def refresh_seeds() -> dict[str, list[str]]:
    seeds: dict[str, set[str]] = {"gordon-ramsay": set(), "jamie-oliver": set(), "nigella-lawson": set()}

    html = fetch_html("https://www.gordonramsay.com/gr/recipes/")
    for m in re.finditer(r'href="(/gr/recipes/[a-z0-9-]+/)"', html):
        if "category" not in m.group(1):
            seeds["gordon-ramsay"].add("https://www.gordonramsay.com" + m.group(1))
    for cat in set(re.findall(r'href="(/gr/recipes/category/[^"]+)"', html)):
        try:
            h = fetch_html("https://www.gordonramsay.com" + cat)
        except HTTPError:
            continue
        for m in re.finditer(r'href="(/gr/recipes/[a-z0-9-]+/)"', h):
            if "category" not in m.group(1):
                seeds["gordon-ramsay"].add("https://www.gordonramsay.com" + m.group(1))

    xml = subprocess.check_output(["curl", "-sL", "https://www.jamieoliver.com/sitemap.xml"], text=True)
    for cat in set(re.findall(r"<loc>(https://www.jamieoliver.com/recipes/[a-z0-9-]+-recipes/)</loc>", xml)):
        try:
            h = fetch_html(cat)
        except HTTPError:
            continue
        for m in re.finditer(r'href="(/recipes/[a-z0-9-]+/[a-z0-9-]+/)"', h):
            seeds["jamie-oliver"].add("https://www.jamieoliver.com" + m.group(1))

    for tag in ["chicken", "fish", "beef", "pasta", "dessert", "cake", "soup", "bread", "vegetarian", "italian"]:
        try:
            h = fetch_html(f"https://www.nigella.com/recipes/{tag}")
        except HTTPError:
            continue
        for m in re.finditer(r'href="(/recipes/[a-z0-9-]+)"', h):
            p = m.group(1)
            if "guests" in p or "search" in p or "members" in p:
                continue
            seeds["nigella-lawson"].add("https://www.nigella.com" + p)

    out = {k: sorted(v) for k, v in seeds.items()}
    (ROOT / "url_seeds.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def scrape_url(url: str) -> tuple[dict, str, int]:
    data = api_post("/v1/scrape/website", {"urls": url, "contentFormat": "markdown", "maxChars": 25000})
    pages = data.get("output") or []
    md = (pages[0].get("markdown") if pages else None) or ""
    title = (pages[0].get("title") if pages else None) or url
    return data, title, len(md)


def search_recipe_urls(chef_name: str, limit: int = 25) -> list[str]:
    queries = [
        f"{chef_name} recipe ingredients",
        f"{chef_name} classic recipe official",
        f"{chef_name} best known dish recipe",
    ]
    seen: set[str] = set()
    urls: list[str] = []
    for q in queries:
        try:
            data = api_post("/v1/search/web", {"query": q, "maxResults": 12})
        except error.URLError:
            continue
        for item in (data.get("output") or {}).get("results") or []:
            url = item.get("url")
            if not url or url in seen:
                continue
            if not RECIPE_URL_HINT.search(url):
                continue
            seen.add(url)
            urls.append(url)
        time.sleep(0.3)
        if len(urls) >= limit:
            break
    return urls[:limit]


def save_recipe(chef_dir: Path, index: int, record: dict) -> None:
    name = f"{index:02d}-{slugify(record.get('title') or 'recipe')}.json"
    (chef_dir / name).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def harvest_chef(chef: dict, seeds: dict, used_urls: set[str]) -> list[dict]:
    chef_dir = ROOT / chef["slug"]
    chef_dir.mkdir(parents=True, exist_ok=True)
    for old in chef_dir.glob("*.json"):
        old.unlink()

    saved: list[dict] = []
    candidates: list[str] = []

    key = chef.get("seed_key")
    if key and seeds.get(key):
        candidates.extend(u for u in seeds[key] if u not in used_urls)

    if len(candidates) < RECIPES_PER_CHEF:
        candidates.extend(u for u in search_recipe_urls(chef["name"]) if u not in used_urls)

    for url in candidates:
        if len(saved) >= RECIPES_PER_CHEF:
            break
        if url in used_urls:
            continue
        try:
            data, title, md_len = scrape_url(url)
        except error.URLError:
            continue
        if md_len < MIN_MD:
            continue
        used_urls.add(url)
        pages = data.get("output") or []
        record = {
            "chef": chef["name"],
            "chefSlug": chef["slug"],
            "title": title,
            "sourceUrl": url,
            "contentMarkdown": pages[0].get("markdown") if pages else "",
            "contentLength": md_len,
            "n3xusRequestId": data.get("requestId"),
            "n3xusRoute": data.get("route"),
            "method": "scrape.website",
        }
        save_recipe(chef_dir, len(saved) + 1, record)
        saved.append(record)
        time.sleep(0.12)

    return saved


def main() -> None:
    print("Refreshing URL seeds (HTML discovery, scrape via API)...")
    seeds = refresh_seeds()
    print("Seeds:", {k: len(v) for k, v in seeds.items()})

    used_urls: set[str] = set()
    summary: dict[str, int] = {}
    for chef in CHEFS[:TARGET_CHEFS]:
        items = harvest_chef(chef, seeds, used_urls)
        summary[chef["slug"]] = len(items)
        print(f"{chef['name']}: {len(items)}/{RECIPES_PER_CHEF}")

    total = sum(summary.values())
    manifest = {
        "n3xusApiBaseUrl": BASE,
        "target": f"{TARGET_CHEFS} chefs × {RECIPES_PER_CHEF} recipes = {TARGET_CHEFS * RECIPES_PER_CHEF}",
        "totalSaved": total,
        "counts": summary,
        "seedCounts": {k: len(v) for k, v in seeds.items()},
        "chefs": [c["name"] for c in CHEFS[:TARGET_CHEFS]],
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TOTAL", total)
    return total


if __name__ == "__main__":
    raise SystemExit(0 if main() >= 200 else 1)
