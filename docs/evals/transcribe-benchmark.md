# Local transcription benchmark

Collected: 2026-09-14T19:20:41.798597+00:00

Phrase coverage checks committed legal fixtures only. It is not a word-error-rate certification.
GPU use is opt-in through `N3XUS_API_TRANSCRIPTION_DEVICE`; CPU remains the default.

| Cases | Success rate | Mean phrase coverage | Mean latency (ms) | Device |
| ---: | ---: | ---: | ---: | --- |
| 1 | 100.0% | 100.0% | 1546.6 | cpu |

| Case | Success | Phrase coverage | Latency (ms) | Failure reason | Missing phrases |
| --- | --- | ---: | ---: | --- | --- |
| jfk-inaugural-excerpt | True | 100.0% | 1546.6 | — | — |
