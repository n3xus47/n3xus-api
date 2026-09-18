# Local image generation

Use `POST /v1/generate/image` only when the user asks n3xusAPI to generate an image:

```json
{
  "prompt": "A clean editorial illustration of ...",
  "negativePrompt": "text, watermark",
  "width": 1024,
  "height": 1024,
  "steps": 25,
  "seed": -1
}
```

This route forwards to a local AUTOMATIC1111-compatible Stable Diffusion server configured by `N3XUS_API_STABLE_DIFFUSION_URL`. If it is not configured, report `capability_not_configured`; do not substitute a hosted image provider. The response contains base64 PNG data URLs in `output.images`.
