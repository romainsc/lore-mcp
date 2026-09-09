# Grooming E5.03+04 — Hybrid search BM25+vector

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

Vector search alone misses exact keyword matches.
BM25 (lexical) catches them. Combining both with
Reciprocal Rank Fusion (RRF) gives +13pts
recall@10 (E14.17).

## Solution

Add FTS5 full-text index alongside sqlite-vec
vectors in the `.db` file. At query time, run
both searches and fuse results with RRF.

### Schema addition

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  content, source_file
);
```

Populated at ingest time alongside vector insert.

### Search flow

1. Vector search: existing KNN on chunks_vec
2. FTS5 search: `SELECT * FROM chunks_fts WHERE chunks_fts MATCH ?`
3. RRF fusion: `score = Σ 1/(k + rank_i)` with k=60 (standard)
4. Return top_k merged results

### Integration points

- `store.py`: create FTS5 table, insert text at ingest
- `store.py:search()`: add hybrid mode
- `server.py:search_docs()`: pass through

### Reference

sqlite-rag-mcp project uses the same pattern.

## DoD

1. FTS5 table created at ingest
2. Hybrid search with RRF fusion
3. Backward compatible: existing .db files work
   (vector-only if no FTS5 table)
4. Benchmark: measure recall@10 before/after

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
