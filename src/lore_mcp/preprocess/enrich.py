"""LLM enrichment for preprocessing pipeline. See E12.09, E12.14.

Contextual retrieval, Q&A mode, and metadata enrichment per section.
Uses OpenAI-compatible /v1/chat/completions endpoint.
Language detection ensures enrichment matches document language.
"""

import json
import logging
import re
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def _detect_language(text: str, lang: str = "") -> str:
    """Detect document language. Uses manifest lang if provided, else langdetect."""
    if lang:
        lang_map = {"fra": "fr", "eng": "en", "deu": "de", "spa": "es",
                    "ita": "it", "por": "pt", "ara": "ar", "zho": "zh",
                    "jpn": "ja", "kor": "ko", "rus": "ru", "nld": "nl"}
        return lang_map.get(lang, lang[:2] if len(lang) >= 2 else "en")
    try:
        from langdetect import detect
        return detect(text[:500])
    except Exception:
        return "en"


_FALLBACK_PROMPT = "Process this section:\n{heading}\n{body}"

_DEFAULT_PROMPTS = None


def _load_default_prompts() -> dict:
    """Load distributed prompts.yaml from package. See E12.74."""
    from pathlib import Path
    import yaml
    prompts_file = Path(__file__).parent.parent / "prompts.yaml"
    if prompts_file.exists():
        return yaml.safe_load(prompts_file.read_text(encoding="utf-8")) or {}
    return {}


def _get_prompt(lang: str, kind: str, heading: str, body: str,
                config=None) -> str:
    """Get enrichment prompt via cascade: inline config → file → default → fallback. See E12.74."""
    global _DEFAULT_PROMPTS
    truncated = body[:500]

    if config and getattr(config, "enrich_prompts", None):
        tmpl = config.enrich_prompts.get(lang, {}).get(kind)
        if tmpl:
            return tmpl.format(heading=heading, body=truncated)

    if config and getattr(config, "enrich_prompts_file", ""):
        from pathlib import Path
        import yaml
        pf = Path(config.enrich_prompts_file)
        if pf.exists():
            custom = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
            tmpl = custom.get(lang, {}).get(kind)
            if tmpl:
                return tmpl.format(heading=heading, body=truncated)

    if _DEFAULT_PROMPTS is None:
        _DEFAULT_PROMPTS = _load_default_prompts()
    tmpl = _DEFAULT_PROMPTS.get(lang, {}).get(kind)
    if not tmpl:
        tmpl = _DEFAULT_PROMPTS.get("en", {}).get(kind)
    if tmpl:
        if tmpl == _DEFAULT_PROMPTS.get("en", {}).get(kind) and lang != "en":
            return f"Write in {lang}. " + tmpl.format(heading=heading, body=truncated)
        return tmpl.format(heading=heading, body=truncated)

    return _FALLBACK_PROMPT.format(heading=heading, body=truncated)


def _call_llm(
    prompt: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    verify_ssl: bool = True,
) -> str:
    """Call an OpenAI-compatible chat completions endpoint."""
    if not llm_url:
        raise ValueError(
            "LLM api_url is required for enrichment. "
            "Set it in config.yaml llm registry."
        )

    url = llm_url

    body = json.dumps({
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 512,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if llm_key:
        headers["Authorization"] = f"Bearer {llm_key}"

    from lore_mcp.preprocess.service import run_with_interrupt
    import json as _json

    kwargs = {"timeout": 60}
    if not verify_ssl:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["context"] = ctx

    req = urllib.request.Request(url, data=body, headers=headers)

    def _do_fetch():
        with urllib.request.urlopen(req, **kwargs) as resp:
            return _json.loads(resp.read())

    data = run_with_interrupt(_do_fetch)
    return data["choices"][0]["message"]["content"].strip()


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) pairs."""
    parts = re.split(r"(^#{1,4}\s+.+$)", text, flags=re.MULTILINE)
    sections = []
    i = 0
    while i < len(parts):
        if re.match(r"^#{1,4}\s+", parts[i]):
            heading = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            sections.append((heading, body))
            i += 2
        else:
            if parts[i].strip():
                sections.append(("", parts[i]))
            i += 1
    return sections


def enrich_context(
    text: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    lang: str = "",
) -> str:
    """Add context paragraphs per section (contextual retrieval)."""
    if not text.strip():
        return text

    lang = _detect_language(text, lang)
    sections = _split_sections(text)
    if not sections:
        return text

    has_headings = any(h for h, _ in sections)
    if not has_headings:
        sections = [("## Document", text)]

    result_parts = []
    for heading, body in sections:
        if not body.strip() or not heading:
            result_parts.append(heading + body)
            continue

        prompt = _get_prompt(lang, "context", heading, body)

        try:
            context = _call_llm(prompt, llm_url, llm_model, llm_key)
            if context:
                result_parts.append(f"{heading}\n\n{context}\n{body}")
            else:
                result_parts.append(heading + body)
        except Exception:
            result_parts.append(heading + body)

    return "\n".join(result_parts)


def enrich_qa(
    text: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    lang: str = "",
) -> str:
    """Append generated questions per section (Q&A mode)."""
    if not text.strip():
        return text

    lang = _detect_language(text, lang)
    sections = _split_sections(text)
    if not sections:
        return text

    has_headings = any(h for h, _ in sections)
    if not has_headings:
        sections = [("## Document", text)]

    result_parts = []
    for heading, body in sections:
        if not body.strip() or not heading:
            result_parts.append(heading + body)
            continue

        prompt = _get_prompt(lang, "qa", heading, body)

        try:
            questions = _call_llm(prompt, llm_url, llm_model, llm_key)
            if questions:
                result_parts.append(f"{heading}{body}\n\n{questions}\n")
            else:
                result_parts.append(heading + body)
        except Exception:
            result_parts.append(heading + body)

    return "\n".join(result_parts)


def enrich_meta(
    text: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    lang: str = "",
) -> str:
    """Add summary and keywords per section (metadata enrichment)."""
    if not text.strip():
        return text

    lang = _detect_language(text, lang)
    sections = _split_sections(text)
    if not sections:
        return text

    has_headings = any(h for h, _ in sections)
    if not has_headings:
        sections = [("## Document", text)]

    result_parts = []
    for heading, body in sections:
        if not body.strip() or not heading:
            result_parts.append(heading + body)
            continue

        prompt = _get_prompt(lang, "meta", heading, body)

        try:
            meta = _call_llm(prompt, llm_url, llm_model, llm_key)
            if meta:
                result_parts.append(f"{heading}{body}\n\n{meta}\n")
            else:
                result_parts.append(heading + body)
        except Exception:
            result_parts.append(heading + body)

    return "\n".join(result_parts)


def _is_stt_content(text: str) -> bool:
    """Detect if text was produced by STT (contains timestamp headings)."""
    return bool(re.search(r"^## \[\d{2}:\d{2}:\d{2}\]", text, re.MULTILINE))


def enrich_stt_fix(
    text: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
    lang: str = "",
) -> str:
    """Correct STT transcription errors using LLM. See E12.72."""
    if not text.strip():
        return text

    if not _is_stt_content(text):
        return text

    lang = _detect_language(text, lang)
    sections = _split_sections(text)
    if not sections:
        return text

    result_parts = []
    for heading, body in sections:
        if not body.strip():
            result_parts.append(heading + body)
            continue

        try:
            prompt = _get_prompt(lang, "stt_fix", heading, body)
        except KeyError:
            result_parts.append(heading + body)
            continue

        try:
            corrected = _call_llm(prompt, llm_url, llm_model, llm_key)
            if corrected:
                result_parts.append(heading + "\n\n" + corrected + "\n")
            else:
                result_parts.append(heading + body)
        except Exception:
            result_parts.append(heading + body)

    return "\n".join(result_parts)
