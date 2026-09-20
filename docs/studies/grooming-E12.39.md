# Grooming E12.39 — Preserve content during enrichment

- **Status:** Implémenté
- **Date:** 2026-09-20

## Problem

DUDH preamble ("Considérant que...") is in
phase1-parse.md (13K) but absent from the final
(49K enriched). The enrichment LLM may truncate
or summarize original content instead of
preserving it and adding alongside.

## Solution

Add to enrichment prompts: "Preserve all
original text. Add context alongside, do not
replace or summarize the original."

Verify in the enrichment code that all sections
are reconstituted after per-section processing.

## DoD

1. Enrichment prompts preserve original text
2. DUDH final contains preamble
3. No content loss during enrichment
4. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
