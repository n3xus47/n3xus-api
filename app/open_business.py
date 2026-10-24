"""Structured open-business search using OpenStreetMap Nominatim and Overpass (ODbL)."""
from math import asin, cos, radians, sin, sqrt

import httpx

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
OVERPASS_INTERPRETER = "https://overpass-api.de/api/interpreter"
DEFAULT_RADIUS_METERS = 10_000
MAX_RADIUS_METERS = 50_000
_NULLABLE_FIELDS = frozenset({"rating", "reviewCount"})
_CATEGORY_TAGS = {
    "amenity": {
        "charging_station": {
            "electric vehicle charging station",
            "charging station",
            "charging stations",
            "ev charging station",
            "ev charger",
            "ev chargers",
            "electric car charger",
            "stacja ładowania",
            "stacja ładowania samochodów",
            "ładowarka samochodowa",
        },
        "cafe": {
            "cafe", "cafes", "café", "cafés", "coffee", "coffee shop", "coffee shops",
            "kawiarnia", "kawiarnie",
        },
        "restaurant": {"restaurant", "restaurants", "restauracja", "restauracje"},
        "pharmacy": {"pharmacy", "pharmacies", "apteka", "apteki"},
        "fuel": {"gas station", "petrol station", "fuel station", "stacja paliw", "stacje paliw"},
    },
    "shop": {"supermarket": {"supermarket", "supermarkets", "sklep spożywczy", "supermarkety"}},
}


def _normalized_search(search: str) -> str:
    return " ".join(search.casefold().split())


def _category_tag(search: str) -> tuple[str, str] | None:
    normalized = _normalized_search(search)
    for key, values in _CATEGORY_TAGS.items():
        for value, phrases in values.items():
            if normalized in phrases:
                return key, value
    return None


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


def normalize_overpass_row(row: dict) -> dict:
    tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
    address_keys = {
        "road": "addr:street",
        "house_number": "addr:housenumber",
        "postcode": "addr:postcode",
        "city": "addr:city",
        "town": "addr:town",
        "village": "addr:village",
        "country": "addr:country",
    }
    address = {field: tags[tag] for field, tag in address_keys.items() if tags.get(tag)}
    street = " ".join(filter(None, (address.get("road"), address.get("house_number"))))
    locality = address.get("city") or address.get("town") or address.get("village")
    formatted_address = ", ".join(
        part for part in (street, address.get("postcode"), locality, address.get("country")) if part
    )
    center = row.get("center") if isinstance(row.get("center"), dict) else {}
    latitude = row.get("lat", center.get("lat"))
    longitude = row.get("lon", center.get("lon"))
    osm_type = row.get("type")
    osm_id = row.get("id")
    record = {
        "name": tags.get("name") or tags.get("operator") or tags.get("brand"),
        "address": address or None,
        "latitude": latitude,
        "longitude": longitude,
        "category": next(
            (key for key in ("amenity", "shop", "leisure", "healthcare") if tags.get(key)), None
        ),
        "placeType": next(
            (tags[key] for key in ("amenity", "shop", "leisure", "healthcare") if tags.get(key)), None
        ),
        "osmType": osm_type,
        "osmId": osm_id,
        "sourceUrl": f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id is not None else None,
        "rating": None,
        "reviewCount": None,
    }
    if formatted_address:
        record["formattedAddress"] = formatted_address
    for output_key, tag_names in {
        "phone": ("contact:phone", "phone"),
        "website": ("contact:website", "website", "contact:url", "url"),
    }.items():
        value = next(
            (tags[tag] for tag in tag_names if isinstance(tags.get(tag), str) and tags[tag].strip()),
            None,
        )
        if value:
            record[output_key] = value.strip()
    return {key: value for key, value in record.items() if value is not None or key in _NULLABLE_FIELDS}


async def fetch_nominatim(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "n3xusAPI local tools"}) as client:
        response = await client.get(
            NOMINATIM_SEARCH,
            params={"q": query, "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": limit},
        )
        response.raise_for_status()
        rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("unexpected nominatim payload")
    return [row for row in rows if isinstance(row, dict)]


async def fetch_overpass(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(
        timeout=5, headers={"User-Agent": "n3xusAPI local tools", "Accept": "application/json"}
    ) as client:
        response = await client.post(OVERPASS_INTERPRETER, data={"data": query})
        response.raise_for_status()
        payload = response.json()
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        raise ValueError("unexpected Overpass payload")
    return [row for row in elements if isinstance(row, dict)][:limit]


def _overpass_query(key: str, value: str, latitude: float, longitude: float, radius: int, limit: int) -> str:
    return (
        f'[out:json][timeout:5];nwr(around:{radius},{latitude},{longitude})'
        f'["{key}"="{value}"];out center tags {limit};'
    )


async def _search_category(search: str, location: str, radius: int, limit: int) -> tuple[list[dict], bool]:
    category = _category_tag(search)
    if category is None:
        raise ValueError("unsupported category")
    location_rows = await fetch_nominatim(location, 1)
    if not location_rows:
        return [], False
    try:
        latitude = float(location_rows[0]["lat"])
        longitude = float(location_rows[0]["lon"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("OpenStreetMap could not resolve the requested location") from error
    query = _overpass_query(*category, latitude, longitude, radius, limit)
    try:
        return await fetch_overpass(query, limit), False
    except (httpx.HTTPError, ValueError):
        fallback_query = f"{category[1].replace('_', ' ')} in {location}"
        fallback_rows = await fetch_nominatim(fallback_query, min(limit * 5, 50))
        matching_rows = [
            row for row in fallback_rows
            if row.get("category") == category[0]
            and row.get("type") == category[1]
            and _is_within_radius(row, latitude, longitude, radius)
        ]
        return matching_rows[:limit], True


def _is_within_radius(row: dict, latitude: float, longitude: float, radius: int) -> bool:
    try:
        row_latitude = float(row["lat"])
        row_longitude = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    latitude_delta = radians(row_latitude - latitude)
    longitude_delta = radians(row_longitude - longitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(latitude)) * cos(radians(row_latitude)) * sin(longitude_delta / 2) ** 2
    )
    distance = 6_371_000 * 2 * asin(sqrt(haversine))
    return distance <= radius


async def search_open_business(payload: dict) -> dict:
    search = payload.get("search")
    if not isinstance(search, str) or not search.strip():
        raise ValueError("search is required")
    location = payload.get("location")
    limit = min(max(int(payload.get("maxItems", 10)), 1), 50)
    category = _category_tag(search)
    try:
        if category and isinstance(location, str) and location.strip():
            radius = min(max(int(payload.get("radiusMeters", DEFAULT_RADIUS_METERS)), 1_000), MAX_RADIUS_METERS)
            rows, fallback_used = await _search_category(search, location.strip(), radius, limit)
            businesses = [normalize_overpass_row(row) for row in rows]
            if fallback_used:
                businesses = [normalize_nominatim_row(row) for row in rows]
        else:
            query = (
                f"{search.strip()}, {location.strip()}"
                if isinstance(location, str) and location.strip()
                else search.strip()
            )
            rows = await fetch_nominatim(query, limit)
            businesses = [normalize_nominatim_row(row) for row in rows]
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("OpenStreetMap search is unavailable") from error
    result = {"attribution": OSM_ATTRIBUTION, "businesses": businesses, "places": businesses}
    if category and isinstance(location, str) and location.strip() and fallback_used:
        result["collectionState"] = "partial"
    return result
