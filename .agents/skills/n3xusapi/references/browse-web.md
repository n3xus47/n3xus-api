# Browser and VM workflows

## Browser actions

Use `POST /v1/browser/act` only when ordinary scraping cannot complete a public read task:

```json
{
  "task": "Find the public contact email shown on the page",
  "startUrl": "https://example.com"
}
```

The local browser uses Chromium and the configured local model. It is limited to eight safe steps and returns a trace. It can read pages, follow public links, change public filters, paginate, and fill visible search fields. It blocks login, registration, purchases, form submission, CAPTCHA interaction, and credential entry. If a human challenge appears, the headed browser may wait for the operator.

Treat `isSuccess: false`, a blocked trace, or a human-challenge timeout as an incomplete result. Do not claim that the requested fact was found unless `result` supports it.

## Local VM

Use `POST /v1/vm/run` for a short script, test, shell command, or Docker operation that the user explicitly asked n3xusAPI to execute:

```json
{
  "language": "python",
  "code": "print('hello')",
  "files": [],
  "outputFiles": []
}
```

The VM route is localhost-only, requires Docker socket access, and is not a full security boundary. Output is capped and returned with explicit truncation flags. Download declared output files through the returned `/v1/vm/files/{requestId}/{fileIndex}` URL.
