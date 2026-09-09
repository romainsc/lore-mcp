# Grooming E6.08 — Parent-child chunking

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

Small chunks give precise retrieval but miss
context. Large chunks give context but dilute
precision. Parent-child chunking indexes small
chunks for precision and retrieves the parent
chunk for context. +15-25% answer precision
(E14.17).

## Solution

### Storage model

Two chunk levels in the database:

```sql
-- Small chunks for search (existing table)
chunks(id, source_file, chunk_index, content,
       metadata, parent_id)

-- Parent chunks for context retrieval
parent_chunks(id, source_file, content)
```

### Ingestion

1. Split into large parent chunks (e.g. 2048)
2. Split each parent into small child chunks
   (e.g. 512)
3. Store both, link via `parent_id`

### Search

1. KNN search on child chunks (precision)
2. For each result, fetch parent chunk (context)
3. Return parent content with child highlight

### Parameters

- `parent_chunk_size`: 2048 (default)
- `child_chunk_size`: 512 (default)
- Overlap per level

### Impact on existing code

- `ingest.py:chunk_document()`: two-pass chunking
- `store.py`: add parent_chunks table, parent_id
  column
- `store.py:search()`: expand to parent after KNN
- Backward compatible: existing .db works (no
  parent_chunks table → skip)

## DoD

1. Two-level chunking at ingest
2. Parent retrieval at search
3. Configurable parent/child sizes
4. Benchmark: measure answer precision before/after
5. Backward compatible with existing .db

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
