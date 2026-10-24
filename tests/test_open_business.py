import httpx
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


async def test_category_search_uses_osm_tags_and_returns_places(monkeypatch):
    geocoded_location = {"lat": "52.2297", "lon": "21.0122"}
    charging_station = {
        "type": "node",
        "id": 123,
        "lat": 52.23,
        "lon": 21.01,
        "tags": {
            "name": "Public charger",
            "amenity": "charging_station",
            "operator": "ChargePoint",
            "phone": "+48 123 456 789",
            "website": "https://example.com/charger",
            "addr:street": "Marszałkowska",
            "addr:housenumber": "1",
            "addr:city": "Warszawa",
        },
    }
    calls = []

    async def fake_nominatim(query, limit):
        calls.append((query, limit))
        return [geocoded_location]

    async def fake_overpass(query, limit):
        calls.append((query, limit))
        return [charging_station]

    monkeypatch.setattr("app.open_business.fetch_nominatim", fake_nominatim)
    monkeypatch.setattr("app.open_business.fetch_overpass", fake_overpass)

    output = await search_open_business(
        {"search": "electric vehicle charging station", "location": "Warsaw, Poland", "maxItems": 5}
    )

    assert len(calls) == 2
    assert calls[0] == ("Warsaw, Poland", 1)
    assert '"amenity"="charging_station"' in calls[1][0]
    assert "52.2297" in calls[1][0]
    assert "21.0122" in calls[1][0]
    assert calls[1][1] == 5
    assert output["businesses"][0] == {
        "name": "Public charger",
        "formattedAddress": "Marszałkowska 1, Warszawa",
        "address": {"road": "Marszałkowska", "house_number": "1", "city": "Warszawa"},
        "latitude": 52.23,
        "longitude": 21.01,
        "category": "amenity",
        "placeType": "charging_station",
        "osmType": "node",
        "osmId": 123,
        "sourceUrl": "https://www.openstreetmap.org/node/123",
        "rating": None,
        "reviewCount": None,
        "phone": "+48 123 456 789",
        "website": "https://example.com/charger",
    }
    assert output["places"] is output["businesses"]


async def test_named_business_search_keeps_nominatim_behavior(monkeypatch):
    calls = []

    async def fake_nominatim(query, limit):
        calls.append((query, limit))
        return [SAMPLE_ROW]

    async def unexpected_overpass(*_args):
        raise AssertionError("named searches should not query Overpass")

    monkeypatch.setattr("app.open_business.fetch_nominatim", fake_nominatim)
    monkeypatch.setattr("app.open_business.fetch_overpass", unexpected_overpass)

    output = await search_open_business({"search": "Tour Eiffel", "location": "Paris"})

    assert calls == [("Tour Eiffel, Paris", 10)]
    assert output["businesses"][0]["name"] == "Tour Eiffel"


async def test_category_search_falls_back_to_partial_nominatim_results(monkeypatch):
    nominatim_calls = []
    nearby_station = {
        **SAMPLE_ROW,
        "lat": "52.2300",
        "lon": "21.0100",
        "category": "amenity",
        "type": "charging_station",
        "name": "Nearby charger",
    }
    distant_station = {**nearby_station, "lat": "52.5000", "lon": "21.5000", "name": "Far charger"}

    async def fake_nominatim(query, limit):
        nominatim_calls.append((query, limit))
        if len(nominatim_calls) == 1:
            return [{"lat": "52.2297", "lon": "21.0122"}]
        return [nearby_station, distant_station]

    async def unavailable_overpass(_query, _limit):
        raise httpx.ConnectError("Overpass unavailable")

    monkeypatch.setattr("app.open_business.fetch_nominatim", fake_nominatim)
    monkeypatch.setattr("app.open_business.fetch_overpass", unavailable_overpass)

    output = await search_open_business(
        {"search": "electric vehicle charging station", "location": "Warsaw, Poland", "maxItems": 5}
    )

    assert nominatim_calls == [("Warsaw, Poland", 1), ("charging station in Warsaw, Poland", 25)]
    assert output["collectionState"] == "partial"
    assert [row["name"] for row in output["businesses"]] == ["Nearby charger"]


async def test_unresolved_category_location_returns_empty_results(monkeypatch):
    async def no_location(_query, _limit):
        return []

    async def unexpected_overpass(*_args):
        raise AssertionError("Overpass should not run without resolved coordinates")

    monkeypatch.setattr("app.open_business.fetch_nominatim", no_location)
    monkeypatch.setattr("app.open_business.fetch_overpass", unexpected_overpass)

    output = await search_open_business(
        {"search": "coffee shop", "location": "Unknown Place That Does Not Exist"}
    )

    assert output["businesses"] == []
    assert output["places"] == []
