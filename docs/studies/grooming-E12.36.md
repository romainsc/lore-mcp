# Grooming E12.36 — Enrichment in source language

- **Status:** Implémenté
- **Date:** 2026-09-20

## Problem

granite-8b produces English context paragraphs,
Q&A, and summaries on French source documents
(DUDH, hatta, OCDE, linuxfr). This degrades
multilingual RAG retrieval: French queries match
the original text but miss English enrichment.

Microsoft multilingual RAG study confirms:
enrichment in source language produces better
retrieval results.

## Solution

Detect document language and include it in the
enrichment prompts. The enrichment LLM must
produce in the same language as the source.

### Prompt change

Add "Respond in the same language as the content"
to all enrichment prompts. The LLM detects the
language itself — no detection logic needed in
lore-mcp.

Current enrich prompts (enrich.py):
```
"Add a contextual paragraph..."
```

New:
```
"Add a contextual paragraph...
Respond in the same language as the content."
```

Applied to: enrich_context, enrich_qa,
enrich_meta.

## DoD

1. Enrichment prompts include "Respond in the
   same language as the content"
2. French sources get French enrichment
3. English sources get English enrichment
4. No language detection logic in lore-mcp
5. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
