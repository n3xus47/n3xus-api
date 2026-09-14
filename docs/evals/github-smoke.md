# Local data-quality evaluation

Collected: 2026-09-14T19:14:05.126532+00:00

Success means a succeeded response with all required fields and no reported partial/blocked/empty state.
Field presence does not prove factual accuracy. Support levels come from the registry and are never upgraded by this report.
Missing provenance remains unknown; source records are retained in the adjacent JSON report.

| Capability | Support | Cases | Success rate | Mean field coverage | Mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| scrape.github | structured | 4 | 100.0% | 100.0% | 560.8 |

| Case | Success | Field coverage | Latency (ms) | Failure reason |
| --- | --- | ---: | ---: | --- |
| github-profile-01 | True | 100.0% | 502.5 | — |
| github-issues-01 | True | 100.0% | 615.3 | — |
| github-search-01 | True | 100.0% | 613.8 | — |
| github-contents-01 | True | 100.0% | 511.5 | — |
