import pytest

from app.llm import LlmError, _parse_model_json


def test_parse_model_json_accepts_fenced_payload():
    assert _parse_model_json('```json\n{"name": "cake"}\n```') == {"name": "cake"}


def test_parse_model_json_rejects_question_refusal():
    with pytest.raises(LlmError, match="refused"):
        _parse_model_json("That is not a valid question")


async def test_generate_applies_output_token_limit(monkeypatch):
    from app.llm import generate

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "short answer"}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeClient)

    answer = await generate("Summarize this evidence", num_predict=512)

    assert answer == "short answer"
    assert captured["payload"]["options"]["num_predict"] == 512
