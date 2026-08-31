# Grooming E10.01 — RAG evaluation study

> Retrospective artifact — study conducted in
> conversation (2026-08-31), documented after
> completion.

## Context

Openshift consumer demand: the consumer indexed
7 collections (94,646 chunks) and needs to
validate chunking parameters before production.
No integrated evaluation tool exists — would
require ad hoc scripting with SDG Hub + RAGAS.

## Study result

### RAGAS (Apache 2.0, v0.4.3)

Covers both needs:
- **Question generation**: TestsetGenerator
- **Metrics**: faithfulness, context_recall,
  answer_correctness, context_precision

Requires a **chat-capable LLM** (not just
embedding) → new env vars `LORE_LLM_URL`,
`LORE_LLM_MODEL`.

Heavy dependency (~500 MB, pulls langchain) →
must be **optional** (`pip install lore-mcp[eval]`).

### SDG Hub (Red Hat, Apache 2.0)

For training data generation, **not** RAG
evaluation Q&A. Not needed for E10.

### Extractive fallback

Built-in question generation from chunk content
(no LLM needed). Text-overlap scoring (hit,
word_overlap) without external dependencies.
Ensures `lore-mcp eval` works without RAGAS.

## Design decisions

- **RAGAS optional**: base install stays lean
- **Extractive fallback**: eval works everywhere
- **Separate LLM config**: embedding endpoint ≠
  judge LLM endpoint

## Status

Study complete, pending user validation.

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.
