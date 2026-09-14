"""Provenance records for data collected from public external sources."""
from datetime import UTC, datetime


def provenance(name: str, urls: list[str] | None = None, state: str = "complete") -> dict:
    return {
        "name": name,
        "urls": urls or [],
        "retrievedAt": datetime.now(UTC).isoformat(),
        "collectionState": state,
    }
