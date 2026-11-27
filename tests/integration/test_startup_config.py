"""Stage 11 startup integration tests.

Proves that the canonical application entrypoint uses validated configuration:
WAXPREP_HOST and WAXPREP_PORT control the real listening address, invalid
configuration prevents startup, and health endpoints still work.

Also covers the in-process ``run()`` wrapper so its body stays under the 100%
coverage gate without spawning a server for every test.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from waxprep import main as main_module
from waxprep.config import Settings

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _clean_env(overrides: dict[str, str]) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("WAXPREP_")}
    env.update(overrides)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _wait_for_http(url: str, timeout: float = 25.0) -> int:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return int(response.status)
        except (urllib.error.URLError, ConnectionError) as exc:  # server not up yet
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"server did not become ready at {url}: {last_error}")


def _stop(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    if process.stdout is not None:
        process.stdout.close()


class TestCanonicalRunFunction:
    """run() passes validated settings to uvicorn instead of CLI defaults."""

    def test_run_uses_validated_host_and_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        def fake_run(app: object, **kwargs: object) -> None:
            captured["app"] = app
            captured.update(kwargs)

        import uvicorn

        monkeypatch.setattr(uvicorn, "run", fake_run)
        monkeypatch.setattr(
            main_module,
            "settings",
            Settings(_env_file=None, host="127.0.0.1", port=6123),
        )

        main_module.run()

        assert captured["host"] == "127.0.0.1"
        assert captured["port"] == 6123
        assert captured["app"] is main_module.get_app()
        assert captured["reload"] is False


class TestModuleEntrypoint:
    """The documented ``python -m waxprep.main`` path is authoritative."""

    def test_entrypoint_binds_configured_host_and_port(self, tmp_path: Path) -> None:
        port = _free_port()
        env = _clean_env({
            "WAXPREP_ENVIRONMENT": "test",
            "WAXPREP_HOST": "127.0.0.1",
            "WAXPREP_PORT": str(port),
            "WAXPREP_LOG_LEVEL": "info",
        })
        process = subprocess.Popen(
            [sys.executable, "-m", "waxprep.main"],
            cwd=tmp_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            assert _wait_for_http(f"{base}/health/liveness") == 200
            assert _wait_for_http(f"{base}/health/readiness") == 200
        finally:
            _stop(process)

    def test_entrypoint_refuses_invalid_configuration(self, tmp_path: Path) -> None:
        env = _clean_env({
            "WAXPREP_HOST": "127.0.0.1",
            "WAXPREP_PORT": "70000",
        })
        completed = subprocess.run(
            [sys.executable, "-m", "waxprep.main"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}".lower()
        assert completed.returncode != 0
        assert "port" in output
        assert "70000" in output

    def test_entrypoint_refuses_production_without_explicit_settings(self, tmp_path: Path) -> None:
        env = _clean_env({"WAXPREP_ENVIRONMENT": "production"})
        completed = subprocess.run(
            [sys.executable, "-m", "waxprep.main"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode != 0
        assert "production" in f"{completed.stdout}\n{completed.stderr}".lower()
