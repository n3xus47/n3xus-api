# Local data-quality evaluation

Collected: 2026-09-14T23:43:40.888754+00:00

Success means a succeeded response with all required fields and no reported partial/blocked/empty state.
Field presence does not prove factual accuracy. Support levels come from the registry and are never upgraded by this report.
Missing provenance remains unknown; source records are retained in the adjacent JSON report.

| Capability | Support | Cases | Success rate | Mean field coverage | Mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| search.web | best_effort | 6 | 33.3% | 100.0% | 3816.4 |

| Case | Success | Field coverage | Latency (ms) | Failure reason |
| --- | --- | ---: | ---: | --- |
| search-realism-gordon-recipe | False | 100.0% | 3235.8 | keyword_mismatch |
| search-realism-jamie-site | True | 100.0% | 2862.6 | — |
| search-realism-python-site | False | 100.0% | 3183.7 | url_pattern_mismatch |
| search-realism-wikipedia-topic | False | 100.0% | 3489.5 | url_pattern_mismatch |
| search-realism-github-repo | False | 100.0% | 3698.8 | url_pattern_mismatch |
| search-realism-ietf-rfc | True | 100.0% | 6428.0 | — |
