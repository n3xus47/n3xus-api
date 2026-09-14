"""Trusted, short-lived Docker jobs for the localhost-only VM endpoint."""
import asyncio
import base64
import json
from pathlib import Path

from requests.exceptions import ReadTimeout, Timeout

from app.config import settings


class VmError(Exception):
    pass


LOG_CHAR_LIMIT = 524_288
RUNTIME_TIMEOUT_SECS = 600
LOCALHOST_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})

IMAGES = {
    "bash": ("alpine:3.20", "main.sh", ["sh", "main.sh"]),
    "python": ("python:3.12-slim", "main.py", ["python", "main.py"]),
    "node": ("node:22-alpine", "main.mjs", ["node", "main.mjs"]),
    "bun": ("oven/bun:1", "main.ts", ["bun", "main.ts"]),
    "rust": ("rust:1-slim", "main.rs", ["sh", "-c", "rustc main.rs -o main && ./main"]),
    "c": ("gcc:14", "main.c", ["sh", "-c", "gcc main.c -o main && ./main"]),
    "go": ("golang:1.23-alpine", "main.go", ["go", "run", "main.go"]),
}


def is_localhost_client(host: str | None) -> bool:
    return host in LOCALHOST_CLIENTS


def bound_logs(stdout: str, stderr: str) -> tuple[str, str, bool, bool]:
    stdout_truncated = len(stdout) > LOG_CHAR_LIMIT
    stderr_truncated = len(stderr) > LOG_CHAR_LIMIT
    return stdout[:LOG_CHAR_LIMIT], stderr[:LOG_CHAR_LIMIT], stdout_truncated, stderr_truncated


def _safe_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value or path.name != value.split("/")[-1]:
        raise VmError("File paths must be relative and cannot contain '..'")
    return path


def _prepare_workspace(request_id: str, code: str, language: str, files: list[dict]) -> tuple[Path, list[str], str]:
    if language not in IMAGES:
        raise VmError("language must be one of bash, python, node, bun, rust, c, or go")
    root = Path(settings.data_dir) / "vm" / request_id
    root.mkdir(parents=True, exist_ok=False)
    image, entrypoint, command = IMAGES[language]
    (root / entrypoint).write_text(code)
    for item in files:
        path, content = item.get("path"), item.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            raise VmError("Each file needs text path and content")
        target = root / _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(content[7:]) if content.startswith("base64,") else content.encode())
    return root, command, image


def collect_output_files(root: Path, request_id: str, output_files: list[str]) -> list[dict]:
    saved: list[dict] = []
    manifest: list[str] = []
    for index, name in enumerate(output_files):
        target = root / _safe_path(name)
        if target.is_file():
            saved.append(
                {
                    "path": name,
                    "downloadPath": f"/v1/vm/files/{request_id}/{index}",
                    "sizeBytes": target.stat().st_size,
                }
            )
            manifest.append(name)
        else:
            saved.append({"path": name, "error": "not_found"})
    (root / ".outputs.json").write_text(json.dumps(manifest))
    return saved


def _container_run_kwargs(mount_root: Path) -> dict:
    return {
        "detach": True,
        "remove": False,
        "working_dir": "/workspace",
        "volumes": {str(mount_root.resolve()): {"bind": "/workspace", "mode": "rw"}},
        "network_mode": "bridge",
        "mem_limit": "1g",
        "nano_cpus": 1_000_000_000,
        "pids_limit": 256,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "read_only": True,
        "tmpfs": {"/tmp": "size=128m"},
    }


def execute_container(client, root: Path, command: list[str], image: str) -> dict:
    mount_root = Path(settings.vm_host_data_dir) / "vm" / root.name if settings.vm_host_data_dir else root
    container = client.containers.run(image, command, **_container_run_kwargs(mount_root))
    execution_state = "complete"
    exit_code: int | None
    try:
        try:
            result = container.wait(timeout=RUNTIME_TIMEOUT_SECS)
            exit_code = result.get("StatusCode")
        except (ReadTimeout, Timeout):
            execution_state = "timeout"
            exit_code = None
            container.kill()
        stdout_raw = container.logs(stdout=True, stderr=False).decode(errors="replace")
        stderr_raw = container.logs(stdout=False, stderr=True).decode(errors="replace")
    finally:
        container.remove(force=True)
    stdout, stderr, stdout_truncated, stderr_truncated = bound_logs(stdout_raw, stderr_raw)
    return {
        "executionState": execution_state,
        "maxRuntimeSecs": RUNTIME_TIMEOUT_SECS,
        "exitCode": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "stdoutTruncated": stdout_truncated,
        "stderrTruncated": stderr_truncated,
    }


def _run(request_id: str, code: str, language: str, files: list[dict], output_files: list[str]) -> dict:
    try:
        import docker
    except ImportError as error:
        raise VmError("Install the Docker Python client and mount /var/run/docker.sock") from error
    root, command, image = _prepare_workspace(request_id, code, language, files)
    try:
        client = docker.from_env()
        result = execute_container(client, root, command, image)
    except VmError:
        raise
    except Exception as error:
        raise VmError("Docker VM execution failed") from error
    result["files"] = collect_output_files(root, request_id, output_files)
    result["isolation"] = {
        "network": "bridge",
        "readOnlyRoot": True,
        "capDropAll": True,
        "noNewPrivileges": True,
        "memLimit": "1g",
        "cpuLimit": 1,
        "pidsLimit": 256,
    }
    return result


async def run(request_id: str, code: str, language: str, files: list[dict], output_files: list[str]) -> dict:
    return await asyncio.to_thread(_run, request_id, code, language, files, output_files)


def output_file(request_id: str, file_index: int) -> Path | None:
    root = Path(settings.data_dir) / "vm" / request_id
    if not root.is_dir() or file_index < 0:
        return None
    manifest = root / ".outputs.json"
    if not manifest.is_file():
        return None
    try:
        names = json.loads(manifest.read_text())
        path = root / _safe_path(names[file_index])
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return path if path.is_file() else None
