from pathlib import Path

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

SUPPORT_LEVELS = ("structured", "best_effort", "experimental", "unavailable")
COLLECTION_STATES = ("complete", "partial", "blocked", "empty")


def test_readme_documents_support_levels() -> None:
    missing = [level for level in SUPPORT_LEVELS if level not in README]
    assert not missing, f"README missing support levels: {missing}"


def test_readme_documents_capabilities_and_eval_workflow() -> None:
    for fragment in (
        "/v1/capabilities",
        "supportLevel",
        "npm run eval",
        "docs/evals/WORKFLOW.md",
    ):
        assert fragment in README, f"README missing: {fragment!r}"


def test_readme_documents_provenance_interpretation() -> None:
    assert "collectionState" in README
    missing = [state for state in COLLECTION_STATES if state not in README]
    assert not missing, f"README missing collection states: {missing}"
