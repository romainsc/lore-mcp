# Grooming E10.15 — Wire RAGAS scoring

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

When a judge LLM is configured (LORE_LLM_URL or
build-config.yaml judge section), scoring remains
text-overlap only. RAGAS metrics (faithfulness,
context_recall) are never activated even when
ragas is installed.

## Behavior

RAGAS metrics (faithfulness, context_recall, etc.)
are **never activated implicitly**. They must be
explicitly requested in the `metrics` list
(build-config or CLI).

If RAGAS metrics are requested but a prerequisite
is missing:
- RAGAS not installed → **error, stop**
- Judge LLM not configured → **error, stop**
- Judge LLM unreachable → **error, stop**

No fallback. No silent degradation. The user
asked for RAGAS, they get RAGAS or an error.

Embedding and retrieval metrics (score_spread,
mrr, etc.) remain the default — they work
without RAGAS or judge LLM.

## DoD

1. RAGAS metrics only when explicitly listed in
   `metrics` config
2. Fail fast if prerequisites missing (not
   installed, no judge, judge unreachable)
3. Metrics selection via build-config or CLI
4. Tests TDD (mock RAGAS to avoid dependency
   in test suite)
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
