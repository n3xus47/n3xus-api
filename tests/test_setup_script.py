import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("shell_override", "expected_env_limit", "expected_runtime_limit"),
    [(None, "3", "3"), ("2", "5", "2")],
)
def test_fast_start_migrates_old_search_default_and_preserves_override(
    tmp_path, shell_override, expected_env_limit, expected_runtime_limit
):
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "ensure-local-stack.sh"
    shutil.copy2(REPO_ROOT / "scripts/ensure-local-stack.sh", script)
    (repo / ".env.example").write_text("N3XUS_API_SEARCH_VARIANT_LIMIT=3\n")
    env_file = repo / ".env"
    env_file.write_text("N3XUS_API_OLLAMA_MODEL=qwen3.5:4b\nN3XUS_API_SEARCH_VARIANT_LIMIT=5\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "${N3XUS_API_SEARCH_VARIANT_LIMIT:-unset}" >> "$CAPTURED_LIMITS"\n'
        'if [ "$*" = "compose exec -T ollama ollama list" ]; then\n'
        '  printf "NAME ID SIZE MODIFIED\\nqwen3.5:4b sha 1GB now\\n"\n'
        "fi\n"
    )
    docker.chmod(0o755)
    curl = fake_bin / "curl"
    curl.write_text("#!/bin/sh\nexit 0\n")
    curl.chmod(0o755)

    captured_limits = tmp_path / "captured-limits.txt"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CAPTURED_LIMITS": str(captured_limits),
            "N3XUS_API_STARTUP_TIMEOUT_SECS": "2",
        }
    )
    if shell_override is not None:
        env["N3XUS_API_SEARCH_VARIANT_LIMIT"] = shell_override
    else:
        env.pop("N3XUS_API_SEARCH_VARIANT_LIMIT", None)

    result = subprocess.run(
        ["bash", str(script)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=5,
    )

    saved_limit = next(
        line.partition("=")[2]
        for line in env_file.read_text().splitlines()
        if line.startswith("N3XUS_API_SEARCH_VARIANT_LIMIT=")
    )
    runtime_limits = captured_limits.read_text().splitlines()
    assert saved_limit == expected_env_limit
    assert runtime_limits and set(runtime_limits) == {expected_runtime_limit}
    if shell_override is None:
        assert "Migrated the previous default search variant limit from 5 to 3." in result.stdout
    else:
        assert "Migrated the previous default search variant limit" not in result.stdout
