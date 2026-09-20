# Grooming E12.38 — LLM post-OCR correction

- **Status:** Implémenté
- **Date:** 2026-09-20

## Problem

Regex `I'` → `l'` is fragile: 40 false positives
on JSON data (worldcup), 106 uncorrected in PDFs
(governing_ai). A regex cannot reliably correct
OCR artifacts without context.

## Solution

Replace regex OCR correction with an LLM
correction pass. Send OCR text to the LLM with
a prompt to correct artifacts without changing
content.

### Implementation

New function in enrich.py or clean.py:

```python
def correct_ocr(text, llm_url, llm_model,
                llm_key) -> str:
    """LLM corrects OCR artifacts."""
    prompt = (
        "The following text was extracted by OCR "
        "and may contain artifacts. Correct OCR "
        "errors (wrong characters, broken words, "
        "apostrophe confusion) without changing "
        "the meaning or content. Preserve all "
        "original text structure and formatting. "
        "Respond in the same language as the "
        "content.\n\n" + text
    )
    ...
```

Called in phase 3 (clean) before enrichment,
only on sources parsed via OCR (images, scanned
PDFs). The backend is tracked in phase1-report
metadata.

Remove `_fix_ocr_artifacts` regex from
`clean_text` — the LLM handles it better.

### When to apply

Only on OCR sources. The phase1-report.json
carries the parse backend. If the source was
parsed via Docling on an image or scanned PDF,
apply LLM correction. If parsed via trafilatura
(HTML) or markitdown (JSON/CSV), skip.

## DoD

1. LLM corrects OCR artifacts on OCR sources
2. Regex `_fix_ocr_artifacts` removed
3. JSON/tables not modified
4. French OCR patterns corrected (I'homme,
   diacritics, etc.)
5. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
