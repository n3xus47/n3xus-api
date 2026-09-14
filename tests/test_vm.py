import json

import pytest
from requests.exceptions import ReadTimeout

from app import vm


def test_bound_logs_marks_truncation():
    stdout = "a" * (vm.LOG_CHAR_LIMIT + 10)
    stderr = "b" * 5
    out_stdout, out_stderr, stdout_truncated, stderr_truncated = vm.bound_logs(stdout, stderr)

    assert len(out_stdout) == vm.LOG_CHAR_LIMIT
    assert out_stderr == stderr
    assert stdout_truncated is True
    assert stderr_truncated is False


def test_collect_output_files_reports_missing(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "ok.txt").write_text("data")

    files = vm.collect_output_files(root, "req123", ["ok.txt", "missing.bin"])

    assert files[0]["downloadPath"] == "/v1/vm/files/req123/0"
    assert files[0]["sizeBytes"] == 4
    assert files[1] == {"path": "missing.bin", "error": "not_found"}
    manifest = json.loads((root / ".outputs.json").read_text())
    assert manifest == ["ok.txt"]


def test_execute_container_marks_timeout(monkeypatch, tmp_path):
    class FakeContainer:
        stdout = b"partial"
        stderr = b""

        def wait(self, timeout=None):
            raise ReadTimeout("timed out")

        def logs(self, stdout=True, stderr=False):
            return self.stdout if stdout else self.stderr

        def kill(self):
            self.killed = True

        def remove(self, force=True):
            self.removed = True

    class FakeContainers:
        last_kwargs = None

        def run(self, image, command, **kwargs):
            FakeContainers.last_kwargs = kwargs
            return FakeContainer()

    class FakeClient:
        containers = FakeContainers()

    root = tmp_path / "vm" / "local_test"
    root.mkdir(parents=True)
    (root / "main.py").write_text("print('hi')")

    monkeypatch.setattr(vm.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(vm.settings, "vm_host_data_dir", None)

    result = vm.execute_container(
        FakeClient(),
        root,
        ["python", "main.py"],
        "python:3.12-slim",
    )

    assert result["executionState"] == "timeout"
    assert result["exitCode"] is None
    assert result["stdout"] == "partial"
    assert result["stdoutTruncated"] is False
    assert FakeContainers.last_kwargs["security_opt"] == ["no-new-privileges:true"]
    assert FakeContainers.last_kwargs["read_only"] is True


def test_execute_container_complete_exit_code(monkeypatch, tmp_path):
    class FakeContainer:
        stdout = b"done"
        stderr = b"warn"

        def wait(self, timeout=None):
            return {"StatusCode": 2}

        def logs(self, stdout=True, stderr=False):
            return self.stdout if stdout else self.stderr

        def remove(self, force=True):
            pass

    class FakeContainers:
        def run(self, image, command, **kwargs):
            return FakeContainer()

    class FakeClient:
        containers = FakeContainers()

    root = tmp_path / "vm" / "local_test2"
    root.mkdir(parents=True)

    result = vm.execute_container(FakeClient(), root, ["sh"], "alpine:3.20")

    assert result["executionState"] == "complete"
    assert result["exitCode"] == 2
    assert result["stderr"] == "warn"


def test_go_is_supported_language():
    assert "go" in vm.IMAGES


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("testclient", True),
        ("192.168.1.2", False),
    ],
)
def test_localhost_client_check(host, expected):
    assert vm.is_localhost_client(host) is expected
