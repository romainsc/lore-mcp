# Grooming E10.09 — AutoRAG multi-model

> Retrospective artifact — grooming occurred in
> conversation (2026-08-31), documented after
> implementation.

## Context

Evaluation and optimization results are specific
to the embedding model. To select the winning
RAG configuration, users need to compare models
(bge-m3, nomic-embed, etc.) alongside chunk
parameters. Models may be local or served via
remote API endpoints.

## Definition of Done

1. `run_optimize()` accepts `embedders` dict
   (name → Embedder) for multi-model iteration
2. `--models` CLI arg: comma-separated names or
   YAML config file path
3. YAML model config supports per-model endpoints
4. 3 metric levels, user-selectable:
   - Embedding (no LLM): score_spread,
     source_diversity, result_diversity
   - Retrieval (ground truth): hit, word_overlap,
     mrr
   - LLM (RAGAS): faithfulness, context_recall
5. Report includes model_name per combination
6. Works without LLM (embedding metrics suffice)
7. Tests, docs, EPUBs updated

## MVPs

Atomic — single MVP extending run_optimize.

## Dependencies

- E10.03 (optimize base)
- E10.08 (auto-configure model from .db) — future

## Design decisions

- **3 metric levels**: not everyone has a chat
  LLM available. Embedding metrics (score_spread,
  source_diversity) are free to compute and
  sufficient to compare models.
- **YAML model config**: supports API endpoints
  per model (vLLM instances running different
  models on the same cluster)
- **CLI flexibility**: comma-separated for quick
  use, YAML for production configs
- **embedders dict**: decouples model lifecycle
  from optimize logic. Caller creates Embedders,
  optimize iterates.
- **METRIC_LEVELS constant**: documents available
  metrics, enables future --metrics CLI flag

## Status

Implemented (tag e10.09), pending user validation.

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.
