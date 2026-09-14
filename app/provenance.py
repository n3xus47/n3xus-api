"""Provenance records for data collected from public external sources."""
from datetime import UTC, datetime


def provenance(name: str, urls: list[str] | None = None, state: str = "complete") -> dict:
    return {
        "name": name,
        "urls": urls or [],
        "retrievedAt": datetime.now(UTC).isoformat(),
        "collectionState": state,
    }


def strip_collection_state(output: object) -> tuple[object, str]:
    if isinstance(output, dict) and isinstance(output.get("collectionState"), str):
        state = output["collectionState"]
        body = {key: value for key, value in output.items() if key != "collectionState"}
        return body, state
    if not output:
        return output, "empty"
    return output, "complete"
