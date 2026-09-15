# Local data-quality evaluation

Collected: 2026-09-15T00:01:54.529634+00:00

Success means a succeeded response with all required fields and no reported partial/blocked/empty state.
Field presence does not prove factual accuracy. Support levels come from the registry and are never upgraded by this report.
Missing provenance remains unknown; source records are retained in the adjacent JSON report.

| Capability | Support | Cases | Success rate | Mean field coverage | Mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| research.deep | experimental | 10 | 100.0% | 100.0% | 85743.6 |
| scrape.amazon | structured | 10 | 100.0% | 100.0% | 1723.3 |
| scrape.github | structured | 10 | 70.0% | 70.0% | 655.8 |
| scrape.google | best_effort | 10 | 100.0% | 100.0% | 345.2 |
| scrape.twitter | best_effort | 10 | 0.0% | 83.3% | 3479.1 |
| scrape.website | structured | 10 | 60.0% | 66.7% | 593.7 |
| scrape.youtube | structured | 10 | 80.0% | 80.0% | 5969.8 |
| search.web | best_effort | 10 | 100.0% | 100.0% | 4582.9 |
| seo.read | best_effort | 10 | 100.0% | 100.0% | 4167.3 |

| Case | Success | Field coverage | Latency (ms) | Failure reason |
| --- | --- | ---: | ---: | --- |
| website-01 | True | 100.0% | 1167.3 | — |
| website-02 | True | 100.0% | 1014.9 | — |
| website-03 | True | 100.0% | 140.9 | — |
| website-04 | False | 0.0% | 392.7 | empty |
| website-05 | False | 66.7% | 743.5 | missing_required_fields |
| website-06 | False | 0.0% | 283.9 | empty |
| website-07 | False | 0.0% | 539.9 | empty |
| website-08 | True | 100.0% | 614.6 | — |
| website-09 | True | 100.0% | 661.7 | — |
| website-10 | True | 100.0% | 377.2 | — |
| search-01 | True | 100.0% | 2619.3 | — |
| search-02 | True | 100.0% | 3481.1 | — |
| search-03 | True | 100.0% | 6769.5 | — |
| search-04 | True | 100.0% | 3267.1 | — |
| search-05 | True | 100.0% | 3891.6 | — |
| search-06 | True | 100.0% | 11140.9 | — |
| search-07 | True | 100.0% | 3604.2 | — |
| search-08 | True | 100.0% | 3596.8 | — |
| search-09 | True | 100.0% | 3596.3 | — |
| search-10 | True | 100.0% | 3862.0 | — |
| github-01 | True | 100.0% | 414.1 | — |
| github-02 | True | 100.0% | 420.8 | — |
| github-03 | True | 100.0% | 504.2 | — |
| github-04 | True | 100.0% | 1429.8 | — |
| github-05 | True | 100.0% | 1436.7 | — |
| github-06 | True | 100.0% | 402.4 | — |
| github-07 | True | 100.0% | 516.5 | — |
| github-08 | False | 0.0% | 409.1 | missing_required_fields |
| github-09 | False | 0.0% | 513.1 | missing_required_fields |
| github-10 | False | 0.0% | 511.0 | missing_required_fields |
| youtube-01 | True | 100.0% | 1129.3 | — |
| youtube-02 | True | 100.0% | 1022.2 | — |
| youtube-03 | True | 100.0% | 156.3 | — |
| youtube-04 | True | 100.0% | 784.7 | — |
| youtube-05 | True | 100.0% | 8358.8 | — |
| youtube-06 | False | 0.0% | 45725.8 | scrape_request_failed |
| youtube-07 | True | 100.0% | 688.9 | — |
| youtube-08 | False | 0.0% | 66.0 | scrape_request_failed |
| youtube-09 | True | 100.0% | 748.7 | — |
| youtube-10 | True | 100.0% | 1016.9 | — |
| research-01 | True | 100.0% | 88681.6 | — |
| research-02 | True | 100.0% | 70247.2 | — |
| research-03 | True | 100.0% | 64276.9 | — |
| research-04 | True | 100.0% | 101219.2 | — |
| research-05 | True | 100.0% | 90031.5 | — |
| research-06 | True | 100.0% | 91658.1 | — |
| research-07 | True | 100.0% | 80992.3 | — |
| research-08 | True | 100.0% | 103184.4 | — |
| research-09 | True | 100.0% | 73460.3 | — |
| research-10 | True | 100.0% | 93684.8 | — |
| places-01 | True | 100.0% | 585.0 | — |
| places-02 | True | 100.0% | 306.7 | — |
| places-03 | True | 100.0% | 410.2 | — |
| places-04 | True | 100.0% | 410.0 | — |
| places-05 | True | 100.0% | 306.5 | — |
| places-06 | True | 100.0% | 307.0 | — |
| places-07 | True | 100.0% | 205.3 | — |
| places-08 | True | 100.0% | 410.1 | — |
| places-09 | True | 100.0% | 306.5 | — |
| places-10 | True | 100.0% | 204.6 | — |
| amazon-01 | True | 100.0% | 1737.7 | — |
| amazon-02 | True | 100.0% | 1398.8 | — |
| amazon-03 | True | 100.0% | 1212.9 | — |
| amazon-04 | True | 100.0% | 1773.1 | — |
| amazon-05 | True | 100.0% | 1808.0 | — |
| amazon-06 | True | 100.0% | 1996.8 | — |
| amazon-07 | True | 100.0% | 2331.6 | — |
| amazon-08 | True | 100.0% | 1483.5 | — |
| amazon-09 | True | 100.0% | 1808.0 | — |
| amazon-10 | True | 100.0% | 1682.1 | — |
| social-01 | False | 83.3% | 3307.3 | missing_required_fields |
| social-02 | False | 83.3% | 3475.8 | missing_required_fields |
| social-03 | False | 83.3% | 3426.7 | missing_required_fields |
| social-04 | False | 83.3% | 2967.9 | missing_required_fields |
| social-05 | False | 83.3% | 8294.9 | missing_required_fields |
| social-06 | False | 83.3% | 2772.5 | missing_required_fields |
| social-07 | False | 83.3% | 2658.4 | missing_required_fields |
| social-08 | False | 83.3% | 2505.9 | missing_required_fields |
| social-09 | False | 83.3% | 2522.0 | missing_required_fields |
| social-10 | False | 83.3% | 2859.2 | missing_required_fields |
| seo-01 | True | 100.0% | 2482.6 | — |
| seo-02 | True | 100.0% | 10018.4 | — |
| seo-03 | True | 100.0% | 3677.1 | — |
| seo-04 | True | 100.0% | 3376.8 | — |
| seo-05 | True | 100.0% | 3073.9 | — |
| seo-06 | True | 100.0% | 3791.8 | — |
| seo-07 | True | 100.0% | 6962.5 | — |
| seo-08 | True | 100.0% | 2510.6 | — |
| seo-09 | True | 100.0% | 2735.6 | — |
| seo-10 | True | 100.0% | 3044.0 | — |
