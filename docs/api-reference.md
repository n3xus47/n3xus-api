# Referencja API

Ten dokument opisuje lokalne API udostępniane przez `app/main.py`. Uruchomiony schemat OpenAPI pod `/openapi.json` jest źródłem prawdy o walidacji i schematach tras; interaktywny podgląd znajduje się pod `/docs`. Trasy korzystające ze źródeł zewnętrznych zależą od ich dostępności i mogą zwrócić częściowy, zablokowany lub pusty wynik.

## Adres bazowy i uwierzytelnianie

Domyślny adres po uruchomieniu Compose to `http://localhost:8000`. Jeśli ustawiono `N3XUS_API_API_KEY`, do każdego żądania poza `GET /v1/health` dodaj `Authorization: Bearer <klucz>`.

Treść żądań JSON używa nazw pól w stylu camelCase, jeśli dotyczy to danego modelu. Ścisłe modele żądań odrzucają nieznane pola; adaptery mogą przyjmować dodatkowe pola specyficzne dla trasy. Każdy `POST` zapisujący żądanie wymaga unikalnego nagłówka `Idempotency-Key`, chyba że ustawiono `dryRun: true`; ponowne użycie klucza odtwarza zapisany wynik. Tryb `dryRun` pomija wykonanie operacji i zwraca envelope ze stanem `dry_run`. Operacje `GET`, `PUT` i `DELETE` na ogół nie korzystają z idempotencji POST.

## Wspólny format odpowiedzi

Większość tras zwraca obiekt podobny do poniższego:

```json
{
  "requestId": "local_…",
  "route": "/v1/scrape/website",
  "capability": "scrape.website",
  "status": "succeeded",
  "replayed": false,
  "costFinal": true,
  "debitMicrousd": 0,
  "output": {},
  "source": {
    "name": "public-website",
    "urls": ["https://example.com"],
    "retrievedAt": "2026-01-01T00:00:00+00:00",
    "collectionState": "complete"
  }
}
```

`status` przyjmuje wartość `succeeded`, `failed` albo `dry_run`. Błędy zawierają `error.code`, `error.retryable` i `error.hint`; niektóre adaptery zwracają również `retryAfterSecs`. Przy ponowieniu z tym samym kluczem idempotencji zwracana jest pierwotna odpowiedź z `replayed: true`. Niektóre proste trasy, w tym kontrola dostępności i odpowiedź zawierająca surowe przesłane bajty, mają format specyficzny dla trasy zamiast wspólnego envelope.

## Stan usługi i inspekcja żądań

| Metoda i trasa | Żądanie | Działanie |
| --- | --- | --- |
| `GET /v1/health` | — | Sprawdza dostępność usługi; zwraca `{"status":"ok"}`. Pomija middleware klucza API. |
| `GET /v1/me` | — | Zwraca lokalne metadane API i przestrzeni roboczej, a nie profil konta hostowanego. |
| `GET /v1/balance` | — | Zwraca metadane lokalnej waluty; nie ma salda kredytów. |
| `GET /v1/usage?sinceDays=7` | Opcjonalny parametr `sinceDays` (ograniczony do 1–365) | Zwraca lokalne podsumowanie użycia; lokalne operacje nie naliczają opłat. |
| `GET /v1/capabilities` | Opcjonalny parametr `capability`, np. `scrape.github` | Zwraca rejestr możliwości albo jeden wpis. |
| `GET /v1/requests?limit=20` | Opcjonalny parametr `limit` (ograniczony do 1–100) | Zwraca ostatnie zapisane żądania idempotentne. |
| `GET /v1/requests/{requestId}` | Ścieżka `requestId` | Zwraca zapisany wynik żądania albo `request_not_found`. |
| `POST /v1/feedback` | `{"message":"…","category":"idea"}` | Lokalnie przyjmuje opinię; nie wysyła jej do hostowanej usługi. |

## Wyszukiwanie i pobieranie danych

| Metoda i trasa | Wymagane pola żądania | Działanie i przydatne pola opcjonalne |
| --- | --- | --- |
| `POST /v1/search/web` | `query` | Łączy wyniki SearxNG i DuckDuckGo, usuwa powtórzone URL-e i filtruje wyniki według trafności. Opcjonalne `maxResults` (1–100, domyślnie 10), `dryRun`. Elementy `output.results` zawierają `title`, `url` oraz opcjonalnie `snippet` i `dateText`. `collectionState: empty` oznacza brak zaakceptowanych wyników. |
| `POST /v1/scrape/website` | `urls` (jeden URL lub lista) | Wyodrębnia strony jako Markdown albo tekst. Opcjonalne: `contentFormat` (`markdown`/`text`), `maxChars` (1 000–1 000 000; domyślnie 250 000), pola ograniczające crawl `maxItems`, `maxPages`, `maxDepth`, `includeUrls`, `excludeUrls`, `browserSessionId` oraz `dryRun`. Strony w wyniku mogą zawierać `url`, `title`, `description`, `language`, `markdown`, `text`, `structuredData`, `imageUrls`, `recipe` i metadane obcięcia. |
| `POST /v1/scrape/image` | `url` | Pobiera jeden publiczny obraz rastrowy. W `output` zwraca `contentType`, `finalUrl`, `sizeBytes` i zakodowane w base64 bajty w polu `base64`. Odrzuca prywatne adresy, przekierowania do sieci prywatnych, nieobsługiwane typy mediów, puste pliki i pliki większe niż 15 MB. |
| `POST /v1/scrape/pdf` | `url` | Wyodrębnia warstwę tekstową publicznego pliku PDF. Opcjonalne: `maxPages`, `maxChars`. Skanowane pliki bez osadzonego tekstu nie są przetwarzane przez OCR. |
| `POST /v1/scrape/extract` | `urls` (1–10) oraz `schema` lub `prompt` | Wyodrębnia JSON dla każdej strony. Najpierw wykorzystuje ustrukturyzowane dane strony i znaczniki HTML; do pozostałej ekstrakcji może użyć lokalnego Ollama. Opcjonalne: `maxChars`, `dryRun`. Poziom wsparcia: `experimental`. |
| `POST /v1/research/deep` | `query` | Zbiera i deduplikuje materiały źródłowe, a następnie zwraca ponumerowane dowody (`raw`, domyślnie) albo syntezę modelu lokalnego (`clean`). `raw` nie wymaga Ollama. `clean` jest eksperymentalny, wymaga Ollama i może zwrócić same dowody, jeśli model nie poda prawidłowych cytowań. Opcjonalne: `context`, `instructions`, `mode` (`raw` lub `clean`), `dryRun`. Kompletność odzwierciedla zebrane dowody, a nie pewność modelu. |
| `POST /v1/scrape/deep` | `query` | Trasa zgodności zwracająca lokalne dossier badawcze. Do obsługi `context`, `instructions` i `mode` użyj `/v1/research/deep`. |

### GitHub

Pobieranie danych z GitHuba korzysta z niezalogowanych, publicznych endpointów REST GitHub i podlega limitom dla anonimowych żądań.

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/scrape/github` lub `/v1/scrape/github/profile` | `usernames` (niepusta lista) | Pobiera publiczne profile użytkowników. |
| `POST /v1/scrape/github/repo` | `repository` | Pobiera metadane publicznego repozytorium. |
| `POST /v1/scrape/github/issues` | `repository` | Wyświetla publiczne issues repozytorium. |
| `POST /v1/scrape/github/pulls` | `repository` | Wyświetla publiczne pull requesty. |
| `POST /v1/scrape/github/commits` | `repository` | Wyświetla publiczne commity. |
| `POST /v1/scrape/github/contents` | `repository` | Pobiera zawartość repozytorium; adapter może interpretować dodatkowe pola ścieżki. |
| `POST /v1/scrape/github/search` | `query` | Wyszukuje publiczne dane GitHuba na podstawie przekazanych pól zapytania. |

### YouTube

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/scrape/youtube/search` | `query` | Wyszukuje publiczne filmy. Opcjonalne `maxItems` (domyślnie 5, maksymalnie 100). |
| `POST /v1/scrape/youtube/channel` | `channels` (lista) | Zbiera znormalizowane rekordy publicznych filmów z kanałów. Opcjonalne `maxItems`. |
| `POST /v1/scrape/youtube/shorts` | `channels` (lista) | Zbiera publiczne Shorts z karty kanału `/shorts`; w razie potrzeby filtruje kartę `/videos`. Opcjonalne `maxItems`. |
| `POST /v1/scrape/youtube/transcript` | `url` | Pobiera dostępne publiczne napisy. Opcjonalne `includeSegments` (domyślnie `true`), `maxChars`. |
| `POST /v1/scrape/youtube/thumbnail` | `url` | Zwraca metadane miniatury publicznego filmu. |

Rekordy filmów zawierają, jeśli dostępne, znormalizowane pola takie jak `id`, `url`, `channelHandle` i `isShort`. Dostępność metadanych i napisów zależy od publicznej dostępności filmu.

### Adaptery publicznych źródeł

Nazwa trasy nie oznacza, że każdy dostawca zwraca ustrukturyzowane dane znane z jego komercyjnego API. Sprawdź `GET /v1/capabilities`, aby poznać adapter i ograniczenia.

| Metoda i trasa | Pola żądania | Aktualne działanie |
| --- | --- | --- |
| `POST /v1/scrape/twitter` | Zależne od adaptera; zwykle zapytanie, nazwy użytkowników lub URL-e | Pobiera dane z publicznych stron. Nie jest to ustrukturyzowany kolektor danych X. |
| `POST /v1/scrape/twitter/{search,user,replies}` | Zależne od zasobu | Adapter publicznych stron X/Twitter; wynik best effort. |
| `POST /v1/scrape/instagram/hashtag` | Pola hashtagu | Wyszukiwanie publicznych stron hashtagów. |
| `POST /v1/scrape/instagram/{profile,posts,comments}` | Zależne od zasobu | Pobiera publiczne metadane i strony. Profile i jawne URL-e postów korzystają z metadanych Open Graph; siatki postów, komentarze i statystyki zaangażowania nie są pobierane bez logowania. |
| `POST /v1/scrape/facebook/{ads,groups}` | Zależne od zasobu | `ads` korzysta z Meta Ads Library API i wymaga uprawnionego `N3XUS_API_META_ADS_ACCESS_TOKEN`; `groups` pobiera ogólne publiczne strony. |
| `POST /v1/scrape/tiktok/{search,profile,posts,comments,transcript}` | Zależne od zasobu; `search` wymaga `query` | Pobiera dane ze stron publicznych; nie jest pełnym ustrukturyzowanym API TikToka. |
| `POST /v1/scrape/amazon/{search,product,reviews}` | Zależne od zasobu | Zwraca ustrukturyzowane rekordy z publicznych stron Amazona w USA, Wielkiej Brytanii i Niemczech. Amazon może blokować automatyczne żądania; zablokowane strony nie generują fikcyjnych danych o produktach. |
| `POST /v1/scrape/threads/posts` | `urls` (jeden URL lub lista); opcjonalne `maxItems` | Pobiera publiczne strony pod wskazanymi URL-ami; nie jest ustrukturyzowanym kolektorem postów Threads. |
| `POST /v1/scrape/open-business/search` | `search`; opcjonalnie `location`, `maxItems` (do 50) i `radiusMeters` (1 000–50 000 m; domyślnie 10 000 m) | Dla nazw konkretnych miejsc wyszukuje w Nominatim. Dla rozpoznanych kategorii (stacje ładowania, kawiarnie, restauracje, apteki, stacje paliw, supermarkety) geokoduje `location` w Nominatim, a potem wyszukuje obiekty po tagach OSM w Overpass. Gdy Overpass jest niedostępny, szuka kategorii i lokalizacji tekstowo w Nominatim oraz odrzuca wyniki poza promieniem; taka odpowiedź ma `source.collectionState: "partial"`, bo może nie zawierać wszystkich miejsc. Nie zwraca ocen ani liczby opinii; telefon i strona WWW pojawiają się tylko, gdy są w tagach OSM. Wymaga `© OpenStreetMap contributors`. |
| `POST /v1/scrape/google/places` | Pola wyszukiwania/lokalizacji | Przestarzały alias zgodności obsługiwany przez OpenStreetMap, a nie Google Places. Korzysta z tych samych reguł wyszukiwania co zalecana trasa `/v1/scrape/open-business/search`. |

## Zadania przeglądarki i sesje operatora

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/browser/act` | `task`, `startUrl` | Korzysta z lokalnego Playwright i Ollama do ograniczonego odczytu publicznych stron, nawigacji po linkach, filtrowania, sortowania, paginacji i wyszukiwania. Zwraca ślad działań. Logowanie, zakupy, rozwiązywanie CAPTCHA i wysyłanie formularzy nie są obsługiwane. |
| `POST /v1/browser/sessions` | `startUrl` | Otwiera widoczne okno Chromium do ręcznej obsługi przez operatora. Operator może sam wykonać czynności na stronie. |
| `GET /v1/browser/sessions/{sessionId}` | Parametr ścieżki `sessionId` | Zwraca stan lokalnej sesji i bieżący URL. |
| `POST /v1/browser/sessions/{sessionId}/resume` | Pola jak w `/v1/scrape/website`; poza trybem dry-run można pominąć `urls` | Wykonuje scrape z jawnym użyciem cookies sesji i lokalnego kontekstu przeglądarki. |
| `DELETE /v1/browser/sessions/{sessionId}` | Parametr ścieżki `sessionId` | Zamyka sesję i usuwa zapisane dane przeglądarki. |

Cookies i local storage sesji pozostają w lokalnym katalogu danych i są używane wyłącznie po jawnym podaniu `browserSessionId`. API nie zwraca cookies ani nie wpisuje danych logowania.

## SEO

Wszystkie trasy SEO korzystają z lokalnych wyników SearxNG. Bezpłatne źródła nie udostępniają wiarygodnych wartości wolumenu słów kluczowych, CPC, trudności, trendu ani nakładania się wyników; te pola pozostają `null`, dopóki nie zostanie wdrożone zatwierdzone źródło.

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/seo/keyword` | `keywords` (1–100 tekstów) | Zwraca lokalnie dostępne dane o słowach kluczowych i SERP; niedostępne metryki komercyjne pozostają `null`. |
| `POST /v1/seo/rank` | `keyword`, `domain` | Sprawdza zaobserwowaną pozycję domeny; opcjonalne `depth` (domyślnie 10). |
| `POST /v1/seo/competitors` | `domain` | Znajduje domeny konkurencji w lokalnych wynikach SERP; opcjonalne `limit` (domyślnie 10). |
| `POST /v1/seo/optimize` | `keyword`, `text` | Korzysta z Ollama, aby zaproponować konkretne zmiany w podanym tekście. |
| `POST /v1/seo/audit` | `keyword` | Zwraca zaobserwowaną pozycję; obecnie nie tworzy rekomendacji. |

Zasady doboru dostawców i pól opisuje [strategia dostawców SEO](seo-provider-strategy.md).

## E-mail i wyszukiwanie danych o firmach

Funkcje e-mail i kontaktów działają lokalnie. Wysyłka SMTP jest opcjonalna i wymaga konfiguracji operatora. Weryfikacja e-mail sprawdza wyłącznie składnię, a nie dostarczalność do skrzynki. Szczegóły: [wysyłka e-mail](email-delivery.md) i [zasady weryfikacji e-mail](email-verification-policy.md).

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/email/find` | `firstName`, `lastName` i `domain` (lub `company`) | Wyszukuje wyłącznie jawnie opublikowane adresy na stronach firmy; nie zgaduje adresów. |
| `POST /v1/email/verify` | `email` | Sprawdza tylko składnię i informuje, że nie sprawdzono istnienia skrzynki. |
| `POST /v1/email/enrich` | `email` | W trybie lokalnym zwraca `not_found`; nie korzysta z brokerów danych osobowych. |
| `POST /v1/company/enrich` | `domain` | Pobiera publiczne strony główne, „o nas” i kontakt w obrębie tej samej domeny; nieobecne pola pozostają pominięte. |
| `GET /v1/email/domains` | — | Wyświetla lokalne domeny nadawcy i rekordy DNS do weryfikacji. |
| `POST /v1/email/domains` | `domain` | Tworzy wpis domeny i token DNS TXT dla domeny kontrolowanej przez operatora. |
| `POST /v1/email/domains/{domainId}/verify` | Parametr ścieżki `domainId` | Sprawdza, czy oczekiwany rekord TXT jest widoczny. |
| `DELETE /v1/email/domains/{domainId}` | Parametr ścieżki `domainId` | Usuwa lokalny wpis domeny. |
| `GET /v1/email/identities` | — | Wyświetla lokalne tożsamości nadawców. |
| `POST /v1/email/identities` | `email` albo `username` i `domain` | Tworzy domyślną tożsamość nadawcy; `displayName` jest opcjonalne. Adres może pochodzić z `N3XUS_API_SMTP_FROM`. |
| `PATCH /v1/email/identities/{emailIdentityId}` | `displayName` | Zmienia nazwę wyświetlaną nadawcy. |
| `GET /v1/email/drafts` | — | Wyświetla lokalne szkice e-maili. |
| `GET /v1/email/messages` | — | Wyświetla wiadomości wysłane przez to lokalne API. |
| `POST /v1/email/send` | `to`, `subject`, `text` | Domyślnie zapisuje szkic. Dodaj `send: true`, aby wysłać wiadomość przez skonfigurowany SMTP. |
| `POST /v1/email/drafts/{draftId}/send` | Parametr ścieżki `draftId` | Wysyła zapisany szkic przez skonfigurowany SMTP, a następnie usuwa szkic. |

## Transkrypcja i generowanie obrazów

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/transcribe/uploads` | `filename`, `sizeBytes` | Tworzy prywatny slot na upload. Maksymalny rozmiar pliku to 25 MB. |
| `PUT /v1/transcribe/uploads/{uploadId}` | Surowe bajty audio w treści żądania | Wysyła plik do wcześniej utworzonego slotu. |
| `POST /v1/transcribe` | `uploadId` | Wykonuje lokalną transkrypcję faster-whisper; domyślnie używa CPU. |
| `POST /v1/generate/image` | `prompt` | Generuje obraz przy użyciu skonfigurowanego lokalnego serwera zgodnego z AUTOMATIC1111. Wymaga `N3XUS_API_STABLE_DIFFUSION_URL`. |

## Zadania Docker

| Metoda i trasa | Wymagane pola żądania | Działanie |
| --- | --- | --- |
| `POST /v1/vm/run` | `code`, `language` | Uruchamia jednorazowy kontener; opcjonalnie przyjmuje `files` i `outputFiles`. Dostęp tylko dla klientów loopback. Obsługiwane języki i limity opisuje [dokument o wykonywaniu zadań Docker](vm-isolation.md). |
| `GET /v1/vm/files/{requestId}/{fileIndex}` | Parametry ścieżki `requestId`, `fileIndex` | Pobiera plik wyjściowy utworzony przez wcześniejsze zadanie. |

Ta trasa wymaga dostępu do gniazda Dockera i zapewnia izolację kontenera w ograniczonym zakresie, a nie pełną granicę bezpieczeństwa. Nie udostępniaj API niezaufanym klientom.

## Pamięć lokalna

| Metoda i trasa | Żądanie | Działanie |
| --- | --- | --- |
| `GET /v1/memory` | — | Wyświetla lokalne pliki pamięci i ich bieżącą liczbę. |
| `GET /v1/memory/{path}` | Parametr ścieżki `path` | Odczytuje jeden plik. |
| `POST /v1/memory/{path}` | `{"content":"…","ifVersion":1}` | Tworzy lub aktualizuje plik tekstowy UTF-8 o rozmiarze do 256 KB. `ifVersion` chroni przed nadpisaniem zmienionego pliku; niezgodna wersja zwraca HTTP 409. Przy tworzeniu nowego pliku można pominąć to pole. |
| `DELETE /v1/memory/{path}` | Parametr ścieżki `path` | Usuwa jeden plik. |

## Przykład: bezpieczne ponawianie żądania

```bash
curl -X POST http://localhost:8000/v1/search/web \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: search-fastapi-docs-001' \
  -d '{"query":"FastAPI documentation","maxResults":5}'
```

Ponowne wysłanie żądania z tym samym kluczem zwróci zapisany wynik zamiast ponownie wykonywać wyszukiwanie. Do odrębnej operacji użyj innego klucza.
