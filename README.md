# n3xusAPI

Lokalne API do aktualnego wyszukiwania, badania i pobierania danych z publicznego internetu. Jest niezależne od zewnętrznych platform API.

## Obecnie obsługiwane

- `POST /v1/scrape/website` — ekstrakcja artykułu do Markdown i/lub tekstu, wielostronicowe crawl, limit znaków i fallback Chromium/Playwright dla stron renderowanych JavaScriptem.
- `POST /v1/search/web` — wyniki SearxNG w zgodnym formacie.
- `POST /v1/scrape/github/*` — publiczny GitHub API: profile, repozytoria, issues, pull requests, commity, zawartość i wyszukiwanie.
- `POST /v1/scrape/youtube/*` — transkrypcje, miniatury oraz znormalizowane rekordy wideo z wyszukiwania, wielu kanałów i Shorts (publiczna zakładka `/shorts`, z fallbackiem filtrowania `/videos`). Pola m.in. `id`, `url`, `channelHandle`, `isShort`; provenance w `source`.
- `POST /v1/scrape/pdf` — tekstowa warstwa publicznych PDF-ów.
- `POST /v1/scrape/{twitter,instagram,tiktok,facebook,amazon}/*`, `/v1/scrape/threads/posts` i `/v1/scrape/google/places` — bezpłatne adaptery wyłącznie do publicznych stron; Google Places korzysta z OpenStreetMap/Nominatim.
- `POST /v1/research/deep` i `/v1/scrape/extract` — badanie oparte na źródłach oraz ekstrakcja JSON przez lokalny Ollama.
- `POST /v1/email/*` — lokalne szkice oraz wysyłka przez własny SMTP po ustawieniu `N3XUS_API_SMTP_URL` i utworzeniu tożsamości. Wyszukiwanie kontaktu sprawdza wyłącznie jawnie opublikowane adresy na stronie firmy; nie zgaduje adresów ani nie używa brokerów danych.
- `POST /v1/seo/*` — lokalny ranking i konkurenci oparte na SearxNG; bezpłatne źródła nie publikują wiarygodnych wolumenów i CPC, więc te pola mają wartość `null`.
- `POST /v1/browser/act` — lokalny Chromium + Ollama dla ograniczonych zadań na publicznej stronie: odczyt, linki, filtry, sortowanie, paginacja i wyszukiwarki. Blokuje logowanie, zakupy, CAPTCHA oraz formularze.
- `POST /v1/transcribe/uploads`, `PUT /v1/transcribe/uploads/{uploadId}`, `POST /v1/transcribe` — prywatny upload do 25 MB i lokalny faster-whisper na CPU.
- `POST /v1/generate/image` — lokalny AUTOMATIC1111/Stable Diffusion po ustawieniu `N3XUS_API_STABLE_DIFFUSION_URL`, np. `http://host.docker.internal:7860`.
- `POST /v1/vm/run`, `GET /v1/vm/files/{requestId}/{fileIndex}` — jednorazowe kontenery Docker z siecią, limitem 1 CPU, 1 GB RAM i 10 minutami wykonania.
- Lokalna pamięć: `GET`, `POST`, `DELETE /v1/memory/{path}`.
- Statusy żądań, idempotencja, `GET /v1/health`, `/v1/me`, `/v1/balance`, `/v1/capabilities`.
- `dryRun: true` waliduje żądanie bez uruchamiania pracy.

Odpowiedzi zachowują podstawowy envelope (`requestId`, `route`, `capability`, `status`, `output`, `error`). Każdy niedry-run `POST` wymaga nagłówka `Idempotency-Key`; identyczne wywołanie zwraca zachowany rezultat. Lokalne wywołania są bezpłatne, dlatego `debitMicrousd` wynosi `0`.

## Uruchomienie

```bash
docker compose up --build
docker compose exec ollama ollama pull qwen3:8b
curl http://localhost:8000/v1/health
```

Dokumentacja OpenAPI: `http://localhost:8000/docs`.

Przykład:

```bash
curl -X POST http://localhost:8000/v1/scrape/website \
  -H 'Content-Type: application/json' \
  -d '{"urls":"https://example.com","contentFormat":"markdown"}'
```

## Granice

API przyjmuje wyłącznie publiczne adresy HTTP(S); blokuje localhost i prywatne sieci, również po przekierowaniu. SearxNG i publiczne źródła mogą ograniczać ruch lub zwracać niepełne wyniki. Adaptery nie omijają logowania, CAPTCHA ani limitów; zablokowane źródło zwraca pustą listę zamiast wymyślonych danych. VM wymaga dostępu API do `/var/run/docker.sock`. To daje kodowi zaufanego lokalnego klienta możliwość przejęcia hosta przez Docker; nie wystawiaj API poza `localhost`. Nie dodawaj kont, cookies ani mechanizmów obchodzenia zabezpieczeń stron bez osobnej decyzji i oceny zgodności z regulaminem źródła.
