# Recipe corpus E2E (n3xusAPI)

Date: 2026-09-15

## Goal

Fetch **200 recipes** from top chefs using local n3xusAPI only (`POST /v1/scrape/website`, `POST /v1/search/web` for discovery).

## Result

| Metric | Value |
| --- | ---: |
| **Total saved** | **200** |
| Primary method | `scrape.website` on official recipe URLs |
| Corpus path | `/home/n3xus/Projekty/przepisy/` |

### By chef (folder)

- **Gordon Ramsay** — `gordonramsay.com/gr/recipes/` (majority of corpus)
- **Jamie Oliver** — `jamieoliver.com/recipes/…`
- **Nigella Lawson** — `nigella.com/recipes/…`
- Other named chefs — partial (0–7 each); search finds URLs but many third-party sites return `blocked` or short markdown locally.

### API quality notes

- After Sandcastle search fusion (#39–#49), Gordon/Jamie recipe **search** returns on-topic URLs; generic queries like „top celebrity chefs” can still be noisy.
- **`site:`** filtering works for Jamie-style queries.
- Reliable bulk harvest for tests: discover URLs from official listing pages, then **scrape** (not search snippets).

## Reproduce

```bash
curl -s http://127.0.0.1:8000/v1/health
python3 /home/n3xus/Projekty/przepisy/pobierz_200.py   # 20×10 attempt
python3 /home/n3xus/Projekty/przepisy/dofill_200_seeds.py  # fill to 200 from seeds via scrape
```

## Tests before push

```bash
cd /home/n3xus/Projekty/n3xus-api
npm run typecheck && npm run test
```
