import json
import re

import httpx

from app.config import settings

_REFUSAL_MARKERS = ("not a valid question", "not a question", "i cannot help with that")


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
        "This is a data-extraction task, not a trivia question. "
        "Do not refuse. Return JSON only, with no commentary.\n\n"
        f"{instruction}\n\nJSON schema:\n{json.dumps(schema)}\n\nPage:\n{content}",
        json_mode=True,
    )
    return _parse_model_json(answer)


def _parse_model_json(answer: str) -> object:
    text = answer.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    lowered = text.lower()
    if any(marker in lowered for marker in _REFUSAL_MARKERS):
        raise LlmError("Model refused extraction")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise LlmError("Model returned invalid JSON") from error
