import pytest

from app.open_business import normalize_nominatim_row, search_open_business


SAMPLE_ROW = {
    "place_id": 999,
    "osm_type": "way",
    "osm_id": 5013364,
    "lat": "48.8583701",
    "lon": "2.2944813",
    "category": "tourism",
    "type": "attraction",
    "name": "Tour Eiffel",
    "display_name": "Tour Eiffel, 5, Avenue Anatole France, Paris, France",
    "address": {"tourism": "Tour Eiffel", "road": "Avenue Anatole France", "city": "Paris", "country": "France"},
    "extratags": {"website": "https://www.toureiffel.paris/", "phone": "+33 892 70 12 39"},
    "osm_url": "https://www.openstreetmap.org/way/5013364",
}


def test_normalize_nominatim_row_maps_supported_fields_only():
    record = normalize_nominatim_row(SAMPLE_ROW)

    assert record["name"] == "Tour Eiffel"
    assert record["formattedAddress"] == SAMPLE_ROW["display_name"]
    assert record["address"] == SAMPLE_ROW["address"]
    assert record["latitude"] == "48.8583701"
    assert record["longitude"] == "2.2944813"
    assert record["category"] == "tourism"
    assert record["placeType"] == "attraction"
    assert record["osmType"] == "way"
    assert record["osmId"] == 5013364
    assert record["sourceUrl"] == SAMPLE_ROW["osm_url"]
    assert record["website"] == "https://www.toureiffel.paris/"
    assert record["phone"] == "+33 892 70 12 39"
    assert record["rating"] is None
    assert record["reviewCount"] is None


def test_normalize_nominatim_row_omits_unsupported_contact_fields():
    row = {**SAMPLE_ROW, "extratags": {}}
    record = normalize_nominatim_row(row)

    assert "phone" not in record
    assert "website" not in record


async def test_search_open_business_returns_attribution_and_places_alias(monkeypatch):
    async def fake_fetch(_query, _limit):
        return [SAMPLE_ROW]

    monkeypatch.setattr("app.open_business.fetch_nominatim", fake_fetch)

    output = await search_open_business({"search": "Eiffel Tower", "location": "Paris"})

    assert output["attribution"] == "© OpenStreetMap contributors"
    assert output["businesses"][0]["name"] == "Tour Eiffel"
    assert output["places"] == output["businesses"]


async def test_search_open_business_requires_search():
    with pytest.raises(ValueError, match="search is required"):
        await search_open_business({})
