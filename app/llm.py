import json

import httpx

from app.config import settings


class LlmError(Exception):
    pass


async def generate(prompt: str, *, json_mode: bool = False) -> str:
    payload = {"model": settings.ollama_model, "prompt": prompt, "stream": False}
    if json_mode:
        payload["format"] = "json"
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{settings.ollama_url.rstrip('/')}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()["response"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise LlmError("Ollama is unavailable or the configured model is missing") from error


async def extract_json(content: str, schema: dict, prompt: str | None) -> object:
    instruction = prompt or "Extract the requested structured data."
    answer = await generate(
        f"{instruction}\n\nReturn only JSON matching this schema:\n{json.dumps(schema)}\n\nPage:\n{content}",
        json_mode=True,
    )
    try:
        return json.loads(answer)
    except json.JSONDecodeError as error:
        raise LlmError("Model returned invalid JSON") from error
