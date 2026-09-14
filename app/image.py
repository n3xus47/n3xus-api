import httpx

from app.config import settings


class ImageError(Exception):
    pass


async def generate_image(prompt: str, payload: dict) -> dict:
    if not settings.stable_diffusion_url:
        raise ImageError("Set N3XUS_API_STABLE_DIFFUSION_URL to a local AUTOMATIC1111-compatible server")
    body = {
        "prompt": prompt,
        "negative_prompt": payload.get("negativePrompt", ""),
        "width": payload.get("width", 1024),
        "height": payload.get("height", 1024),
        "steps": payload.get("steps", 25),
        "seed": payload.get("seed", -1),
    }
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{settings.stable_diffusion_url.rstrip('/')}/sdapi/v1/txt2img", json=body)
            response.raise_for_status()
            images = response.json().get("images", [])
    except (httpx.HTTPError, ValueError) as error:
        raise ImageError("Local Stable Diffusion server is unavailable") from error
    if not images:
        raise ImageError("Local Stable Diffusion server returned no image")
    return {"images": [f"data:image/png;base64,{image}" for image in images]}
