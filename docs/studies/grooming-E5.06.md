# Grooming E5.06+07 — Reranking cross-encoder

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

Vector retrieval returns candidates ranked by
embedding similarity. A cross-encoder reranker
can re-score these candidates with a more
accurate (but slower) model. +5-15pts nDCG@10
(E14.17).

## Study questions (E5.06)

1. **Model selection**: BGE Reranker v2 (Apache
   2.0) vs ms-marco-MiniLM. License, quality,
   size, latency
2. **Integration point**: after search, before
   returning results. In `store.py:search()` or
   `server.py:search_docs()`?
3. **Latency budget**: reranking adds ~50-200ms
   per query. Acceptable within 500ms CPU target?
4. **Top-N strategy**: retrieve top_k*3 from
   vector, rerank, return top_k

## Implementation (E5.07)

```python
def search(db, query_embedding, top_k=5, rerank=True):
    candidates = knn_search(db, query_embedding, top_k=top_k * 3)
    if rerank:
        candidates = rerank_with_cross_encoder(query, candidates)
    return candidates[:top_k]
```

Optional dependency: `sentence-transformers`
already installed (cross-encoder support built-in).

## DoD

1. E5.06: model selected, integration point
   decided, latency measured
2. E5.07: reranking wired, optional (flag or
   config), benchmark before/after

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
