"""Official Meta Ads Library (Graph API ``ads_archive``) adapter."""

import httpx

from app.config import settings

GRAPH_URL = "https://graph.facebook.com/v21.0/ads_archive"
LIBRARY_FIELDS = (
    "id",
    "ad_creation_time",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "ad_creative_bodies",
    "ad_creative_link_captions",
    "ad_creative_link_descriptions",
    "ad_creative_link_titles",
    "ad_snapshot_url",
    "page_id",
    "page_name",
    "publisher_platforms",
    "eu_total_reach",
    "beneficiary_payers",
    "bylines",
    "spend",
    "impressions",
    "demographic_distribution",
)


class MetaAdsError(Exception):
    pass


def _first(value: object) -> str | None:
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], str) else None
    return value if isinstance(value, str) else None


def normalize_ad(row: dict) -> dict:
    ad_id = row.get("id")
    bodies = row.get("ad_creative_bodies")
    if isinstance(bodies, str):
        bodies = [bodies]
    elif not isinstance(bodies, list):
        bodies = []
    transparency = {
        key: row[key]
        for key in ("eu_total_reach", "beneficiary_payers", "bylines", "spend", "impressions", "demographic_distribution")
        if row.get(key) is not None
    }
    return {
        "id": ad_id,
        "libraryUrl": f"https://www.facebook.com/ads/library/?id={ad_id}" if isinstance(ad_id, str) else None,
        "copy": {
            "bodies": bodies,
            "linkTitle": _first(row.get("ad_creative_link_titles")),
            "linkDescription": _first(row.get("ad_creative_link_descriptions")),
            "linkCaption": _first(row.get("ad_creative_link_captions")),
        },
        "creative": {"snapshotUrl": row.get("ad_snapshot_url")},
        "landingUrl": None,
        "dates": {
            "createdAt": row.get("ad_creation_time"),
            "deliveryStart": row.get("ad_delivery_start_time"),
            "deliveryStop": row.get("ad_delivery_stop_time"),
        },
        "platforms": row.get("publisher_platforms") if isinstance(row.get("publisher_platforms"), list) else [],
        "page": {"id": row.get("page_id"), "name": row.get("page_name")},
        "transparency": transparency,
    }


def _countries(payload: dict) -> list[str]:
    raw = payload.get("countries") or payload.get("adReachedCountries") or ["US"]
    if isinstance(raw, str):
        return [raw.upper()]
    if isinstance(raw, list) and raw and all(isinstance(item, str) for item in raw):
        return [item.upper() for item in raw]
    raise ValueError("countries must be a country code or non-empty list of codes")


async def search_ads(payload: dict) -> dict:
    token = settings.meta_ads_access_token
    if not token:
        raise MetaAdsError("Set N3XUS_API_META_ADS_ACCESS_TOKEN to use the Meta Ads Library API.")
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    params: dict[str, str | int] = {
        "access_token": token,
        "search_terms": query.strip(),
        "ad_reached_countries": ",".join(_countries(payload)),
        "limit": min(int(payload.get("maxItems", 25)), 100),
        "fields": ",".join(LIBRARY_FIELDS),
    }
    if isinstance(payload.get("pageToken"), str) and payload["pageToken"]:
        params["after"] = payload["pageToken"]
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_secs, headers={"User-Agent": settings.user_agent}) as client:
            response = await client.get(GRAPH_URL, params=params)
            if response.status_code in {401, 403}:
                raise MetaAdsError("Meta Ads Library access token was rejected.")
            response.raise_for_status()
            body = response.json()
    except MetaAdsError:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise MetaAdsError("Meta Ads Library API request failed") from error
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        rows = []
    paging = body.get("paging") if isinstance(body, dict) else {}
    cursors = paging.get("cursors") if isinstance(paging, dict) else {}
    next_token = cursors.get("after") if isinstance(cursors, dict) else None
    return {
        "ads": [normalize_ad(row) for row in rows if isinstance(row, dict)],
        "nextPageToken": next_token if isinstance(next_token, str) and next_token else None,
    }
