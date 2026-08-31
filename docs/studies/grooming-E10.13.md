# Grooming E10.13 — Unified build config YAML

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

Currently, `lore-mcp build` configuration is
split across multiple sources:
- `manifest.yaml` — sources + biblio
- `models.yaml` — embedding models
- `LORE_LLM_URL/MODEL` env vars — judge LLM
- CLI flags — chunk sizes, num questions, etc.

The user must juggle a YAML file, env vars, and
CLI args. For the target UX (provide everything
lore-mcp needs in one place), all build
configuration should be in one file.

## Proposed format

```yaml
# build-config.yaml

embedding_models:
  - name: BAAI/bge-m3
    mode: local
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: api
    api_url: http://localhost:8081/v1/embeddings
  - name: ibm-granite/granite-embedding-311m-multilingual-r2
    mode: api
    api_url: http://localhost:8082/v1/embeddings

judge:
  model: ibm-granite/granite-3.3-8b-instruct
  api_url: http://localhost:11434/v1
  verify_ssl: false

metrics:
  # Level 1 (no LLM, no ground truth)
  - score_spread
  - source_diversity
  - result_diversity
  # Level 2 (with ground truth)
  - hit
  - mrr
  - word_overlap
  # Level 3 (needs judge LLM via RAGAS)
  # - faithfulness
  # - context_recall

optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
```

## CLI

```bash
lore-mcp build manifest.yaml \
  --docs-dir /path/to/sources/ \
  --output-dir /path/to/output/ \
  --config build-config.yaml
```

The `--config` replaces `--models`, env vars for
judge, and CLI flags for optimize params. CLI
flags can still override config file values.

## Relationship to existing files

- `manifest.yaml` — unchanged, describes WHAT to
  index (sources + biblio). One per collection.
- `build-config.yaml` — describes HOW to build
  (models, judge, metrics, params). Reusable
  across collections.
- Env vars — fallback when no config file. Lower
  precedence than config file.

## DoD

1. `parse_build_config(path) -> BuildConfig`
2. `run_build` accepts `config` parameter
3. Judge LLM config read from file (replaces
   LORE_LLM_URL/MODEL env vars as primary source)
4. Metrics selectable via config
5. Optimize params from config
6. CLI `--config` flag
7. Env vars remain as fallback
8. Tests TDD
9. Documentation

## MVPs

- **MVP1**: parse config file, replace --models
  and optimize CLI flags
- **MVP2**: judge LLM config from file, metrics
  selection

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
