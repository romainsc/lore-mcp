"""LLM enrichment for preprocessing pipeline. See E12.09.

Contextual retrieval and Q&A mode, applied per section.
Uses OpenAI-compatible /v1/chat/completions endpoint.
"""

import json
import re
import urllib.request
import urllib.error


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
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

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
) -> str:
    """Add context paragraphs per section (contextual retrieval)."""
    if not text.strip():
        return text

    sections = _split_sections(text)
    if not sections:
        return text

    result_parts = []
    for heading, body in sections:
        if not body.strip() or not heading:
            result_parts.append(heading + body)
            continue

        prompt = (
            "You are preparing a document section for RAG indexing. "
            "Write a short context paragraph (2-3 sentences, max 100 tokens) "
            "explaining where this section sits in the document and what it covers. "
            "Do not repeat the section content.\n\n"
            f"Section heading: {heading}\n"
            f"Section content: {body[:500]}\n\n"
            "Context paragraph:"
        )

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
) -> str:
    """Append generated questions per section (Q&A mode)."""
    if not text.strip():
        return text

    sections = _split_sections(text)
    if not sections:
        return text

    result_parts = []
    for heading, body in sections:
        if not body.strip() or not heading:
            result_parts.append(heading + body)
            continue

        prompt = (
            "Generate 2-3 questions that this document section answers. "
            "Output only the questions, one per line, prefixed with 'Q: '.\n\n"
            f"Section: {heading}\n{body[:500]}\n\n"
            "Questions:"
        )

        try:
            questions = _call_llm(prompt, llm_url, llm_model, llm_key)
            if questions:
                result_parts.append(f"{heading}{body}\n\n{questions}\n")
            else:
                result_parts.append(heading + body)
        except Exception:
            result_parts.append(heading + body)

    return "\n".join(result_parts)
