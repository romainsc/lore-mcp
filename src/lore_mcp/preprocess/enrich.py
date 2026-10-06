"""LLM enrichment for preprocessing pipeline. See E12.09, E12.14.

Contextual retrieval, Q&A mode, and metadata enrichment per section.
Uses LLMConfig for typed endpoint configuration.
Language detection ensures enrichment matches document language.
"""

import logging
import re

from lore_mcp.preprocess.llm import LLMConfig, call_llm, call_llm_batch

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


def _enrich_sections(
    text: str,
    llm: LLMConfig,
    lang: str,
    kind: str,
    assemble,
) -> str:
    """Generic section enrichment with concurrent LLM calls."""
    if not text.strip():
        return text

    lang = _detect_language(text, lang)
    sections = _split_sections(text)
    if not sections:
        return text

    has_headings = any(h for h, _ in sections)
    if not has_headings:
        sections = [("## Document", text)]

    prompts = []
    prompt_indices = []
    for i, (heading, body) in enumerate(sections):
        if body.strip() and heading:
            prompts.append(_get_prompt(lang, kind, heading, body))
            prompt_indices.append(i)

    results = [None] * len(sections)
    if prompts:
        try:
            llm_results = call_llm_batch(llm, prompts)
            for j, idx in enumerate(prompt_indices):
                results[idx] = llm_results[j]
        except Exception:
            pass

    result_parts = []
    for i, (heading, body) in enumerate(sections):
        result_parts.append(assemble(heading, body, results[i]))

    return "\n".join(result_parts)


def enrich_context(
    text: str,
    llm_url: str = "",
    llm_model: str = "",
    llm_key: str = "",
    lang: str = "",
    verify_ssl: bool = True,
    concurrency: int = 1,
    llm: LLMConfig | None = None,
) -> str:
    """Add context paragraphs per section (contextual retrieval)."""
    if llm is None:
        llm = LLMConfig(api_url=llm_url, model=llm_model, api_key=llm_key,
                         verify_ssl=verify_ssl, concurrency=concurrency)

    def assemble(heading, body, context):
        if context:
            return f"{heading}\n\n{context}\n{body}"
        return heading + body

    return _enrich_sections(text, llm, lang, "context", assemble)


def enrich_qa(
    text: str,
    llm_url: str = "",
    llm_model: str = "",
    llm_key: str = "",
    lang: str = "",
    verify_ssl: bool = True,
    concurrency: int = 1,
    llm: LLMConfig | None = None,
) -> str:
    """Append generated questions per section (Q&A mode)."""
    if llm is None:
        llm = LLMConfig(api_url=llm_url, model=llm_model, api_key=llm_key,
                         verify_ssl=verify_ssl, concurrency=concurrency)

    def assemble(heading, body, questions):
        if questions:
            return f"{heading}{body}\n\n{questions}\n"
        return heading + body

    return _enrich_sections(text, llm, lang, "qa", assemble)


def enrich_meta(
    text: str,
    llm_url: str = "",
    llm_model: str = "",
    llm_key: str = "",
    lang: str = "",
    verify_ssl: bool = True,
    concurrency: int = 1,
    llm: LLMConfig | None = None,
) -> str:
    """Add summary and keywords per section (metadata enrichment)."""
    if llm is None:
        llm = LLMConfig(api_url=llm_url, model=llm_model, api_key=llm_key,
                         verify_ssl=verify_ssl, concurrency=concurrency)

    def assemble(heading, body, meta):
        if meta:
            return f"{heading}{body}\n\n{meta}\n"
        return heading + body

    return _enrich_sections(text, llm, lang, "meta", assemble)


def _is_stt_content(text: str) -> bool:
    """Detect if text was produced by STT (contains timestamp headings)."""
    return bool(re.search(r"^## \[\d{2}:\d{2}:\d{2}\]", text, re.MULTILINE))


def enrich_stt_fix(
    text: str,
    llm_url: str = "",
    llm_model: str = "",
    llm_key: str = "",
    lang: str = "",
    verify_ssl: bool = True,
    concurrency: int = 1,
    llm: LLMConfig | None = None,
) -> str:
    """Correct STT transcription errors using LLM. See E12.72."""
    if not text.strip():
        return text

    if not _is_stt_content(text):
        return text

    if llm is None:
        llm = LLMConfig(api_url=llm_url, model=llm_model, api_key=llm_key,
                         verify_ssl=verify_ssl, concurrency=concurrency)

    lang = _detect_language(text, lang)
    sections = _split_sections(text)
    if not sections:
        return text

    prompts = []
    prompt_indices = []
    for i, (heading, body) in enumerate(sections):
        if body.strip():
            try:
                prompts.append(_get_prompt(lang, "stt_fix", heading, body))
                prompt_indices.append(i)
            except KeyError:
                pass

    results = [None] * len(sections)
    if prompts:
        try:
            llm_results = call_llm_batch(llm, prompts)
            for j, idx in enumerate(prompt_indices):
                results[idx] = llm_results[j]
        except Exception:
            pass

    result_parts = []
    for i, (heading, body) in enumerate(sections):
        corrected = results[i]
        if corrected:
            result_parts.append(heading + "\n\n" + corrected + "\n")
        else:
            result_parts.append(heading + body)

    return "\n".join(result_parts)


def _json_example(speakers: list[str]) -> str:
    """Build a JSON example string for speaker mapping prompt."""
    parts = [f'"{s}": "Name or {s}"' for s in speakers[:4]]
    return ", ".join(parts)


def enrich_speaker_id(
    text: str,
    speakers_hint: str = "",
    llm: LLMConfig | None = None,
    lang: str = "",
    **kwargs,
) -> str:
    """Replace anonymous speaker labels with LLM-inferred names. See E12.125."""
    import json as _json

    if not re.search(r"##\s+Speaker\s+\d+", text):
        return text

    if llm is None or not llm.api_url:
        return text

    speakers_found = sorted(set(re.findall(r"Speaker\s+\d+", text)))
    if not speakers_found:
        return text

    excerpt = text[:3000]

    if speakers_hint:
        prompt = (
            f"This is a multi-speaker transcription. "
            f"Context about the speakers: {speakers_hint}\n\n"
            f"Transcription excerpt:\n{excerpt}\n\n"
            f"Identify each speaker. Return a JSON object mapping "
            f"current labels to real names.\n"
            f"Example: {{{_json_example(speakers_found)}}}\n"
            f"If you cannot identify a speaker, keep the original label. "
            f"Return ONLY the JSON object, no other text."
        )
    else:
        prompt = (
            f"This is a multi-speaker transcription.\n\n"
            f"Transcription excerpt:\n{excerpt}\n\n"
            f"Identify each speaker from context clues "
            f"(self-introductions, names mentioned by others, roles). "
            f"Return a JSON object mapping current labels to real names.\n"
            f"Example: {{{_json_example(speakers_found)}}}\n"
            f"If you cannot identify a speaker, keep the original label. "
            f"Return ONLY the JSON object, no other text."
        )

    try:
        response = call_llm(llm, prompt)
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            mapping = _json.loads(response[start:end])
        else:
            return text
    except Exception as e:
        logger.warning("Speaker identification failed: %s", e)
        return text

    result = text
    for old_label, new_name in mapping.items():
        if old_label != new_name and new_name.strip():
            result = result.replace(old_label, new_name)

    return result
