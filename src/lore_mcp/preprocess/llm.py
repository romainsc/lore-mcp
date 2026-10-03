"""Unified LLM call interface with concurrent batch support. See docs/architecture.md."""

import json
import logging
import threading
import time
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Typed configuration for an LLM endpoint."""

    api_url: str = ""
    model: str = ""
    api_key: str = ""
    verify_ssl: bool = True
    concurrency: int = 1
    timeout: int = 60
    max_tokens: int = 512
    temperature: float = 0.3

    @classmethod
    def from_registry(cls, entry: dict) -> "LLMConfig":
        """Build from an llm registry dict entry."""
        return cls(
            api_url=entry.get("api_url", ""),
            model=entry.get("model", ""),
            api_key=entry.get("api_key", ""),
            verify_ssl=entry.get("verify_ssl", True),
            concurrency=entry.get("concurrency", 1),
            timeout=entry.get("timeout", 60),
        )


def call_llm(config: LLMConfig, prompt: str) -> str:
    """Call an OpenAI-compatible chat completions endpoint. Returns content string."""
    if not config.api_url:
        raise ValueError(
            "LLM api_url is required for enrichment. "
            "Set it in config.yaml llm registry."
        )
    from lore_mcp.preprocess.service import run_with_interrupt

    body = json.dumps({
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    kwargs = {"timeout": config.timeout}
    if not config.verify_ssl:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["context"] = ctx

    req = urllib.request.Request(config.api_url, data=body, headers=headers)

    def _do_fetch():
        with urllib.request.urlopen(req, **kwargs) as resp:
            return json.loads(resp.read())

    data = run_with_interrupt(_do_fetch)
    return data["choices"][0]["message"]["content"].strip()


def call_llm_batch(config: LLMConfig, prompts: list[str]) -> list[str]:
    """Call LLM for multiple prompts with concurrency limit.

    Returns results in the same order as prompts.
    Ctrl+C responsive within 0.5s (daemon threads + main poll).
    """
    from lore_mcp.preprocess.service import _shutdown_requested

    if config.concurrency <= 1:
        return [call_llm(config, p) for p in prompts]

    results = [None] * len(prompts)
    errors = [None] * len(prompts)
    sem = threading.Semaphore(config.concurrency)

    def worker(idx, prompt):
        try:
            with sem:
                if _shutdown_requested:
                    return
                results[idx] = call_llm(config, prompt)
        except Exception as e:
            errors[idx] = e

    threads = []
    for i, prompt in enumerate(prompts):
        t = threading.Thread(target=worker, args=(i, prompt), daemon=True)
        t.start()
        threads.append(t)

    while any(t.is_alive() for t in threads):
        time.sleep(0.5)
        if _shutdown_requested:
            raise KeyboardInterrupt("Shutdown requested")

    for i, e in enumerate(errors):
        if e is not None:
            raise e

    return results
