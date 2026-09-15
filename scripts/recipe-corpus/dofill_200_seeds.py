#!/usr/bin/env python3
"""Dopełnij do 200 przepisów scrape z url_seeds (Gordon/Jamie/Nigella) via n3xusAPI."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib import request

BASE = os.environ.get("N3XUS_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
MIN_MD = 400
TARGET = 200

DOMAIN_CHEF = {
    "gordonramsay.com": ("gordon-ramsay", "Gordon Ramsay"),
    "jamieoliver.com": ("jamie-oliver", "Jamie Oliver"),
    "nigella.com": ("nigella-lawson", "Nigella Lawson"),
}


def api_scrape(url: str) -> tuple[dict, str, int]:
    body = json.dumps({"urls": url, "contentFormat": "markdown", "maxChars": 25000}).encode()
    req = request.Request(
        f"{BASE}/v1/scrape/website",
        data=body,
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())},
        method="POST",
    )
    with request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    pages = data.get("output") or []
    md = (pages[0].get("markdown") if pages else None) or ""
    title = (pages[0].get("title") if pages else None) or url
    return data, title, len(md)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "recipe"


def existing_urls() -> set[str]:
    urls: set[str] = set()
    for path in ROOT.glob("*/*.json"):
        try:
            urls.add(json.loads(path.read_text())["sourceUrl"])
        except (KeyError, json.JSONDecodeError):
            pass
    return urls


def chef_for_url(url: str) -> tuple[str, str] | None:
    for domain, pair in DOMAIN_CHEF.items():
        if domain in url:
            return pair
    return None


def main() -> int:
    seeds = json.loads((ROOT / "url_seeds.json").read_text())
    pool: list[str] = []
    for key in ("gordon-ramsay", "jamie-oliver", "nigella-lawson"):
        pool.extend(seeds.get(key, []))

    used = existing_urls()
    saved = len(used)
    print("Already have", saved, "recipes")

    for url in pool:
        if saved >= TARGET:
            break
        if url in used:
            continue
        meta = chef_for_url(url)
        if not meta:
            continue
        slug, name = meta
        try:
            data, title, md_len = api_scrape(url)
        except Exception as exc:
            print("skip", url[:60], exc)
            continue
        if md_len < MIN_MD:
            continue
        chef_dir = ROOT / slug
        chef_dir.mkdir(exist_ok=True)
        idx = len(list(chef_dir.glob("*.json"))) + 1
        record = {
            "chef": name,
            "chefSlug": slug,
            "title": title,
            "sourceUrl": url,
            "contentMarkdown": (data.get("output") or [{}])[0].get("markdown", ""),
            "contentLength": md_len,
            "n3xusRequestId": data.get("requestId"),
            "n3xusRoute": data.get("route"),
            "method": "scrape.website",
        }
        out = chef_dir / f"{idx:03d}-{slugify(title)}.json"
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        used.add(url)
        saved += 1
        if saved % 10 == 0:
            print("progress", saved)
        time.sleep(0.1)

    counts = {d.name: len(list(d.glob("*.json"))) for d in ROOT.iterdir() if d.is_dir()}
    total = sum(counts.values())
    manifest = json.loads((ROOT / "manifest.json").read_text()) if (ROOT / "manifest.json").exists() else {}
    manifest.update({"totalSaved": total, "counts": counts, "target200FromSeeds": True})
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TOTAL", total)
    return total


if __name__ == "__main__":
    raise SystemExit(0 if main() >= TARGET else 1)
