"""Inference service lifecycle management. See docs/studies/grooming-E12.25.md."""

import logging
import subprocess
import time
import urllib.request

logger = logging.getLogger(__name__)


def start_service(llm_entry: dict, timeout: int = 300) -> None:
    """Start an inference service and wait for it to be ready."""
    start_cmd = llm_entry.get("start")
    if not start_cmd:
        return

    timeout = llm_entry.get("start_timeout", timeout)

    _log_vram()
    logger.info("Starting service: %s", start_cmd)
    subprocess.Popen(
        start_cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    api_url = llm_entry.get("api_url", "")
    if api_url:
        _wait_for_health(api_url, timeout)


def capture_service_logs(llm_entry: dict, output_dir: str = "") -> str:
    """Capture container logs before stopping. Returns log text."""
    stop_cmd = llm_entry.get("stop", "")
    name = llm_entry.get("name", "")
    container = stop_cmd.split()[-1] if stop_cmd else ""
    if not container:
        return ""

    try:
        result = subprocess.run(
            ["podman", "logs", container],
            capture_output=True, text=True, timeout=30,
        )
        logs = result.stdout + result.stderr
    except Exception:
        return ""

    if output_dir and logs.strip():
        from pathlib import Path
        log_path = Path(output_dir) / f"is-logs-{name or container}.txt"
        log_path.write_text(logs, encoding="utf-8")
        logger.info("IS logs saved: %s", log_path)

    return logs


def _log_vram() -> None:
    """Log current GPU VRAM usage for diagnostic."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        logger.debug("VRAM: %s MiB (used, free, total)", result.stdout.strip())
    except Exception:
        pass


def stop_service(llm_entry: dict) -> None:
    """Stop an inference service."""
    stop_cmd = llm_entry.get("stop")
    if not stop_cmd:
        return

    logger.info("Stopping service: %s", stop_cmd)
    _log_vram()
    subprocess.run(
        stop_cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30,
    )
    _log_vram()


def check_service(llm_entry: dict) -> bool:
    """Check if a service is accessible."""
    api_url = llm_entry.get("api_url", "")
    if not api_url:
        return False

    for probe in (_health_url(api_url), _models_url(api_url)):
        try:
            req = urllib.request.Request(probe)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            continue
    return False


def _health_url(api_url: str) -> str:
    """Derive /health URL from an API URL."""
    base = api_url.rstrip("/")
    if "/v1" in base:
        return base.split("/v1")[0] + "/health"
    return base + "/health"


def _models_url(api_url: str) -> str:
    """Derive /v1/models URL from an API URL."""
    base = api_url.rstrip("/")
    if base.endswith("/v1"):
        return base + "/models"
    if "/v1/" in base:
        return base.split("/v1/")[0] + "/v1/models"
    return base + "/v1/models"


def _wait_for_health(api_url: str, timeout: int = 60) -> None:
    """Poll /health until service reports ready or timeout.

    IS containers return {"status": "ok"} on /health when
    the model is loaded and ready for inference.
    """
    deadline = time.time() + timeout
    health = _health_url(api_url)

    while time.time() < deadline:
        try:
            req = urllib.request.Request(health)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info("Service ready (%s)", health)
                    return
        except Exception:
            pass
        time.sleep(2)

    raise TimeoutError(f"Service at {api_url} not ready after {timeout}s")
