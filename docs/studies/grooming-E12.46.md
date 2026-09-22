# Grooming E12.46 — Enrich meta labels in source language

- **Status:** Removed (no change needed)
- **Date:** 2026-09-22

## Problem

The audit (2026-09-22) found `Summary:` and
`Keywords:` labels in English on French sources.
The enrichment content (summary text, keywords)
was correctly in French (E12.36), but the
structural labels were in English.

## Analysis

### What the labels do

The `Summary:` / `Keywords:` labels in the
`enrich_meta` prompt serve one purpose: instruct
the LLM to produce structured output (consistent
format across calls). Without them, the LLM
produces free-form text of varying length and
structure.

### What the labels don't do

- **No downstream parsing**: no code in lore-mcp
  reads or matches these labels. The enriched
  markdown is chunked and embedded as raw text.
- **No RAG signal**: embedding models encode
  semantic content, not formatting labels. A few
  English tokens (`Summary:`, `Keywords:`) in
  French text have no measurable effect on
  cosine similarity retrieval.

### Options evaluated

1. **EN labels everywhere** — zero cost, zero
   effect on RAG. Labels are noise for embedding.
2. **Mini-dictionary** — translate labels per
   language. Adds maintenance for cosmetic gain.
3. **Single EN template + LLM instruction** —
   "respond in {lang}" failed with granite-8b
   (E12.36).
4. **LLM translates the prompt** — works but
   adds LLM calls for a cosmetic improvement on
   text no human reads directly.

### Conclusion

The enrichment content is already in the source
language (E12.36). The labels are LLM formatting
instructions, not user-facing or RAG-relevant
text. Translating them adds complexity (any of
options 2-4) for zero functional benefit.

**Decision: no change. Close as removed.**

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
