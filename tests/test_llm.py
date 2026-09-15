import pytest

from app.llm import LlmError, _parse_model_json


def test_parse_model_json_accepts_fenced_payload():
    assert _parse_model_json('```json\n{"name": "cake"}\n```') == {"name": "cake"}


def test_parse_model_json_rejects_question_refusal():
    with pytest.raises(LlmError, match="refused"):
        _parse_model_json("That is not a valid question")
