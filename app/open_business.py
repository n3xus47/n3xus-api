"""Structured open-business search using OpenStreetMap Nominatim (ODbL)."""
import httpx

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
_NULLABLE_FIELDS = frozenset({"rating", "reviewCount"})


def _nominatim_source_url(row: dict) -> str | None:
    osm_url = row.get("osm_url")
    if isinstance(osm_url, str) and osm_url:
        return osm_url
    osm_type = row.get("osm_type")
    osm_id = row.get("osm_id")
    if osm_type and osm_id is not None:
        return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    return None


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
        "sourceUrl": _nominatim_source_url(row),
        "rating": None,
        "reviewCount": None,
    }
    if isinstance(extratags.get("phone"), str) and extratags["phone"].strip():
        record["phone"] = extratags["phone"].strip()
    if isinstance(extratags.get("website"), str) and extratags["website"].strip():
        record["website"] = extratags["website"].strip()
    return {key: value for key, value in record.items() if value is not None or key in _NULLABLE_FIELDS}


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
