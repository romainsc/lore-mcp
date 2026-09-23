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


_ENRICH_PROMPTS = {
    "fr": {
        "context": (
            "Vous préparez une section de document pour l'indexation RAG. "
            "Rédigez un court paragraphe de contexte (2-3 phrases, max 100 tokens) "
            "expliquant la place de cette section dans le document et ce qu'elle couvre.\n\n"
            "Titre de la section : {heading}\n"
            "Contenu de la section : {body}\n\n"
            "Paragraphe de contexte :"
        ),
        "qa": (
            "Générez 2-3 questions auxquelles cette section de document répond. "
            "Produisez uniquement les questions, une par ligne, préfixées par 'Q: '.\n\n"
            "Section : {heading}\n{body}\n\n"
            "Questions :"
        ),
        "meta": (
            "Résumez cette section en 1-2 phrases, puis listez 5-10 mots-clés.\n"
            "Format :\n"
            "Summary: <résumé>\n"
            "Keywords: <mot1>, <mot2>, ...\n\n"
            "Section : {heading}\n{body}"
        ),
    },
    "en": {
        "context": (
            "You are preparing a document section for RAG indexing. "
            "Write a short context paragraph (2-3 sentences, max 100 tokens) "
            "explaining where this section sits in the document and what it covers.\n\n"
            "Section heading: {heading}\n"
            "Section content: {body}\n\n"
            "Context paragraph:"
        ),
        "qa": (
            "Generate 2-3 questions that this document section answers. "
            "Output only the questions, one per line, prefixed with 'Q: '.\n\n"
            "Section: {heading}\n{body}\n\n"
            "Questions:"
        ),
        "meta": (
            "Summarize this section in 1-2 sentences, then list 5-10 keywords.\n"
            "Format:\n"
            "Summary: <summary>\n"
            "Keywords: <keyword1>, <keyword2>, ...\n\n"
            "Section: {heading}\n{body}"
        ),
    },
}


def _get_prompt(lang: str, kind: str, heading: str, body: str) -> str:
    """Get enrichment prompt in the detected language."""
    templates = _ENRICH_PROMPTS.get(lang, {})
    if not templates:
        fallback = _ENRICH_PROMPTS["en"][kind]
        return f"Write in {lang}. " + fallback.format(heading=heading, body=body[:500])
    return templates[kind].format(heading=heading, body=body[:500])


def _call_llm(
    prompt: str,
    llm_url: str,
    llm_model: str,
    llm_key: str = "",
) -> str:
    """Call an OpenAI-compatible chat completions endpoint."""
    if not llm_url:
        raise ValueError(
            "LORE_LLM_URL is required for LLM enrichment. "
            "Set it to an OpenAI-compatible endpoint."
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

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

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
