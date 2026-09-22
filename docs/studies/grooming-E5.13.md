# Grooming E5.13 — Pre-filtering with sqlite-vec metadata columns

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

Current search uses post-filtering: KNN on all
vectors, then discard non-matching results. With
selective filters, top_k results not guaranteed.

Industry consensus (2025-2026): pre-filtering is
the standard for production RAG. Post-filtering
is an anti-pattern.

## Solution

Use sqlite-vec native metadata columns in vec0.
Pre-filtering via WHERE in KNN query — bitmap
intersection, no JOIN needed.

### Schema change

```sql
CREATE VIRTUAL TABLE chunks_vec USING vec0(
  embedding float[768] distance_metric=cosine,
  +source_file TEXT,
  +level TEXT
);
```

### KNN with pre-filter

```sql
SELECT rowid, distance
FROM chunks_vec
WHERE embedding MATCH ?
  AND k = ?
  AND source_file = ?
ORDER BY distance;
```

### All filter fields

| Field | Pre-filter | SQL op |
|-------|:---:|---|
| source_file | vec0 metadata | `= value` or `LIKE` |
| level | vec0 metadata | `= value` |
| license | JOIN sources | `LIKE '%value%'` |
| title | JOIN sources | `LIKE '%value%'` |
| author | JOIN sources | `LIKE '%value%'` |
| date_from | JOIN sources | `>= value` |
| date_to | JOIN sources | `<= value` |

source_file and level in vec0 (most frequent,
hard constraints). Other fields via sources table
JOIN on the pre-filtered rowids.

### Chain of resolution for field values

1. Manifest (user declaration, source of truth)
2. Inference (extract_source_metadata: front
   matter, first heading, langdetect)
3. Absent → field empty, no filter on that field

## Implementation

1. `create_tables`: add +source_file, +level to vec0
2. `insert_chunk`/`insert_chunks`: populate metadata
3. `_search_vector`: add WHERE clauses for filters
4. Remove `_apply_filters` (post-filter)
5. `_parse_filters`: unchanged (parsing filter string)

No migration, no fallback. Existing .db rebuilt.

## DoD

1. chunks_vec with +source_file, +level metadata
2. All filters as pre-filter (native or JOIN)
3. Metadata columns populated at insertion
4. _apply_filters removed
5. top_k results guaranteed when filter matches
6. Tests

## Sources

- sqlite-vec metadata columns:
  https://alexgarcia.xyz/blog/2024/sqlite-vec-metadata-release/
- Issue #196 (JOIN limitation):
  https://github.com/asg017/sqlite-vec/issues/196
- RAG pre-filtering consensus:
  https://mudassirkhan.me/blog/rag-metadata-filtering-strategies

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
