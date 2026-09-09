# Grooming E10.29 — End-to-end optimize

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

`lore-mcp optimize` only varies chunking params
(chunk_size, overlap, top_k). The full pipeline
has more dimensions that affect retrieval quality:
preprocessing (enrich techniques), chunking, and
search (reranking, adjacent-chunk).

## Solution

Extend optimize to vary all pipeline params in
a single run, evaluated against NDCG/recall.

### Dimensions

| Dimension | Values | Stage |
|-----------|--------|-------|
| enrich | none, context, qa, context+qa | Preprocessing |
| chunk_size | 512, 1024, 2048 | Chunking |
| chunk_overlap | 64, 128, 256 | Chunking |
| top_k | 3, 5, 10 | Search |
| rerank | true, false | Search (E5.07) |
| adjacent | 0, 1, 2 | Search (E5.08) |

### Grid size

3 × 3 × 3 × 2 × 3 = 162 configs with enrich
variants. Prohibitive without filtering.

### Approach

Staged optimization:
1. Optimize chunking (existing — chunk_size ×
   overlap × top_k)
2. With winning chunking, test enrich variants
3. With winning enrich+chunking, test search
   variants (rerank, adjacent)

Reduces grid to ~27 + 4 + 6 = 37 configs.

### Dependencies

- E5.07 (reranking) for rerank dimension
- E5.08 (adjacent-chunk) for adjacent dimension
- E12.09 (enrich) for enrich dimension
- All optional: dimensions without implementation
  are skipped

## DoD

1. Optimize varies preprocessing + chunking +
   search params
2. Staged optimization to control grid size
3. Report shows best config across all dimensions
4. Backward compatible: existing optimize works

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
