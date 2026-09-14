from pathlib import Path

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")


def test_readme_documents_support_levels():
    for level in ("structured", "best_effort", "experimental", "unavailable"):
        assert level in README


def test_readme_documents_capabilities_and_eval_workflow():
    assert "/v1/capabilities" in README
    assert "npm run eval" in README
    assert "docs/evals/WORKFLOW.md" in README


def test_readme_documents_provenance_interpretation():
    assert "collectionState" in README
    for state in ("complete", "partial", "blocked", "empty"):
        assert state in README
