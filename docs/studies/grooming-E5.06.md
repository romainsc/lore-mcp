# Grooming E5.06+07 — Reranking cross-encoder

- **Status:** Validé
- **Date:** 2026-09-09

## What is reranking?

### The problem with vector search

Vector search (KNN) compares the embedding of a
query with pre-computed embeddings of chunks.
Embeddings are compressed representations — 768
dimensions to summarize an entire text. This
compression loses nuance. Two texts about
different topics can end up with similar vectors.

### How a cross-encoder works

A **cross-encoder** is a different kind of model.
Instead of comparing two pre-computed vectors,
it takes the query AND a candidate chunk as input
**together**, passes both through a transformer,
and outputs a direct relevance score.

It "reads" both texts side by side instead of
comparing two compressed summaries.

| Step | Method | Speed | Quality |
|------|--------|-------|---------|
| Retrieval (KNN) | Bi-encoder: compare pre-computed vectors | Fast (~ms for thousands) | Good (approximate) |
| Reranking | Cross-encoder: read query+chunk together | Slow (~10ms per pair) | Better (precise) |

### Why both?

A cross-encoder is too slow to score every chunk
in the database (10ms × 10,000 = 100 seconds).
But it is fast enough to re-score 15 candidates
(10ms × 15 = 150ms).

The **retrieve-then-rerank** pattern:
1. KNN returns top 15 candidates (fast, approximate)
2. Cross-encoder re-scores these 15 (slow, precise)
3. Return top 5 after reranking

### Measured impact

+5-15pts nDCG@10 (E14.17). The noisier the
corpus, the more reranking helps — it corrects
vector search mistakes.

Combined with contextual retrieval (E12.09):
- Context alone: −35% retrieval failures
- Context + hybrid BM25 (E5.03): −49%
- Context + hybrid BM25 + reranking: **−67%**

## Study questions (E5.06)

1. **Model candidates**: evaluate available
   cross-encoder models. Criteria per project
   rules: free/libre license, multilingual
   (FR+EN corpus), size, quality (MTEB
   reranking benchmark), latency
2. **GPU/CPU**: cross-encoders are small (~30-100M
   params). CPU is feasible for 15 candidates.
   Same fallback pattern as Embedder (GPU → CPU)
3. **Latency budget**: reranking adds ~50-200ms.
   Must stay within 500ms CPU total (search target)
4. **Configuration**: reranking model is a user
   choice in `config.yaml`, not hardcoded.
   API key optional per model

```yaml
# config.yaml
reranking:
  model: <to be determined by study>
  api_key: sk-...    # optional
```

5. **Optimize dimension**: E10.29 can test
   multiple reranking models alongside other
   params

## Implementation (E5.07)

### Search flow

```python
def search(db, query_text, query_embedding,
           top_k=5, rerank=True):
    candidates = knn_search(db, query_embedding,
                            top_k=top_k * 3)
    if rerank and reranker_available():
        candidates = rerank_candidates(
            query_text, candidates)
    return candidates[:top_k]
```

Note: `search()` currently receives
`query_embedding` only. Needs `query_text` too
for the cross-encoder.

### Integration points

- `config.yaml`: reranking model + optional key
- `store.py:search()`: add query_text param,
  rerank step after KNN
- `server.py:search_docs()`: pass query text
  to search
- `embedder.py` or new `reranker.py`: load and
  run cross-encoder

### Backward compatible

- No reranking config → vector-only (existing
  behavior)
- Reranking is opt-in via config

## DoD

E5.06 (study):
1. Models evaluated with criteria above
2. Recommendation with benchmark data
3. Configuration format defined

E5.07 (implementation):
1. Reranking wired in search pipeline
2. Configurable via config.yaml
3. Optional (no config → no reranking)
4. Benchmark: nDCG@10 before/after on corpus

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
