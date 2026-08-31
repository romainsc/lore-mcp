# Grooming E10.15 — Wire RAGAS scoring

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

When a judge LLM is configured (LORE_LLM_URL or
build-config.yaml judge section), scoring remains
text-overlap only. RAGAS metrics (faithfulness,
context_recall) are never activated even when
ragas is installed.

## DoD

1. When RAGAS is installed AND judge LLM is
   configured, use RAGAS metrics
2. When RAGAS is not installed, fall back to
   text-overlap (current behavior)
3. Metrics selection via build-config or CLI
4. Tests TDD (mock RAGAS to avoid dependency
   in test suite)
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
