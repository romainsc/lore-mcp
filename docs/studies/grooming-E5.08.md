# Grooming E5.08 — Adjacent-chunk retrieval

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

A retrieved chunk may lack context. The answer
spans chunk boundaries. Returning surrounding
chunks (i-1, i, i+1) provides continuity.
(Snowflake pattern, E14.17)

## Solution

After KNN search, expand each result to include
adjacent chunks from the same source file.

### Approach

1. Each chunk has `source_file` and `chunk_index`
   in the `chunks` table
2. For each result, query: `SELECT * FROM chunks
   WHERE source_file = ? AND chunk_index IN
   (?, ?, ?)` (i-1, i, i+1)
3. Deduplicate (overlapping windows)
4. Return merged context

### Parameters

- `window_size`: number of adjacent chunks on
  each side (default: 1 → returns 3 chunks)
- Configurable via `top_k` interaction: if
  window=1 and top_k=5, up to 15 chunks returned

### Integration

In `store.py:search()`, after KNN, expand results.
Optional flag `adjacent=True`.

## DoD

1. Adjacent-chunk expansion in search
2. Deduplication of overlapping windows
3. Configurable window_size
4. Test: verify context continuity

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
