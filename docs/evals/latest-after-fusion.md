# Local data-quality evaluation

Collected: 2026-09-14T20:17:41.137732+00:00

Success means a succeeded response with all required fields and no reported partial/blocked/empty state.
Field presence does not prove factual accuracy. Support levels come from the registry and are never upgraded by this report.
Missing provenance remains unknown; source records are retained in the adjacent JSON report.

| Capability | Support | Cases | Success rate | Mean field coverage | Mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| research.deep | experimental | 10 | 0.0% | 10.0% | 11032.6 |
| scrape.amazon | structured | 10 | 0.0% | 0.0% | 0.5 |
| scrape.github | structured | 10 | 70.0% | 70.0% | 583.5 |
| scrape.google | best_effort | 10 | 0.0% | 0.0% | 0.8 |
| scrape.twitter | best_effort | 10 | 0.0% | 0.0% | 0.4 |
| scrape.website | structured | 10 | 60.0% | 66.7% | 762.7 |
| scrape.youtube | structured | 10 | 80.0% | 80.0% | 6860.5 |
| search.web | best_effort | 10 | 10.0% | 10.0% | 7221.7 |
| seo.read | best_effort | 10 | 0.0% | 0.0% | 0.4 |

| Case | Success | Field coverage | Latency (ms) | Failure reason |
| --- | --- | ---: | ---: | --- |
| website-01 | True | 100.0% | 1565.9 | — |
| website-02 | True | 100.0% | 1489.9 | — |
| website-03 | True | 100.0% | 723.2 | — |
| website-04 | False | 0.0% | 511.9 | empty |
| website-05 | False | 66.7% | 806.4 | missing_required_fields |
| website-06 | False | 0.0% | 318.0 | empty |
| website-07 | False | 0.0% | 604.3 | empty |
| website-08 | True | 100.0% | 645.2 | — |
| website-09 | True | 100.0% | 650.0 | — |
| website-10 | True | 100.0% | 312.5 | — |
| search-01 | True | 100.0% | 5557.9 | — |
| search-02 | False | 0.0% | 3892.0 | empty |
| search-03 | False | 0.0% | 3798.5 | empty |
| search-04 | False | 0.0% | 3881.3 | empty |
| search-05 | False | 0.0% | 4202.7 | empty |
| search-06 | False | 0.0% | 3862.4 | empty |
| search-07 | False | 0.0% | 20769.7 | empty |
| search-08 | False | 0.0% | 12941.4 | empty |
| search-09 | False | 0.0% | 8191.8 | empty |
| search-10 | False | 0.0% | 5119.2 | empty |
| github-01 | True | 100.0% | 511.2 | — |
| github-02 | True | 100.0% | 408.4 | — |
| github-03 | True | 100.0% | 418.0 | — |
| github-04 | True | 100.0% | 1321.9 | — |
| github-05 | True | 100.0% | 1144.8 | — |
| github-06 | True | 100.0% | 410.9 | — |
| github-07 | True | 100.0% | 489.7 | — |
| github-08 | False | 0.0% | 517.0 | missing_required_fields |
| github-09 | False | 0.0% | 305.6 | missing_required_fields |
| github-10 | False | 0.0% | 307.5 | missing_required_fields |
| youtube-01 | True | 100.0% | 1125.5 | — |
| youtube-02 | True | 100.0% | 1146.4 | — |
| youtube-03 | True | 100.0% | 239.8 | — |
| youtube-04 | True | 100.0% | 1014.4 | — |
| youtube-05 | True | 100.0% | 9428.9 | — |
| youtube-06 | False | 0.0% | 52617.1 | scrape_request_failed |
| youtube-07 | True | 100.0% | 788.4 | — |
| youtube-08 | False | 0.0% | 71.6 | scrape_request_failed |
| youtube-09 | True | 100.0% | 953.1 | — |
| youtube-10 | True | 100.0% | 1220.4 | — |
| research-01 | False | 50.0% | 47897.2 | missing_required_fields |
| research-02 | False | 50.0% | 44112.4 | missing_required_fields |
| research-03 | False | 0.0% | 18310.9 | RemoteProtocolError |
| research-04 | False | 0.0% | 1.2 | ReadError |
| research-05 | False | 0.0% | 0.8 | ReadError |
| research-06 | False | 0.0% | 0.9 | ReadError |
| research-07 | False | 0.0% | 0.7 | ReadError |
| research-08 | False | 0.0% | 0.7 | ReadError |
| research-09 | False | 0.0% | 0.7 | ReadError |
| research-10 | False | 0.0% | 0.8 | ReadError |
| places-01 | False | 0.0% | 1.0 | ReadError |
| places-02 | False | 0.0% | 1.5 | ReadError |
| places-03 | False | 0.0% | 0.8 | ReadError |
| places-04 | False | 0.0% | 0.7 | ReadError |
| places-05 | False | 0.0% | 0.7 | ReadError |
| places-06 | False | 0.0% | 0.7 | ReadError |
| places-07 | False | 0.0% | 0.7 | ReadError |
| places-08 | False | 0.0% | 0.8 | ReadError |
| places-09 | False | 0.0% | 0.7 | ReadError |
| places-10 | False | 0.0% | 0.7 | ReadError |
| amazon-01 | False | 0.0% | 0.7 | ReadError |
| amazon-02 | False | 0.0% | 0.7 | ReadError |
| amazon-03 | False | 0.0% | 0.7 | ReadError |
| amazon-04 | False | 0.0% | 0.8 | ReadError |
| amazon-05 | False | 0.0% | 0.4 | ConnectError |
| amazon-06 | False | 0.0% | 0.4 | ConnectError |
| amazon-07 | False | 0.0% | 0.4 | ConnectError |
| amazon-08 | False | 0.0% | 0.4 | ConnectError |
| amazon-09 | False | 0.0% | 0.5 | ConnectError |
| amazon-10 | False | 0.0% | 0.5 | ConnectError |
| social-01 | False | 0.0% | 0.4 | ConnectError |
| social-02 | False | 0.0% | 0.4 | ConnectError |
| social-03 | False | 0.0% | 0.4 | ConnectError |
| social-04 | False | 0.0% | 0.4 | ConnectError |
| social-05 | False | 0.0% | 0.4 | ConnectError |
| social-06 | False | 0.0% | 0.4 | ConnectError |
| social-07 | False | 0.0% | 0.5 | ConnectError |
| social-08 | False | 0.0% | 0.4 | ConnectError |
| social-09 | False | 0.0% | 0.4 | ConnectError |
| social-10 | False | 0.0% | 0.4 | ConnectError |
| seo-01 | False | 0.0% | 0.4 | ConnectError |
| seo-02 | False | 0.0% | 0.4 | ConnectError |
| seo-03 | False | 0.0% | 0.5 | ConnectError |
| seo-04 | False | 0.0% | 0.4 | ConnectError |
| seo-05 | False | 0.0% | 0.4 | ConnectError |
| seo-06 | False | 0.0% | 0.5 | ConnectError |
| seo-07 | False | 0.0% | 0.4 | ConnectError |
| seo-08 | False | 0.0% | 0.4 | ConnectError |
| seo-09 | False | 0.0% | 0.5 | ConnectError |
| seo-10 | False | 0.0% | 0.4 | ConnectError |
