# Grooming E12.56 — Unified model registry

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Embedding and reranking models are outside the
LLM registry. No start/stop lifecycle. Build
fails if embedding service not started manually.

## Solution

All models in `llm:` registry. Specialized
sections reference by name.

### Config migration

```yaml
llm:
  - name: nomic-embed
    model: nomic-ai/nomic-embed-text-v2-moe
    api_url: http://127.0.0.1:8082
    start: podman run -d --name tei-nomic ...
    stop: podman stop tei-nomic-v2
    start_timeout: 120

  - name: granite-reranker
    model: ibm-granite/granite-embedding-reranker-english-r2
    # no start/stop = always available or builtin

embedding:
  model: nomic-embed    # registry lookup
  mode: api             # embedding-specific

reranking:
  model: granite-reranker  # registry lookup
```

### Code changes

1. `_get_embedder()`: resolve model via
   `config.get_llm()`, start_service if needed
2. `Embedder`: receives api_url from registry
3. Search reranking: resolve via registry
4. Build: auto-start embedding, auto-stop after
5. Serve: auto-start at first search_docs

### Lifecycle

```
build:
  start_service(embedding_entry)
  → ingest all sources
  stop_service(embedding_entry)

serve (first search_docs):
  start_service(embedding_entry)
  → embed query → search
  (keep running until server stops)
```

## DoD

1. All models in registry with start/stop
2. embedding.model references registry by name
3. reranking.model references registry by name
4. Build auto-start/stop embedding
5. Serve auto-start embedding at first search
6. Tests
7. No backward compat (pre-release)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
