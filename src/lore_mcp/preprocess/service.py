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

    logger.info("Starting service: %s", start_cmd)
    subprocess.Popen(
        start_cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    api_url = llm_entry.get("api_url", "")
    if api_url:
        _wait_for_health(api_url, timeout)


def stop_service(llm_entry: dict) -> None:
    """Stop an inference service."""
    stop_cmd = llm_entry.get("stop")
    if not stop_cmd:
        return

    logger.info("Stopping service: %s", stop_cmd)
    subprocess.run(
        stop_cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30,
    )


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
    """Poll until service is ready for inference or timeout.

    Two-stage: first wait for /v1/models (HTTP up), then send
    a trivial inference request to confirm the model is loaded.
    """
    import json

    deadline = time.time() + timeout
    models = _models_url(api_url)

    while time.time() < deadline:
        try:
            req = urllib.request.Request(models)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
        time.sleep(2)
    else:
        raise TimeoutError(f"Service at {api_url} not responding after {timeout}s")

    logger.info("Service HTTP up, verifying inference readiness...")

    chat_url = api_url.rstrip("/")
    if not chat_url.endswith("/chat/completions"):
        chat_url = chat_url.rstrip("/") + "/chat/completions"

    # 1x1 red PNG pixel (68 bytes) for minimal VLM probe
    _PROBE_IMG = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
        "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
    )

    body = json.dumps({
        "model": "",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "ok"},
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{_PROBE_IMG}"}},
        ]}],
        "max_tokens": 1,
    }).encode("utf-8")

    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                chat_url, data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    logger.info("Service ready (inference verified)")
                    return
        except Exception:
            pass
        time.sleep(3)

    raise TimeoutError(f"Service at {api_url} HTTP up but inference not ready after {timeout}s")
