# Scraping with n3xusAPI

Use this reference for websites, PDFs, structured extraction, and public platform adapters.

## Website pages

`POST /v1/scrape/website` accepts one URL or a list:

```json
{
  "urls": ["https://example.com/article"],
  "contentFormat": "markdown",
  "maxChars": 25000,
  "maxPages": 10,
  "maxDepth": 0
}
```

Use only the fields needed by the task. `contentFormat` is `markdown` or `text`; `maxChars` is per extracted page. For a crawl, constrain `maxPages`, `maxDepth`, `includeUrls`, or `excludeUrls`.

Read `output` as an array of page objects. A page can include `url`, `markdown` or `text`, `title`, `description`, `language`, `structuredData`, `imageUrls`, and optional `recipe`. `truncated` and `totalChars` appear when the character limit was reached. Read `urlOutcomes` to distinguish returned, blocked, non-HTML, and failed seeds. Use `source.collectionState` to report `complete`, `partial`, `blocked`, or `empty`.

For recipe pages, prefer `output[].recipe` and its `recipeIngredient` data when present. Do not invent ingredients from a generic article or from a search snippet.

## Public image files

Use `POST /v1/scrape/image` when the task needs the actual image bytes rather than image URLs found in page metadata:

```json
{
  "url": "https://example.com/image.jpg"
}
```

The response includes `output.contentType`, `output.finalUrl`, `output.sizeBytes`, and base64 data in `output.base64`. One public raster image up to 15 MB is accepted. Decode or pass along the returned bytes only when the user's task requires the image; avoid including the full base64 value in a text response. Private-network destinations, unsafe redirects, unsupported media types, and oversized files are rejected.

## Structured extraction

`POST /v1/scrape/extract` requires 1–10 URLs plus `schema` or `prompt`:

```json
{
  "urls": ["https://example.com/page"],
  "schema": {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"]
  },
  "maxChars": 250000
}
```

The output contains one `{url, data}` item per extracted page. JSON-LD and HTML structure are preferred; the local model is a fallback and may be unavailable or incomplete.

## PDFs

`POST /v1/scrape/pdf` accepts a public text-layer PDF URL and optional `maxPages` and `maxChars`. Scanned image-only PDFs are unsupported. Treat `pdf_not_readable` and `pdf_too_large` as explicit failures.

## Platform routes

Prefer the narrowest route when it exists:

- GitHub: `/v1/scrape/github/profile`, `/repo`, `/issues`, `/pulls`, `/commits`, `/contents`, `/search`
- YouTube: `/v1/scrape/youtube/search`, `/channel`, `/shorts`, `/transcript`, `/thumbnail`
- Instagram: `/v1/scrape/instagram/profile`, `/posts`, `/comments`, `/hashtag`
- X/Twitter, TikTok, Facebook, Amazon: `/v1/scrape/{provider}/{resource}`
- Places: `/v1/scrape/open-business/search`; `/v1/scrape/google/places` is an OpenStreetMap/Nominatim compatibility alias
- Threads: `/v1/scrape/threads/posts`

Read `GET /v1/capabilities` before relying on a structured record. `best_effort` routes may return public page content rather than normalized platform data. The Google Places compatibility route is backed by OpenStreetMap Nominatim; it is not Google Places data. Never claim ratings, comments, engagement, product fields, or contact data that the returned object does not contain.

## Public-only boundary

n3xusAPI accepts public HTTP(S) URLs and rejects localhost, private-network targets, credentials in URLs, logins, CAPTCHA solving, and access-control bypasses. A blocked or empty source is a result to report, not a reason to fabricate data or switch to raw direct fetching.
