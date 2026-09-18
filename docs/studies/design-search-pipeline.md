# Design — Search pipeline

- **Status:** Référence
- **Date:** 2026-09-18
- **Module:** `store.py`

## Query flow

```
query (text + embedding)
│
├─ 1. Retrieve candidates (3× top_k)
│     ├─ Vector KNN (sqlite-vec, cosine)
│     └─ FTS5 full-text (if table exists + query_text)
│
├─ 2. Fuse: RRF (k=60)
│     score(doc) = Σ 1/(k + rank_i + 1) over all lists
│
├─ 3. Filter (post-retrieval)
│     key:value pairs — source, title, author,
│     license, level, date_from, date_to
│
├─ 4. Rerank (optional)
│     Cross-encoder (sentence-transformers)
│     Re-scores query+passage pairs
│
├─ 5. MMR (optional)
│     Maximal Marginal Relevance (λ=0.5)
│     Jaccard similarity on word sets
│
├─ 6. Per-source cap (optional)
│     Max N chunks per source_file
│
├─ 7. Expand (optional, one of)
│     ├─ Parent-child: replace child → parent
│     └─ Adjacent: merge ±window_size chunks
│
└─ 8. Truncate to top_k
```

## Hybrid search

Two retrieval paths run in parallel on 3×top_k:
- **Vector**: `chunks_vec MATCH` (sqlite-vec KNN,
  cosine distance). Score = 1.0 − distance.
- **FTS5**: `chunks_fts MATCH` (BM25 ranking).
  Score = −rank. Falls back to vector-only if
  FTS5 table absent or no query_text.

RRF fuses by summing reciprocal ranks (k=60).
Both paths join `sources` table for biblio.

## Reranking

Optional cross-encoder via sentence-transformers.
Model loaded once, cached in `_reranker` global.
Configured via `reranking.model` in config.yaml.
Re-scores all candidates, returns top_k.

## Context expansion

- **Adjacent** (`window_size`): fetches all chunks
  for the same source_file, merges center ±
  window_size into one text. Deduplicates by
  (source, start, end) key.
- **Parent-child** (`parent_child`): replaces
  child chunk content with parent_chunks content.
  Deduplicates by parent_id.

Mutually applicable — parent first, adjacent
second.

## Key parameters

| Parameter | Default | Source |
|-----------|---------|--------|
| `top_k` | 5 | MCP tool param |
| `query_text` | "" | MCP tool (for FTS5) |
| `reranking_model` | "" | config.yaml |
| `window_size` | 0 | config.yaml |
| `mmr` | false | config.yaml |
| `max_per_source` | 0 | config.yaml |
| `parent_child` | false | config.yaml |
| `filters` | {} | MCP tool param |

## Cross-references

- `docs/architecture.md` — storage schema
- `docs/studies/grooming-E5.03.md` — hybrid search
- `docs/studies/grooming-E5.06.md` — reranking
- `docs/studies/grooming-E5.08.md` — adjacent-chunk
- `docs/studies/grooming-E5.11.md` — context window
- `docs/studies/grooming-E5.12.md` — MMR (E5.12)
- `docs/studies/design-config-registry.md` — config

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
