# Grooming E10.02 — lore-mcp eval

> Retrospective artifact — grooming occurred in
> conversation (2026-08-31), documented after
> implementation.

## Context

Platform component should provide self-service
tools to validate output quality. Consumers
should not need to build ad hoc eval pipelines.

## Definition of Done

1. `lore-mcp eval` CLI subcommand
2. Generate N questions from indexed chunks
   (extractive fallback, RAGAS if installed)
3. For each question: embed → search → score
4. JSON report with per-question and aggregate
   scores
5. `EvalConfig` from env vars (`LORE_LLM_URL`,
   `LORE_LLM_MODEL`)
6. `run_eval()` pipeline function
7. Tests, docs updated

## MVPs

Atomic — single MVP.

## Dependencies

- E10.01 (study) — determines approach
- `ragas>=0.4` optional dependency
- Embedder module for query embedding

## Design decisions

- **Extractive fallback**: `_generate_extractive()`
  selects key sentences from chunks as questions.
  Works without any LLM.
- **Text-overlap scoring**: `_score_retrieval()`
  uses hit rate and word overlap. No external
  dependency.
- **EvalConfig.from_env()**: consistent with
  the project's env-var-based configuration
- **Questions generated from the DB**: no need
  to access original source files at eval time

## Status

Implemented (tag e10.02-mvp1), pending user
validation.

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.
