from uuid import uuid4

import httpx
import pytest

from app.main import app
from app.models import Page


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_extract_returns_recipe_from_page_without_ollama(client, monkeypatch):
    async def fake_scrape(_):
        return [
            Page(
                url="https://example.com/cake",
                markdown="# Cake\nBuy now",
                recipe={
                    "name": "Lemon cake",
                    "recipeIngredient": ["200 g flour", "2 eggs"],
                    "source": "jsonld",
                    "url": "https://example.com/cake",
                },
            )
        ], [{"url": "https://example.com/cake", "status": "returned"}], None

    async def unexpected_llm(*_args, **_kwargs):
        raise AssertionError("LLM must not run when JSON-LD recipe is present")

    monkeypatch.setattr("app.main.scrape_website", fake_scrape)
    monkeypatch.setattr("app.main.extract_json", unexpected_llm)

    response = await client.post(
        "/v1/scrape/extract",
        headers={"Idempotency-Key": f"extract-recipe-{uuid4()}"},
        json={
            "urls": ["https://example.com/cake"],
            "prompt": "Extract the recipe as JSON",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "recipeIngredient": {"type": "array"},
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"][0]["data"]["name"] == "Lemon cake"
    assert body["output"][0]["data"]["recipeIngredient"] == ["200 g flour", "2 eggs"]
