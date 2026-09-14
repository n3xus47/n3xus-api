# n3xusAPI

Lokalne API do aktualnego wyszukiwania, badania i pobierania danych z publicznego internetu. Jest niezależne od zewnętrznych platform API.

## Obecnie obsługiwane

- `POST /v1/scrape/website` — ekstrakcja artykułu do Markdown i/lub tekstu, wielostronicowe crawl, limit znaków i fallback Chromium/Playwright dla stron renderowanych JavaScriptem.
- `POST /v1/search/web` — wyniki SearxNG w zgodnym formacie.
- `POST /v1/scrape/github/*` — publiczny GitHub API: profile, repozytoria, issues, pull requests, commity, zawartość i wyszukiwanie.
- `POST /v1/scrape/youtube/*` — transkrypcje, miniatury oraz znormalizowane rekordy wideo z wyszukiwania, wielu kanałów i Shorts (publiczna zakładka `/shorts`, z fallbackiem filtrowania `/videos`). Pola m.in. `id`, `url`, `channelHandle`, `isShort`; provenance w `source`.
- `POST /v1/scrape/pdf` — tekstowa warstwa publicznych PDF-ów.
- `POST /v1/scrape/{twitter,instagram,tiktok,facebook,amazon}/*`, `/v1/scrape/threads/posts`, `/v1/scrape/open-business/search` oraz alias `/v1/scrape/google/places` — bezpłatne adaptery do publicznych stron. Amazon zwraca znormalizowane listingi/produkty/recenzje z publicznych stron (US/UK/DE); przy blokadzie CAPTCHA — pusty wynik ze stanem `blocked`, bez surowego tekstu strony. Rekordy open-business pochodzą z OpenStreetMap/Nominatim (nie z Google Places), z jawną atrybucją OSM.
- `POST /v1/research/deep` i `/v1/scrape/extract` — badanie oparte na źródłach oraz ekstrakcja JSON przez lokalny Ollama.
- `POST /v1/email/*` — lokalne szkice oraz wysyłka przez własny SMTP po ustawieniu `N3XUS_API_SMTP_URL` i utworzeniu tożsamości. Wyszukiwanie kontaktu sprawdza wyłącznie jawnie opublikowane adresy na stronie firmy; nie zgaduje adresów ani nie używa brokerów danych. `/v1/email/verify` sprawdza tylko składnię (`checkKind: syntax_only`); dostarczalność wymaga zatwierdzonego adaptera (`docs/email-verification-policy.md`).
- `POST /v1/seo/*` — lokalny ranking i konkurenci oparte na SearxNG; bezpłatne źródła nie publikują wiarygodnych wolumenów i CPC, więc te pola mają wartość `null`.
- `POST /v1/browser/act` — lokalny Chromium + Ollama dla ograniczonych zadań na publicznej stronie: odczyt, linki, filtry, sortowanie, paginacja i wyszukiwarki. Blokuje logowanie, zakupy, CAPTCHA oraz formularze.
- `POST /v1/transcribe/uploads`, `PUT /v1/transcribe/uploads/{uploadId}`, `POST /v1/transcribe` — prywatny upload do 25 MB i lokalny faster-whisper na CPU.
- `POST /v1/generate/image` — lokalny AUTOMATIC1111/Stable Diffusion po ustawieniu `N3XUS_API_STABLE_DIFFUSION_URL`, np. `http://host.docker.internal:7860`.
- `POST /v1/vm/run`, `GET /v1/vm/files/{requestId}/{fileIndex}` — jednorazowe kontenery Docker z siecią, limitem 1 CPU, 1 GB RAM i 10 minutami wykonania.
- Lokalna pamięć: `GET`, `POST`, `DELETE /v1/memory/{path}`.
- Statusy żądań, idempotencja, `GET /v1/health`, `/v1/me`, `/v1/balance`, `/v1/capabilities`.
- `dryRun: true` waliduje żądanie bez uruchamiania pracy.

Odpowiedzi zachowują podstawowy envelope (`requestId`, `route`, `capability`, `status`, `output`, `error`). Każdy niedry-run `POST` wymaga nagłówka `Idempotency-Key`; identyczne wywołanie zwraca zachowany rezultat. Lokalne wywołania są bezpłatne, dlatego `debitMicrousd` wynosi `0`.

## Poziomy wsparcia

Każda możliwość ma przypisany poziom w rejestrze zwracanym przez `GET /v1/capabilities` (pole `supportLevel`). Opcjonalnie filtruj: `GET /v1/capabilities?capability=scrape.amazon`. Poziomy opisują **jakość kontraktu danych**, a nie sam fakt, że endpoint istnieje.

| Poziom | Znaczenie |
| --- | --- |
| `structured` | Normalizowane rekordy z oczekiwanymi polami; adapter jest źródłowo specyficzny (np. GitHub REST, yt-dlp). |
| `best_effort` | Publiczny fetch strony lub ograniczone API; wynik może być niepełny lub ogólny — **nie traktuj go jak pełnego rekordu produktu, posta czy miejsca Google**. |
| `experimental` | Lokalny model lub heurystyka (Ollama, browser act); jakość zależy od konfiguracji. |
| `unavailable` | Celowo nieobsługiwane lokalnie (np. wzbogacanie osoby po e-mail); wywołanie zwraca błąd kontraktu zamiast zgadywać dane. |

Pole `limitations` i `adapter` w tym samym obiekcie wyjaśniają źródło i znane ograniczenia. Pełna mapa luk względem komercyjnych API: `docs/deepapi-parity-audit.md`.

## Pochodzenie danych (`source`)

Gdy dane pochodzą z zewnętrznego publicznego źródła, udane odpowiedzi mogą zawierać blok `source` (na poziomie envelope lub w `output`):

- `name` — identyfikator adaptera (np. `github-public-rest`, `openstreetmap-nominatim`);
- `urls` — adresy użyte przy pobraniu;
- `retrievedAt` — znacznik czasu ISO 8601 (UTC);
- `collectionState` — jak poszło pobranie:
  - `complete` — zebrano oczekiwane dane;
  - `partial` — część pól lub stron brakuje;
  - `blocked` — źródło odmówiło dostępu (limit, CAPTCHA, polityka);
  - `empty` — legalny brak wyników (np. puste wyszukiwanie).

Brak bloku `source` oznacza, że provenance nie zostało jeszcze znormalizowane dla tej trasy — **nie uzupełniaj go samodzielnie**. Pusty wynik z `collectionState: empty` to uczciwy stan, nie błąd klienta.

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

## Ewaluacja jakości danych

Reprodukowalny harness mierzy obecność wymaganych pól, latencję i powody niepowodzeń na **legalnych, publicznych** celach — bez sekretów i credentials.

```bash
docker compose up --build   # API musi działać na localhost
npm run eval -- --fixtures evals/smoke.json --output docs/evals/latest.md
```

Domyślnie: `http://127.0.0.1:8000`, timeout klienta 120 s na operację sieciową. Szczegóły metryk, fixture JSON i interpretacja raportu: `docs/evals/WORKFLOW.md`. Przykładowy raport smoke: `docs/evals/harness-smoke.md`.

**Ważne:** sukces w ewaluacji wymaga `status: succeeded`, wszystkich wymaganych pól **oraz** braku `collectionState` równego `partial`, `blocked` lub `empty`. Raport **nie podnosi** poziomu `supportLevel` — sukces `best_effort` nie oznacza akceptacji jako danych `structured`. Pełny korpus M1 i baseline jakości to osobny krok w backlogu; smoke tylko weryfikuje ścieżkę harnessu.

## Granice

API przyjmuje wyłącznie publiczne adresy HTTP(S); blokuje localhost i prywatne sieci, również po przekierowaniu. SearxNG i publiczne źródła mogą ograniczać ruch lub zwracać niepełne wyniki. Adaptery nie omijają logowania, CAPTCHA ani limitów; zablokowane źródło zwraca pustą listę zamiast wymyślonych danych. VM wymaga dostępu API do `/var/run/docker.sock`. To daje kodowi zaufanego lokalnego klienta możliwość przejęcia hosta przez Docker; nie wystawiaj API poza `localhost`. Nie dodawaj kont, cookies ani mechanizmów obchodzenia zabezpieczeń stron bez osobnej decyzji i oceny zgodności z regulaminem źródła.
