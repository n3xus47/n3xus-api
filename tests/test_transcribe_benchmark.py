import json
from pathlib import Path

import pytest

from app.transcribe import AudioError
from app.transcribe_benchmark import load_benchmark, render_report, resolve_case_paths, run_benchmark


FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "transcribe"


def benchmark_cases(**overrides):
    case = {
        "id": "sample",
        "file": "jfk.wav",
        "expectedContains": [],
        "provenance": "test fixture",
    }
    case.update(overrides)
    return resolve_case_paths(load_benchmark([case]), FIXTURES)


def test_load_benchmark_validates_fixture():
    with pytest.raises(ValueError, match="non-empty"):
        load_benchmark([])
    cases = resolve_case_paths(
        load_benchmark(json.loads((FIXTURES / "benchmark.json").read_text())["cases"]),
        FIXTURES,
    )
    assert cases[0]["id"] == "jfk-inaugural-excerpt"


def test_run_benchmark_scores_phrases_and_latency(monkeypatch):
    class FakeInfo:
        language = "en"

    class FakeSegment:
        def __init__(self, text, start, end):
            self.text = text
            self.start = start
            self.end = end

    class FakeModel:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def transcribe(self, path, **kwargs):
            assert Path(path).is_file()
            return [FakeSegment("And so my fellow Americans", 0, 1)], FakeInfo()

    monkeypatch.setattr("app.transcribe.create_whisper_model", lambda *args, **kwargs: FakeModel())
    results = run_benchmark(cases=benchmark_cases(expectedContains=["fellow americans", "missing phrase"]))
    assert results[0]["latencyMs"] >= 0
    assert results[0]["coverage"] == 0.5
    assert not results[0]["success"]
    assert results[0]["reason"] == "missing_expected_phrases"
    assert results[0]["device"] == "cpu"


def test_run_benchmark_reports_cuda_config(monkeypatch):
    monkeypatch.setattr("app.transcribe.settings.transcription_device", "cuda")
    monkeypatch.setattr("app.transcribe.settings.transcription_compute_type", "float16")

    class FakeCuda:
        @staticmethod
        def get_cuda_device_count():
            return 1

    monkeypatch.setitem(__import__("sys").modules, "ctranslate2", FakeCuda)

    class FakeModel:
        def __init__(self, model, device, compute_type):
            assert device == "cuda"
            assert compute_type == "float16"

        def transcribe(self, path, **kwargs):
            class Info:
                language = "en"

            return [], Info()

    monkeypatch.setattr(
        "app.transcribe.create_whisper_model",
        lambda model, device, compute_type: FakeModel(model, device, compute_type),
    )
    result = run_benchmark(cases=benchmark_cases())[0]
    assert result["device"] == "cuda"


def test_resolve_device_rejects_unknown(monkeypatch):
    monkeypatch.setattr("app.transcribe.settings.transcription_device", "tpu")
    with pytest.raises(AudioError, match="cpu, cuda, or auto"):
        run_benchmark(cases=benchmark_cases())


def test_render_report_lists_failures():
    text = render_report([{
        "id": "jfk",
        "success": False,
        "coverage": 0.5,
        "latencyMs": 12.3,
        "reason": "missing_expected_phrases",
        "device": "cpu",
        "missingPhrases": ["foo"],
    }])
    assert "missing_expected_phrases" in text
    assert "12.3" in text
