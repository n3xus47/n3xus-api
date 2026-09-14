# Local data-quality evaluation

Collected: 2026-09-14T18:54:45.993788+00:00

Success means a succeeded response with all required fields and no reported partial/blocked/empty state.
Field presence does not prove factual accuracy. Support levels come from the registry and are never upgraded by this report.
Missing provenance remains unknown; source records are retained in the adjacent JSON report.

| Capability | Support | Cases | Success rate | Mean field coverage | Mean latency (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| research.deep | experimental | 10 | 0.0% | 0.0% | 868.5 |
| scrape.amazon | best_effort | 10 | 0.0% | 0.0% | 921.8 |
| scrape.github | structured | 10 | 100.0% | 100.0% | 622.0 |
| scrape.google | best_effort | 10 | 90.0% | 90.0% | 441.3 |
| scrape.instagram | best_effort | 10 | 100.0% | 100.0% | 3245.5 |
| scrape.website | structured | 10 | 100.0% | 100.0% | 543.5 |
| scrape.youtube | structured | 10 | 80.0% | 80.0% | 12801.2 |
| search.web | best_effort | 10 | 10.0% | 10.0% | 766.2 |
| seo.read | best_effort | 10 | 10.0% | 55.0% | 1623.2 |

| Case | Success | Field coverage | Latency (ms) | Failure reason |
| --- | --- | ---: | ---: | --- |
| website-01 | True | 100.0% | 956.2 | — |
| website-02 | True | 100.0% | 1140.7 | — |
| website-03 | True | 100.0% | 68.0 | — |
| website-04 | True | 100.0% | 383.4 | — |
| website-05 | True | 100.0% | 148.3 | — |
| website-06 | True | 100.0% | 480.3 | — |
| website-07 | True | 100.0% | 121.2 | — |
| website-08 | True | 100.0% | 410.0 | — |
| website-09 | True | 100.0% | 1512.4 | — |
| website-10 | True | 100.0% | 214.7 | — |
| search-01 | False | 0.0% | 1908.3 | empty |
| search-02 | False | 0.0% | 1325.6 | empty |
| search-03 | False | 0.0% | 3014.3 | empty |
| search-04 | False | 0.0% | 159.5 | empty |
| search-05 | True | 100.0% | 173.1 | — |
| search-06 | False | 0.0% | 541.1 | empty |
| search-07 | False | 0.0% | 102.6 | empty |
| search-08 | False | 0.0% | 205.0 | empty |
| search-09 | False | 0.0% | 107.7 | empty |
| search-10 | False | 0.0% | 125.2 | empty |
| github-profile-01 | True | 100.0% | 385.5 | — |
| github-profile-02 | True | 100.0% | 514.1 | — |
| github-profile-03 | True | 100.0% | 406.6 | — |
| github-repo-01 | True | 100.0% | 1135.7 | — |
| github-repo-02 | True | 100.0% | 1323.0 | — |
| github-issues-01 | True | 100.0% | 512.1 | — |
| github-commits-01 | True | 100.0% | 305.6 | — |
| github-pulls-01 | True | 100.0% | 618.6 | — |
| github-search-01 | True | 100.0% | 612.0 | — |
| github-contents-01 | True | 100.0% | 407.3 | — |
| youtube-search-01 | True | 100.0% | 934.0 | — |
| youtube-search-02 | True | 100.0% | 973.5 | — |
| youtube-search-03 | True | 100.0% | 848.9 | — |
| youtube-transcript-01 | True | 100.0% | 1137.0 | — |
| youtube-transcript-02 | False | 0.0% | 1022.1 | scrape_request_failed |
| youtube-thumbnail-01 | False | 0.0% | 305.6 | scrape_request_failed |
| youtube-thumbnail-02 | True | 100.0% | 174.2 | — |
| youtube-channel-01 | True | 100.0% | 70629.3 | — |
| youtube-channel-02 | True | 100.0% | 51232.0 | — |
| youtube-search-04 | True | 100.0% | 755.2 | — |
| research-01 | False | 0.0% | 1194.2 | http_500 |
| research-02 | False | 0.0% | 642.4 | http_500 |
| research-03 | False | 0.0% | 1119.4 | http_500 |
| research-04 | False | 0.0% | 721.9 | http_500 |
| research-05 | False | 0.0% | 1024.6 | http_500 |
| research-06 | False | 0.0% | 711.5 | http_500 |
| research-07 | False | 0.0% | 959.5 | http_500 |
| research-08 | False | 0.0% | 843.7 | http_500 |
| research-09 | False | 0.0% | 655.3 | http_500 |
| research-10 | False | 0.0% | 812.9 | http_500 |
| places-01 | True | 100.0% | 259.9 | — |
| places-02 | True | 100.0% | 878.0 | — |
| places-03 | True | 100.0% | 506.8 | — |
| places-04 | True | 100.0% | 926.1 | — |
| places-05 | True | 100.0% | 512.4 | — |
| places-06 | True | 100.0% | 307.5 | — |
| places-07 | True | 100.0% | 301.7 | — |
| places-08 | True | 100.0% | 297.4 | — |
| places-09 | True | 100.0% | 269.4 | — |
| places-10 | False | 0.0% | 154.2 | missing_required_fields |
| amazon-01 | False | 0.0% | 719.0 | missing_required_fields |
| amazon-02 | False | 0.0% | 818.0 | missing_required_fields |
| amazon-03 | False | 0.0% | 1025.3 | missing_required_fields |
| amazon-04 | False | 0.0% | 3015.9 | missing_required_fields |
| amazon-05 | False | 0.0% | 460.9 | missing_required_fields |
| amazon-06 | False | 0.0% | 818.8 | missing_required_fields |
| amazon-07 | False | 0.0% | 819.6 | missing_required_fields |
| amazon-08 | False | 0.0% | 409.7 | missing_required_fields |
| amazon-09 | False | 0.0% | 619.8 | missing_required_fields |
| amazon-10 | False | 0.0% | 511.3 | missing_required_fields |
| social-instagram-01 | True | 100.0% | 3246.5 | — |
| social-instagram-02 | True | 100.0% | 8013.8 | — |
| social-instagram-03 | True | 100.0% | 2570.3 | — |
| social-instagram-04 | True | 100.0% | 2724.9 | — |
| social-instagram-05 | True | 100.0% | 2844.7 | — |
| social-instagram-06 | True | 100.0% | 3402.0 | — |
| social-instagram-07 | True | 100.0% | 2359.8 | — |
| social-instagram-08 | True | 100.0% | 1920.5 | — |
| social-instagram-09 | True | 100.0% | 2075.9 | — |
| social-instagram-10 | True | 100.0% | 3296.6 | — |
| seo-01 | False | 50.0% | 1338.3 | missing_required_fields |
| seo-02 | False | 50.0% | 1538.6 | missing_required_fields |
| seo-03 | False | 50.0% | 1023.8 | missing_required_fields |
| seo-04 | True | 100.0% | 1638.4 | — |
| seo-05 | False | 50.0% | 1863.2 | missing_required_fields |
| seo-06 | False | 50.0% | 2127.7 | missing_required_fields |
| seo-07 | False | 50.0% | 1228.6 | missing_required_fields |
| seo-08 | False | 50.0% | 1232.1 | missing_required_fields |
| seo-09 | False | 50.0% | 1227.4 | missing_required_fields |
| seo-10 | False | 50.0% | 3013.4 | missing_required_fields |
