# Evaluation harness

Start the local API and its desired local dependencies, then run `npm run eval`.
For local faster-whisper quality and latency on committed legal audio fixtures, run
`npm run eval:transcribe` (see `evals/transcribe/FIXTURES.md`). That command calls
the transcription adapter directly; it does not require the HTTP API to be running.
No credentials are required. A configured API that requires authentication will be
reported as HTTP 401; the harness does not load or send secrets. It accepts only a
localhost HTTP API origin, disables proxy environment settings, and follows no API
redirects. Public target protections remain enforced by the API.

Options: `npm run eval -- --fixtures evals/smoke.json --output docs/evals/latest.md
--base-url http://127.0.0.1:8000 --timeout 120` (on one line).
The timeout is the HTTP client timeout per network operation, in seconds.
Fixtures execute sequentially with fresh idempotency keys to avoid cached replays.
Use only lawful public targets; never include credentials, cookies or private data.

Each JSON fixture has a unique `id`, registered `capability`, public-data API
`route`, request `payload`, and non-empty `required` output paths. Dotted paths
traverse objects; `*` traverses every array record, e.g. `output.results.*.url`.
Null, empty strings, empty lists/objects, and absent fields count as missing;
zero and false are present. Empty arrays contribute a missing observation.
Coverage is present observations divided by all required observations per case;
capability summaries average case coverage. Success requires every observation,
a succeeded envelope, matching capability, and no reported partial/blocked/empty
state. HTTP and transport failures remain in the denominator and the run continues.
A completed report exits successfully even when source evaluations fail; malformed
fixtures or inability to write the report fail the command.

Markdown records success rate, mean coverage, mean latency, and case failure
reasons. Adjacent JSON retains fixture definitions, individual metrics and returned
source provenance. Missing provenance is unknown, not fabricated. Field presence
is not a factual accuracy or quality judgment. Registry support levels are shown
unchanged; best-effort success is not structured-data acceptance. Choose meaningful
source-specific fields rather than generic page text when evaluating adapters.

The single public example-domain fixture proves the harness path only. The M1
corpus lives in `evals/m1-corpus.json` (90 lawful public cases, 10 per suite).
Run `npm run eval -- --fixtures evals/m1-corpus.json --output docs/evals/m1-baseline.md --timeout 180` and commit the generated `docs/evals/m1-baseline.md` and
`docs/evals/m1-baseline.json` as the reproducible baseline. Support levels and
evaluation workflow are documented in the root `README.md`.
