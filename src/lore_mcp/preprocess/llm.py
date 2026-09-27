"""Unified LLM call interface with concurrent batch support. See docs/architecture.md."""

import json
import logging
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)


def call_llm(
    prompt: str,
    api_url: str,
    model: str,
    api_key: str = "",
    verify_ssl: bool = True,
    timeout: int = 60,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
    """Call an OpenAI-compatible chat completions endpoint. Returns content string."""
    if not api_url:
        raise ValueError(
            "LLM api_url is required for enrichment. "
            "Set it in config.yaml llm registry."
        )
    from lore_mcp.preprocess.service import run_with_interrupt

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    kwargs = {"timeout": timeout}
    if not verify_ssl:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["context"] = ctx

    req = urllib.request.Request(api_url, data=body, headers=headers)

    def _do_fetch():
        with urllib.request.urlopen(req, **kwargs) as resp:
            return json.loads(resp.read())

    data = run_with_interrupt(_do_fetch)
    return data["choices"][0]["message"]["content"].strip()


def call_llm_batch(
    prompts: list[str],
    api_url: str,
    model: str,
    api_key: str = "",
    verify_ssl: bool = True,
    timeout: int = 60,
    max_tokens: int = 512,
    temperature: float = 0.3,
    concurrency: int = 1,
) -> list[str]:
    """Call LLM for multiple prompts with concurrency limit.

    Returns results in the same order as prompts.
    Ctrl+C responsive within 0.5s (daemon threads + main poll).
    """
    from lore_mcp.preprocess.service import _shutdown_requested

    if concurrency <= 1:
        return [
            call_llm(p, api_url, model, api_key, verify_ssl,
                     timeout, max_tokens, temperature)
            for p in prompts
        ]

    results = [None] * len(prompts)
    errors = [None] * len(prompts)
    sem = threading.Semaphore(concurrency)

    def worker(idx, prompt):
        try:
            with sem:
                if _shutdown_requested:
                    return
                results[idx] = call_llm(
                    prompt, api_url, model, api_key, verify_ssl,
                    timeout, max_tokens, temperature,
                )
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
