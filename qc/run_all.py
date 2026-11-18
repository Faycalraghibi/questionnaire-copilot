"""Cross-platform launcher for FastAPI and Streamlit (`make run`, decision D21)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from qc.config import get_settings

REPO_ROOT = Path(__file__).parent.parent


def _wait_for_api(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{url}/health", timeout=1.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"API did not become healthy at {url} within {timeout_s}s")


def main() -> None:
    settings = get_settings()
    env = os.environ.copy()
    env.setdefault("API_URL", settings.api_url)

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "qc.api:app",
        "--host",
        settings.api_host,
        "--port",
        str(settings.api_port),
    ]
    ui_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(REPO_ROOT / "ui" / "app.py"),
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ]

    api_proc = subprocess.Popen(api_cmd, cwd=REPO_ROOT, env=env)
    ui_proc: subprocess.Popen | None = None
    try:
        _wait_for_api(settings.api_url)
        print(f"API ready at {settings.api_url}")
        ui_proc = subprocess.Popen(ui_cmd, cwd=REPO_ROOT, env=env)
        print("UI running at http://localhost:8501")
        while True:
            if api_proc.poll() is not None or ui_proc.poll() is not None:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (ui_proc, api_proc):
            if proc is not None and proc.poll() is None:
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    main()
