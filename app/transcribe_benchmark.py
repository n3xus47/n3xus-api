"""Local transcription quality and latency benchmark on committed legal audio fixtures."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from app.transcribe import AudioError, resolve_whisper_runtime, transcribe_file


def load_benchmark(raw):
    if not isinstance(raw, list) or not raw:
        raise ValueError("Benchmark cases must be a non-empty JSON array")
    cases = []
    ids = set()
    for case in raw:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in ids:
            raise ValueError("Each benchmark case needs a unique string id")
        ids.add(case["id"])
        file_name = case.get("file")
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("Each benchmark case needs a file path")
        phrases = case.get("expectedContains", [])
        if not isinstance(phrases, list) or not all(isinstance(p, str) and p.strip() for p in phrases):
            raise ValueError("expectedContains must be a list of non-empty strings when present")
        if not isinstance(case.get("provenance"), str) or not case["provenance"].strip():
            raise ValueError("Each case must document audio provenance")
        cases.append({**case, "file": file_name, "expectedContains": phrases})
    return cases


def resolve_case_paths(cases, root: Path):
    resolved = []
    for case in cases:
        path = Path(case["file"])
        if not path.is_absolute():
            path = (root / path).resolve()
        if not path.is_file():
            raise ValueError(f"Benchmark audio file is missing: {case['file']}")
        resolved.append({**case, "path": path})
    return resolved


def phrase_coverage(text: str, phrases: list[str]) -> tuple[float, list[str]]:
    if not phrases:
        return 1.0, []
    lowered = text.lower()
    missing = [phrase for phrase in phrases if phrase.lower() not in lowered]
    return (len(phrases) - len(missing)) / len(phrases), missing


def run_benchmark(cases):
    device, compute_type = resolve_whisper_runtime()
    results = []
    for case in cases:
        started = perf_counter()
        reason = ""
        coverage = 0.0
        missing = []
        output = None
        try:
            output = transcribe_file(case["path"])
            coverage, missing = phrase_coverage(output.get("text", ""), case["expectedContains"])
            if coverage < 1:
                reason = "missing_expected_phrases"
        except AudioError as error:
            reason = str(error)
        results.append({
            "id": case["id"],
            "success": not reason,
            "coverage": coverage,
            "latencyMs": (perf_counter() - started) * 1000,
            "reason": reason,
            "device": device,
            "computeType": compute_type,
            "missingPhrases": missing,
            "provenance": case["provenance"],
            "language": output.get("language") if isinstance(output, dict) else None,
            "textPreview": (output or {}).get("text", "")[:160],
        })
    return results


def render_report(results):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("<", "&lt;")

    lines = [
        "# Local transcription benchmark",
        "",
        f"Collected: {datetime.now(UTC).isoformat()}",
        "",
        "Phrase coverage checks committed legal fixtures only. It is not a word-error-rate certification.",
        "GPU use is opt-in through `N3XUS_API_TRANSCRIPTION_DEVICE`; CPU remains the default.",
        "",
        "| Cases | Success rate | Mean phrase coverage | Mean latency (ms) | Device |",
        "| ---: | ---: | ---: | ---: | --- |",
    ]
    n = len(results)
    device = results[0]["device"] if results else "cpu"
    lines.append(
        f"| {n} | {sum(r['success'] for r in results) / n:.1%} | "
        f"{sum(r['coverage'] for r in results) / n:.1%} | "
        f"{sum(r['latencyMs'] for r in results) / n:.1f} | {device} |"
    )
    lines += ["", "| Case | Success | Phrase coverage | Latency (ms) | Failure reason | Missing phrases |",
              "| --- | --- | ---: | ---: | --- | --- |"]
    for result in results:
        missing = ", ".join(result["missingPhrases"]) or "—"
        lines.append(
            f"| {cell(result['id'])} | {result['success']} | {result['coverage']:.1%} | "
            f"{result['latencyMs']:.1f} | {cell(result['reason'] or '—')} | {cell(missing)} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default="evals/transcribe/benchmark.json")
    parser.add_argument("--output", default="docs/evals/transcribe-benchmark.md")
    args = parser.parse_args()
    fixtures = Path(args.fixtures)
    payload = json.loads(fixtures.read_text())
    cases = resolve_case_paths(load_benchmark(payload["cases"]), fixtures.parent)
    results = run_benchmark(cases)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(results))
    output.with_suffix(".json").write_text(json.dumps({"results": results}, indent=2) + "\n")
    print(f"Wrote {output}: {sum(r['success'] for r in results)}/{len(results)} cases succeeded")


if __name__ == "__main__":
    main()
