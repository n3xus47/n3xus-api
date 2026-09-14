"""Structured open-business search using OpenStreetMap Nominatim (ODbL)."""
from urllib.parse import quote_plus

import httpx

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"


def normalize_nominatim_row(row: dict) -> dict:
    extratags = row.get("extratags") if isinstance(row.get("extratags"), dict) else {}
    record = {
        "name": row.get("name") or row.get("display_name"),
        "formattedAddress": row.get("display_name"),
        "address": row.get("address") if isinstance(row.get("address"), dict) else None,
        "latitude": row.get("lat"),
        "longitude": row.get("lon"),
        "category": row.get("category"),
        "placeType": row.get("type"),
        "osmType": row.get("osm_type"),
        "osmId": row.get("osm_id"),
        "sourceUrl": row.get("osm_url")
        or (
            f"https://www.openstreetmap.org/{row['osm_type']}/{row['osm_id']}"
            if row.get("osm_type") and row.get("osm_id") is not None
            else None
        ),
        "rating": None,
        "reviewCount": None,
    }
    if isinstance(extratags.get("phone"), str) and extratags["phone"].strip():
        record["phone"] = extratags["phone"].strip()
    if isinstance(extratags.get("website"), str) and extratags["website"].strip():
        record["website"] = extratags["website"].strip()
    return {key: value for key, value in record.items() if value is not None or key in {"rating", "reviewCount"}}


async def fetch_nominatim(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "n3xusAPI local tools"}) as client:
        response = await client.get(
            NOMINATIM_SEARCH,
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "extratags": 1,
                "limit": limit,
            },
        )
        response.raise_for_status()
        rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("unexpected nominatim payload")
    return [row for row in rows if isinstance(row, dict)]


async def search_open_business(payload: dict) -> dict:
    search = payload.get("search")
    if not isinstance(search, str) or not search:
        raise ValueError("search is required")
    location = payload.get("location")
    query = f"{search}, {location}" if isinstance(location, str) and location.strip() else search
    limit = min(int(payload.get("maxItems", 10)), 50)
    try:
        rows = await fetch_nominatim(query, limit)
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("OpenStreetMap public geocoder is unavailable") from error
    businesses = [normalize_nominatim_row(row) for row in rows]
    return {"attribution": OSM_ATTRIBUTION, "businesses": businesses, "places": businesses}
